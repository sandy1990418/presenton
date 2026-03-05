"""
Document Chunker Service

Splits documents into semantic chunks for use in presentation generation.
Each chunk includes a summary and the original content, allowing slide
generation to reference only relevant chunks.
"""

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from models.llm_message import LLMSystemMessage, LLMUserMessage
from services.llm_client import LLMClient
from utils.llm_provider import get_model

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """A chunk of document content with metadata."""

    id: int
    title: str  # Short title/topic for this chunk
    summary: str  # Brief summary of the chunk content
    content: str  # Original content
    document_id: int = 0  # Source document index in multi-file uploads

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DocumentChunker:
    """
    Splits documents into semantic chunks.

    Chunking strategies:
    1. By headers/sections if document has structure
    2. By paragraph groups if no clear structure
    3. By token count with overlap for long documents
    """

    def __init__(
        self,
        max_chunk_size: int = 1500,  # Max characters per chunk
        min_chunk_size: int = 200,  # Min characters per chunk
        overlap: int = 100,  # Character overlap between chunks
    ):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap = overlap

    def _get_adaptive_chunk_size(self, text_length: int) -> int:
        """Scale chunk size by document length to avoid chunk explosion."""
        if text_length > 5_000_000:
            return 8000
        if text_length > 1_000_000:
            return 5000
        if text_length > 200_000:
            return 3000
        return self.max_chunk_size

    def _has_meaningful_text(self, text: str, sample_size: int = 256) -> bool:
        """Fast non-empty check without scanning/copying full large strings."""
        if not text:
            return False
        head = text[:sample_size]
        tail = text[-sample_size:] if len(text) > sample_size else ""
        return bool(head.strip() or tail.strip())

    async def chunk_documents(
        self,
        documents: str,
        generate_summaries: bool = True,
        llm_summary_char_threshold: int = 100_000,
        document_id: int = 0,
        merge_small_min_size: Optional[int] = None,
    ) -> List[DocumentChunk]:
        """
        Split documents into chunks.

        Args:
            documents: Raw document content
            generate_summaries: Whether to generate LLM summaries for chunks
            llm_summary_char_threshold: Skip LLM summaries when document is larger than
                this size and use extractive summaries instead.
            document_id: Source document index for multi-file uploads.
            merge_small_min_size: Merge tiny adjacent chunks below this size.

        Returns:
            List of DocumentChunk objects
        """
        if not self._has_meaningful_text(documents):
            return []

        adaptive_chunk_size = self._get_adaptive_chunk_size(len(documents))
        original_max_chunk_size = self.max_chunk_size
        self.max_chunk_size = adaptive_chunk_size

        # Try structured chunking first (by headers)
        try:
            chunks = self._chunk_by_headers(documents)

            # Fall back to paragraph-based chunking
            if not chunks or len(chunks) == 1:
                chunks = self._chunk_by_paragraphs(documents)
        finally:
            self.max_chunk_size = original_max_chunk_size

        merge_target = (
            merge_small_min_size
            if merge_small_min_size is not None
            else max(self.min_chunk_size, adaptive_chunk_size // 2)
        )
        chunks = self._merge_small_chunks(chunks, min_size=merge_target)

        # Create DocumentChunk objects
        result = []
        for i, (title, content) in enumerate(chunks):
            chunk = DocumentChunk(
                id=i,
                title=title,
                summary="",  # Will be filled if generate_summaries=True
                content=content.strip(),
                document_id=document_id,
            )
            result.append(chunk)

        # Generate summaries if requested
        if generate_summaries and result:
            if len(documents) > llm_summary_char_threshold:
                for chunk in result:
                    chunk.summary = self._extract_summary(chunk.content)
            else:
                result = await self._generate_chunk_summaries(result)

        return result

    def _chunk_by_headers(self, text: str) -> List[tuple]:
        """
        Split by markdown headers or common section patterns.
        Returns list of (title, content) tuples.
        """
        # Match markdown headers (# ## ### etc.)
        header_pattern = r"^(#{1,6})\s+(.+?)$"

        # Also match common patterns like "Section 1:" or "1. Title"
        section_pattern = r"^(?:Section\s+\d+[:.]\s*|(?:\d+\.)+\s+)(.+?)$"
        # Match CJK section titles like "第一章", "一、", "（一）"
        cjk_section_pattern = (
            r"^(?:第[一二三四五六七八九十百\d]+[章节節部分编篇]|"
            r"[一二三四五六七八九十百\d]+[、．.])\s*(.+?)$"
        )

        lines = text.split("\n")
        chunks = []
        current_title = "Introduction"
        current_content = []

        for line in lines:
            # Check for markdown header
            header_match = re.match(header_pattern, line, re.MULTILINE)
            section_match = re.match(
                section_pattern, line, re.MULTILINE | re.IGNORECASE
            )
            cjk_section_match = re.match(cjk_section_pattern, line, re.MULTILINE)

            if header_match or section_match or cjk_section_match:
                # Save previous chunk if it has content
                if current_content:
                    content = "\n".join(current_content).strip()
                    if len(content) >= self.min_chunk_size:
                        chunks.append((current_title, content))
                    elif chunks:
                        # Merge small chunk with previous
                        prev_title, prev_content = chunks[-1]
                        chunks[-1] = (prev_title, prev_content + "\n\n" + content)

                # Start new chunk
                if header_match:
                    current_title = header_match.group(2)
                elif section_match:
                    current_title = section_match.group(1)
                else:
                    current_title = cjk_section_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        # Don't forget the last chunk
        if current_content:
            content = "\n".join(current_content).strip()
            if len(content) >= self.min_chunk_size:
                chunks.append((current_title, content))
            elif chunks:
                prev_title, prev_content = chunks[-1]
                chunks[-1] = (prev_title, prev_content + "\n\n" + content)

        # If chunks are too large, split them further
        final_chunks = []
        for title, content in chunks:
            if len(content) > self.max_chunk_size * 2:
                # Split large chunks
                sub_chunks = self._split_large_chunk(title, content)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append((title, content))

        return final_chunks

    def _chunk_by_paragraphs(self, text: str) -> List[tuple]:
        """
        Fallback chunking by character window (Unicode-safe).
        This is faster and more robust for very large multilingual documents.
        """
        if not text:
            return []

        chunks = []
        chunk_index = 1
        step = max(1, self.max_chunk_size - self.overlap)

        for start in range(0, len(text), step):
            content = text[start : start + self.max_chunk_size]
            normalized = content.strip()
            if not normalized:
                continue
            if len(normalized) >= self.min_chunk_size:
                chunks.append((f"Section {chunk_index}", content))
                chunk_index += 1
            elif chunks:
                # Merge with previous
                prev_title, prev_content = chunks[-1]
                chunks[-1] = (prev_title, prev_content + "\n\n" + content)

        return chunks

    def _merge_small_chunks(self, chunks: List[tuple], min_size: int) -> List[tuple]:
        """Merge adjacent tiny chunks to improve slide-generation context quality."""
        if not chunks:
            return chunks

        merged: List[tuple] = []
        pending_title, pending_content = chunks[0]

        for title, content in chunks[1:]:
            if len(pending_content) < min_size:
                pending_content = f"{pending_content}\n\n{content}"
                continue
            merged.append((pending_title, pending_content))
            pending_title, pending_content = title, content

        if merged and len(pending_content) < min_size:
            prev_title, prev_content = merged[-1]
            merged[-1] = (prev_title, f"{prev_content}\n\n{pending_content}")
        else:
            merged.append((pending_title, pending_content))

        return merged

    def _split_large_chunk(self, title: str, content: str) -> List[tuple]:
        """Split a large chunk into smaller pieces."""
        chunks = []

        # Try to split by paragraphs first
        paragraphs = re.split(r"\n\s*\n", content)

        current_content = []
        current_length = 0
        part = 1

        for para in paragraphs:
            if current_length + len(para) > self.max_chunk_size and current_content:
                chunks.append((f"{title} (Part {part})", "\n\n".join(current_content)))
                part += 1
                current_content = []
                current_length = 0

            current_content.append(para)
            current_length += len(para)

        if current_content:
            chunk_title = f"{title} (Part {part})" if part > 1 else title
            chunks.append((chunk_title, "\n\n".join(current_content)))

        return chunks

    async def _generate_chunk_summaries(
        self,
        chunks: List[DocumentChunk],
        batch_size: int = 30,
    ) -> List[DocumentChunk]:
        """Generate summaries for chunks using LLM in batches.

        Chunks are processed in batches of *batch_size* to stay within
        context-window and output-token limits.  Each batch gets its own
        LLM call with ``max_tokens`` scaled to the batch size.
        """

        if len(chunks) <= 3:
            for chunk in chunks:
                chunk.summary = self._extract_summary(chunk.content)
            return chunks

        client = LLMClient()
        model = get_model()

        system_prompt = (
            "You are a document analyzer. For each chunk provided, "
            "generate a brief 1-2 sentence summary capturing the key "
            "information, data points, and facts.\n\n"
            "Output format - one line per chunk:\n"
            "CHUNK <id>: <summary>\n\n"
            "Be concise but capture the essential facts and data."
        )

        chunks_by_id: Dict[int, DocumentChunk] = {chunk.id: chunk for chunk in chunks}

        # Process chunks in batches
        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]

            chunks_text = ""
            for chunk in batch:
                preview = chunk.content[:500]
                if len(chunk.content) > 500:
                    preview += "..."
                chunks_text += f"\n[CHUNK {chunk.id}: {chunk.title}]\n{preview}\n"

            # Scale max_tokens to batch size (~40 tokens per summary)
            max_tokens = min(len(batch) * 40, 4096)

            try:
                response = await client.generate(
                    model=model,
                    messages=[
                        LLMSystemMessage(content=system_prompt),
                        LLMUserMessage(content=f"Summarize each chunk:\n{chunks_text}"),
                    ],
                    max_tokens=max_tokens,
                )

                if response:
                    for line in response.split("\n"):
                        match = re.match(
                            r"CHUNK\s*(\d+)\s*:\s*(.+)",
                            line,
                            re.IGNORECASE,
                        )
                        if match:
                            chunk_id = int(match.group(1))
                            summary = match.group(2).strip()
                            chunk = chunks_by_id.get(chunk_id)
                            if chunk is not None:
                                chunk.summary = summary

            except Exception:
                logger.exception("Failed to generate chunk summaries for batch")

        # Fill in any missing summaries with extractive fallback
        for chunk in chunks:
            if not chunk.summary:
                chunk.summary = self._extract_summary(chunk.content)

        return chunks

    def _extract_summary(self, text: str) -> str:
        """Extractive summary that supports both Latin and CJK punctuation."""
        match = re.match(r"^(.+?[.!?。！？])\s*", text.strip())
        if match:
            first_sentence = match.group(1)
            if len(text) < 500:
                return first_sentence
            tail = text[-60:].strip()
            return f"{first_sentence} ... {tail}"
        return text[:200].strip() + ("..." if len(text) > 200 else "")

    def _extract_first_sentence(self, text: str) -> str:
        """Backward-compatible wrapper."""
        return self._extract_summary(text)


def format_chunks_for_prompt(chunks: List[DocumentChunk]) -> str:
    """Format chunks for inclusion in a prompt."""
    result = "## Available Source Chunks\n\n"
    for chunk in chunks:
        result += f"[CHUNK {chunk.id}] {chunk.title}\n"
        result += f"Summary: {chunk.summary}\n\n"
    return result


def format_chunk_content_for_slide(
    chunks: List[dict],
    chunk_refs: List[int],
) -> str:
    """
    Format specific chunk contents for slide generation.

    Args:
        chunks: All available chunks (as dicts with 'id', 'title', 'content' keys)
        chunk_refs: List of chunk IDs to include

    Returns:
        Formatted string with referenced chunk contents
    """
    if not chunk_refs:
        return ""

    # Build an ID-based lookup so chunk_refs are matched by ID,
    # not by list position.
    def _get_id(chunk: Any) -> int:
        return chunk.get("id", -1) if isinstance(chunk, dict) else chunk.id

    chunks_by_id: Dict[int, Any] = {_get_id(c): c for c in chunks}

    result = "## Source Reference Context\n\n"
    result += "Use the following source content as authoritative reference:\n\n"

    for ref_id in chunk_refs:
        chunk = chunks_by_id.get(ref_id)
        if chunk is None:
            continue
        title = (
            chunk.get("title", f"Chunk {ref_id}")
            if isinstance(chunk, dict)
            else chunk.title
        )
        content = chunk.get("content", "") if isinstance(chunk, dict) else chunk.content
        result += f"### {title}\n"
        result += f"{content}\n\n"

    return result
