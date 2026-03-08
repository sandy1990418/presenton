"""
Source context preparation service.

Extracts source/chunk/retrieval logic from stateless_pptx_service so
the main service stays orchestration-focused.
"""

import asyncio
import logging
import os
import re
from collections import defaultdict
from typing import List, Optional

from fastapi import HTTPException

from models.presentation_outline_model import PresentationOutlineModel
from models.stateless_models import SourceChunk
from services.document_chunker import DocumentChunker
from services.documents_loader import DocumentsLoader

logger = logging.getLogger(__name__)

# Global semaphore shared across all requests to limit concurrent file
# parsing operations (CPU/memory-heavy).  Prevents resource exhaustion
# when multiple users upload large files simultaneously.
_GLOBAL_PARSE_SEMAPHORE = asyncio.Semaphore(
    int(os.getenv("STATELESS_GLOBAL_PARSE_CONCURRENCY", "4"))
)


class SourceContextService:
    """Build and score source chunks for outline + slide generation."""

    def __init__(self) -> None:
        self._source_chunk_concurrency = int(
            os.getenv("STATELESS_SOURCE_CHUNK_CONCURRENCY", "2")
        )
        self._max_source_files = int(os.getenv("STATELESS_SOURCE_MAX_FILES", "20"))
        self._max_parse_files = int(os.getenv("STATELESS_SOURCE_MAX_PARSE_FILES", "20"))
        self._max_parse_total_bytes = int(
            os.getenv("STATELESS_SOURCE_MAX_PARSE_BYTES", str(600 * 1024 * 1024))
        )
        self._max_source_chars_per_doc = int(
            os.getenv("STATELESS_SOURCE_MAX_CHARS_PER_DOC", "120000")
        )
        self._max_source_total_chars = int(
            os.getenv("STATELESS_SOURCE_MAX_TOTAL_CHARS", "500000")
        )
        self._max_chunks_per_doc = int(
            os.getenv("STATELESS_SOURCE_MAX_CHUNKS_PER_DOC", "80")
        )
        self._max_total_chunks = int(
            os.getenv("STATELESS_SOURCE_MAX_TOTAL_CHUNKS", "400")
        )
        self._max_outline_prompt_chunks = int(
            os.getenv("STATELESS_OUTLINE_MAX_PROMPT_CHUNKS", "40")
        )
        self._max_chunk_refs_per_slide = int(
            os.getenv("STATELESS_OUTLINE_MAX_REFS_PER_SLIDE", "2")
        )
        self._large_file_bytes_threshold = int(
            os.getenv("STATELESS_SOURCE_LARGE_FILE_BYTES", str(8 * 1024 * 1024))
        )
        self._large_doc_chars_threshold = int(
            os.getenv("STATELESS_SOURCE_LARGE_DOC_CHARS", "250000")
        )
        self._enable_llm_chunk_summary = (
            os.getenv("STATELESS_SOURCE_ENABLE_LLM_SUMMARY", "false").lower() == "true"
        )

    @staticmethod
    def _has_meaningful_text(doc: Optional[str], sample_size: int = 256) -> bool:
        if not doc:
            return False
        head = doc[:sample_size]
        tail = doc[-sample_size:] if len(doc) > sample_size else ""
        return bool(head.strip() or tail.strip())

    def _select_files_for_parsing(self, files: List[str]) -> List[str]:
        if not files:
            return []

        selected: List[str] = []
        total_bytes = 0
        max_files = max(1, self._max_parse_files)
        max_bytes = max(1, self._max_parse_total_bytes)

        for file_path in files:
            if len(selected) >= max_files:
                break

            file_size = 0
            try:
                if os.path.exists(file_path):
                    file_size = max(0, int(os.path.getsize(file_path)))
            except Exception:
                file_size = 0

            if file_size > 0 and total_bytes + file_size > max_bytes:
                continue

            selected.append(file_path)
            total_bytes += file_size

        if not selected and files:
            selected = [files[0]]

        return selected

    @staticmethod
    def _safe_get_file_size(file_path: str) -> int:
        try:
            if os.path.exists(file_path):
                return max(0, int(os.path.getsize(file_path)))
        except Exception:
            return 0
        return 0

    def _compress_document_with_coverage(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text

        target_windows = min(12, max(4, max_chars // 18000))
        marker_overhead = 64
        window_size = max(4000, (max_chars // target_windows) - marker_overhead)
        target_windows = max(1, min(target_windows, max_chars // max(1, window_size)))
        window_size = max(2000, max_chars // max(1, target_windows) - marker_overhead)

        if target_windows <= 1 or len(text) <= window_size:
            return self._truncate_with_head_tail(text, max_chars)

        max_start = max(0, len(text) - window_size)
        step = max(1, max_start // (target_windows - 1))

        windows: List[str] = []
        for i in range(target_windows):
            start = min(i * step, max_start)
            end = start + window_size
            segment = text[start:end]
            windows.append(
                f"[SEGMENT {i + 1}/{target_windows} @ {start}:{end}]\n{segment}"
            )

        compressed = "\n\n".join(windows)
        if len(compressed) > max_chars:
            compressed = self._truncate_with_head_tail(compressed, max_chars)
        return compressed

    @staticmethod
    def _truncate_with_head_tail(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        marker = "\n\n[...trimmed...]\n\n"
        usable = max(1, max_chars - len(marker))
        head = usable // 2
        tail = usable - head
        return f"{text[:head]}{marker}{text[-tail:]}"

    @staticmethod
    def _downsample_chunks(chunks: List, max_chunks: int) -> List:
        if len(chunks) <= max_chunks:
            return chunks
        if max_chunks <= 0:
            return []
        if max_chunks == 1:
            return [chunks[len(chunks) // 2]]

        step = (len(chunks) - 1) / (max_chunks - 1)
        indices = sorted({round(i * step) for i in range(max_chunks)})
        return [chunks[i] for i in indices]

    def _enforce_total_char_budget(self, chunks: List) -> List:
        """Drop chunks once the cumulative content length exceeds the budget."""
        budget = self._max_source_total_chars
        if budget <= 0:
            return chunks

        total_chars = sum(len(getattr(c, "content", "")) for c in chunks)
        if total_chars <= budget:
            return chunks

        # Keep chunks round-robin across documents to maintain coverage
        chunks_by_doc = defaultdict(list)
        for chunk in chunks:
            chunks_by_doc[getattr(chunk, "document_id", 0)].append(chunk)

        doc_ids = sorted(chunks_by_doc.keys())
        per_doc_budget = max(1, budget // len(doc_ids)) if doc_ids else budget

        kept: List = []
        for doc_id in doc_ids:
            doc_chunks = chunks_by_doc[doc_id]
            doc_chars = 0
            for chunk in doc_chunks:
                c_len = len(getattr(chunk, "content", ""))
                if doc_chars + c_len > per_doc_budget and kept:
                    break
                kept.append(chunk)
                doc_chars += c_len

        logger.info(
            "Total char budget: kept %d/%d chunks (%d chars -> budget %d)",
            len(kept),
            len(chunks),
            total_chars,
            budget,
        )
        return kept

    def _cap_total_chunks(self, chunks: List) -> List:
        if len(chunks) <= self._max_total_chunks:
            return chunks

        chunks_by_doc = defaultdict(list)
        for chunk in chunks:
            chunks_by_doc[getattr(chunk, "document_id", 0)].append(chunk)

        doc_ids = sorted(chunks_by_doc.keys())
        if not doc_ids:
            return self._downsample_chunks(chunks, self._max_total_chunks)

        per_doc_cap = max(1, self._max_total_chunks // len(doc_ids))
        capped: List = []
        for doc_id in doc_ids:
            capped.extend(self._downsample_chunks(chunks_by_doc[doc_id], per_doc_cap))

        if len(capped) > self._max_total_chunks:
            capped = self._downsample_chunks(capped, self._max_total_chunks)

        return capped

    @staticmethod
    def _tokenize_for_retrieval(text: str) -> List[str]:
        if not text:
            return []
        return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text.lower())

    def _rank_chunk_ids_for_query(
        self,
        query: str,
        chunks: List,
        top_k: int,
    ) -> List[int]:
        if not chunks or top_k <= 0:
            return []

        query_terms = self._tokenize_for_retrieval(query)
        if not query_terms:
            return [chunk.id for chunk in chunks[:top_k]]

        scored = []
        for chunk in chunks:
            title = getattr(chunk, "title", "") or ""
            summary = getattr(chunk, "summary", "") or ""
            content = getattr(chunk, "content", "") or ""

            title_l = title.lower()
            summary_l = summary.lower()
            content_l = content[:1200].lower()
            score = 0.0

            for term in query_terms:
                if term in title_l:
                    score += 3.0
                elif term in summary_l:
                    score += 1.5
                elif term in content_l:
                    score += 0.5

            scored.append((score, len(summary), len(content), chunk.id))

        scored.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
        ranked_ids = [chunk_id for score, _, _, chunk_id in scored if score > 0]
        if not ranked_ids:
            ranked_ids = [chunk_id for _, _, _, chunk_id in scored]
        return ranked_ids[:top_k]

    def _select_prompt_chunks(
        self,
        chunks: List,
        query: Optional[str],
    ) -> List[dict]:
        if not chunks:
            return []

        max_prompt = max(1, self._max_outline_prompt_chunks)
        candidate_ids = self._rank_chunk_ids_for_query(
            query or "",
            chunks,
            top_k=len(chunks),
        )
        chunks_by_id = {chunk.id: chunk for chunk in chunks}
        ranked_chunks = [
            chunks_by_id[cid] for cid in candidate_ids if cid in chunks_by_id
        ]

        selected = []
        used_ids = set()
        doc_represented = set()
        for chunk in ranked_chunks:
            doc_id = getattr(chunk, "document_id", 0)
            if doc_id in doc_represented:
                continue
            selected.append(chunk)
            used_ids.add(chunk.id)
            doc_represented.add(doc_id)
            if len(selected) >= max_prompt:
                break

        if len(selected) < max_prompt:
            for chunk in ranked_chunks:
                if chunk.id in used_ids:
                    continue
                selected.append(chunk)
                used_ids.add(chunk.id)
                if len(selected) >= max_prompt:
                    break

        prompt_chunks: List[dict] = []
        for local_id, chunk in enumerate(selected):
            chunk_dict = chunk.to_dict()
            chunk_dict["source_chunk_id"] = chunk_dict["id"]
            chunk_dict["id"] = local_id
            if not chunk_dict.get("summary"):
                chunk_dict["summary"] = chunk_dict.get("title", "")
            prompt_chunks.append(chunk_dict)

        return prompt_chunks

    @staticmethod
    def _remap_prompt_chunk_refs(
        outlines: PresentationOutlineModel,
        prompt_chunks: List[dict],
    ) -> None:
        if not prompt_chunks:
            return
        local_to_source = {
            chunk.get("id"): chunk.get("source_chunk_id", chunk.get("id"))
            for chunk in prompt_chunks
        }
        for slide in outlines.slides:
            refs = getattr(slide, "chunk_refs", None)
            if refs is None:
                continue
            mapped_refs = []
            seen = set()
            for ref in refs:
                source_ref = local_to_source.get(ref)
                if source_ref is None or source_ref in seen:
                    continue
                mapped_refs.append(source_ref)
                seen.add(source_ref)
            slide.chunk_refs = mapped_refs

    def _assign_chunk_refs_to_outlines(
        self,
        outlines: PresentationOutlineModel,
        source_chunks: Optional[List[SourceChunk]],
        query: Optional[str],
    ) -> None:
        if not source_chunks:
            return

        valid_ids = {chunk.id for chunk in source_chunks}
        default_refs = self._rank_chunk_ids_for_query(
            query or "",
            source_chunks,
            top_k=self._max_chunk_refs_per_slide,
        )

        for slide in outlines.slides:
            slide_text = (slide.content or "").strip()
            if slide_text.lower().startswith("table of contents"):
                slide.chunk_refs = []
                continue

            refs = getattr(slide, "chunk_refs", None) or []
            valid_refs = []
            seen = set()
            for ref in refs:
                if ref in valid_ids and ref not in seen:
                    valid_refs.append(ref)
                    seen.add(ref)

            if valid_refs:
                slide.chunk_refs = valid_refs[: self._max_chunk_refs_per_slide]
                continue

            ranked_refs = self._rank_chunk_ids_for_query(
                f"{query or ''}\n{slide_text}",
                source_chunks,
                top_k=self._max_chunk_refs_per_slide,
            )
            slide.chunk_refs = ranked_refs or default_refs

    async def _prepare_source_context(
        self,
        files: Optional[List[str]],
        query: Optional[str] = None,
    ) -> tuple[str, Optional[List[SourceChunk]], Optional[str], Optional[List[dict]]]:
        additional_context = ""
        source_chunks: Optional[List[SourceChunk]] = None
        source_summary: Optional[str] = None
        chunks_for_prompt: Optional[List[dict]] = None

        if not files:
            return additional_context, source_chunks, source_summary, chunks_for_prompt
        if len(files) > self._max_source_files:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {self._max_source_files} files are supported per request.",
            )

        files_to_parse = self._select_files_for_parsing(files)
        if not files_to_parse:
            return additional_context, source_chunks, source_summary, chunks_for_prompt

        per_request_semaphore = asyncio.Semaphore(self._source_chunk_concurrency)
        n_files = len(files_to_parse)

        # When there are many files, each file gets a proportional share
        # of the total char budget so we compress *before* chunking.
        per_doc_budget = min(
            self._max_source_chars_per_doc,
            max(20_000, self._max_source_total_chars // max(1, n_files)),
        )

        async def chunk_one_document(file_path: str, document_id: int):
            async with _GLOBAL_PARSE_SEMAPHORE, per_request_semaphore:
                file_size = self._safe_get_file_size(file_path)
                loader = DocumentsLoader(file_paths=[file_path])
                await loader.load_documents()
                raw_documents = [
                    doc for doc in loader.documents if self._has_meaningful_text(doc)
                ]
                if not raw_documents:
                    return [], False

                merged_text = "\n\n".join(raw_documents)
                is_large_document = (
                    file_size >= self._large_file_bytes_threshold
                    or len(merged_text) >= self._large_doc_chars_threshold
                )

                # Always compress when text exceeds per-doc budget,
                # not just for "large" documents.
                needs_compress = is_large_document or len(merged_text) > per_doc_budget
                budgeted_text = (
                    self._compress_document_with_coverage(
                        merged_text,
                        per_doc_budget,
                    )
                    if needs_compress
                    else merged_text
                )

                chunker = DocumentChunker()
                chunks = await chunker.chunk_documents(
                    budgeted_text,
                    generate_summaries=(
                        self._enable_llm_chunk_summary and not is_large_document
                    ),
                    document_id=document_id,
                )
                if not self._enable_llm_chunk_summary:
                    for chunk in chunks:
                        if not chunk.summary:
                            chunk.summary = chunker._extract_summary(chunk.content)
                if not chunks and self._has_meaningful_text(budgeted_text):
                    fallback_chunker = DocumentChunker(min_chunk_size=1)
                    chunks = await fallback_chunker.chunk_documents(
                        budgeted_text,
                        generate_summaries=(
                            self._enable_llm_chunk_summary and not is_large_document
                        ),
                        document_id=document_id,
                    )
                    if not self._enable_llm_chunk_summary:
                        for chunk in chunks:
                            if not chunk.summary:
                                chunk.summary = fallback_chunker._extract_summary(
                                    chunk.content
                                )
                if is_large_document:
                    chunks = self._downsample_chunks(chunks, self._max_chunks_per_doc)
                return chunks, is_large_document

        chunk_results: List[tuple[List, bool]] = await asyncio.gather(
            *[
                chunk_one_document(file_path, document_id)
                for document_id, file_path in enumerate(files_to_parse)
            ]
        )

        chunks = []
        global_chunk_id = 0
        for document_chunks, _ in chunk_results:
            for chunk in document_chunks:
                chunks.append(chunk)

        # Always cap chunk count and total chars, not just for large docs.
        chunks = self._cap_total_chunks(chunks)
        chunks = self._enforce_total_char_budget(chunks)

        for chunk in chunks:
            chunk.id = global_chunk_id
            global_chunk_id += 1

        if chunks:
            source_chunks = [SourceChunk(**chunk.to_dict()) for chunk in chunks]
            chunks_for_prompt = self._select_prompt_chunks(chunks, query)
            summary_lines: List[str] = []
            total_summary_chars = 0
            for chunk in chunks:
                if not chunk.summary:
                    continue
                summary_line = f"- {chunk.summary}"
                if total_summary_chars + len(summary_line) > 2000:
                    summary_lines.append("...")
                    break
                summary_lines.append(summary_line)
                total_summary_chars += len(summary_line)
            if summary_lines:
                source_summary = "\n".join(summary_lines)
                if len(files_to_parse) < len(files):
                    source_summary = (
                        f"[Partial source coverage: parsed {len(files_to_parse)}/{len(files)} files due budget]\n"
                        + source_summary
                    )

        return additional_context, source_chunks, source_summary, chunks_for_prompt
