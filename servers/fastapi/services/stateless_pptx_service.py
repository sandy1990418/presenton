"""
Stateless PPTX Service for database-free presentation generation.

This service handles the complete flow of generating presentations
without relying on database storage.
"""

import asyncio
import math
import os
import random
import traceback
import uuid
from typing import Callable, List, Literal, Optional

import aiohttp
import dirtyjson
from fastapi import HTTPException
from pathvalidate import sanitize_filename

from constants.presentation import DEFAULT_TEMPLATES
from enums.tone import Tone
from enums.verbosity import Verbosity
from models.presentation_layout import PresentationLayoutModel
from models.presentation_outline_model import (
    PresentationOutlineModel,
    SlideOutlineModel,
)
from models.presentation_structure_model import PresentationStructureModel
from models.pptx_models import PptxPresentationModel
from models.stateless_models import (
    SourceChunk,
    StatelessGenerationContext,
    StatelessOutlineResponse,
)
from services.document_chunker import format_chunk_content_for_slide
from services.image_generation_service import ImageGenerationService
from services.pptx_presentation_creator import PptxPresentationCreator
from services.source_chunk_store import SOURCE_CHUNK_STORE
from services.source_context_service import SourceContextService
from services.temp_file_service import TEMP_FILE_SERVICE
from utils.context_budget import estimate_source_budget
from utils.get_layout_by_name import get_layout_by_name
from utils.llm_calls.generate_presentation_outlines import generate_ppt_outline
from utils.llm_calls.generate_presentation_structure import (
    generate_presentation_structure,
)
from utils.llm_calls.generate_slide_content import (
    get_slide_content_from_type_and_outline,
    get_system_prompt as get_slide_system_prompt,
    get_user_prompt as get_slide_user_prompt,
)
from utils.llm_provider import get_model
from utils.ppt_utils import (
    get_presentation_title_from_outlines,
    select_toc_or_list_slide_layout_index,
)
from utils.process_slides import process_slide_and_fetch_assets


class StatelessSlideData:
    """Container for slide data without database model."""

    def __init__(
        self,
        layout_group: str,
        layout: str,
        index: int,
        content: dict,
        speaker_note: Optional[str] = None,
    ):
        self.layout_group = layout_group
        self.layout = layout
        self.index = index
        self.content = content
        self.speaker_note = speaker_note


class StatelessPptxService:
    """Service for stateless PPTX generation."""

    _SOURCE_CONTEXT_CONFIG_KEYS = {
        "_source_chunk_concurrency",
        "_max_source_files",
        "_max_parse_files",
        "_max_parse_total_bytes",
        "_max_source_chars_per_doc",
        "_max_source_total_chars",
        "_max_chunks_per_doc",
        "_max_total_chunks",
        "_max_outline_prompt_chunks",
        "_max_chunk_refs_per_slide",
        "_large_file_bytes_threshold",
        "_large_doc_chars_threshold",
        "_enable_llm_chunk_summary",
    }

    def __init__(self, temp_dir: Optional[str] = None):
        """
        Initialize the service.

        Args:
            temp_dir: Optional temp directory. If not provided, one will be created.
        """
        self._temp_dir = temp_dir or TEMP_FILE_SERVICE.create_temp_dir()
        self._image_service = ImageGenerationService(self._temp_dir)
        self._source_context_service = SourceContextService()

    def __getattr__(self, name: str):
        if name in self._SOURCE_CONTEXT_CONFIG_KEYS:
            return getattr(self._source_context_service, name)
        raise AttributeError(f"{self.__class__.__name__!s} has no attribute {name!s}")

    def __setattr__(self, name: str, value):
        if (
            name in self._SOURCE_CONTEXT_CONFIG_KEYS
            and "_source_context_service" in self.__dict__
        ):
            setattr(self._source_context_service, name, value)
            return
        super().__setattr__(name, value)

    async def _prepare_source_context(
        self,
        files: Optional[List[str]],
        query: Optional[str] = None,
    ) -> tuple[str, Optional[List[SourceChunk]], Optional[str], Optional[List[dict]]]:
        return await self._source_context_service._prepare_source_context(files, query)

    def _remap_prompt_chunk_refs(
        self,
        outlines: PresentationOutlineModel,
        prompt_chunks: List[dict],
    ) -> None:
        self._source_context_service._remap_prompt_chunk_refs(outlines, prompt_chunks)

    def _assign_chunk_refs_to_outlines(
        self,
        outlines: PresentationOutlineModel,
        source_chunks: Optional[List[SourceChunk]],
        query: Optional[str],
    ) -> None:
        self._source_context_service._assign_chunk_refs_to_outlines(
            outlines, source_chunks, query
        )

    async def generate_outlines(
        self,
        content: str,
        n_slides: int,
        language: str,
        template: str = "general",
        files: Optional[List[str]] = None,
        tone: Tone = Tone.DEFAULT,
        verbosity: Verbosity = Verbosity.STANDARD,
        instructions: Optional[str] = None,
        include_table_of_contents: bool = False,
        include_title_slide: bool = True,
        web_search: bool = False,
    ) -> StatelessOutlineResponse:
        """
        Generate presentation outlines from content.

        Args:
            content: Main presentation topic/content
            n_slides: Target number of slides
            language: Output language
            template: Template name (passed through generation context)
            files: Optional file paths for additional context
            tone: Presentation tone
            verbosity: Content verbosity level
            instructions: Custom generation instructions
            include_table_of_contents: Whether to include TOC
            include_title_slide: Whether to include title slide
            web_search: Whether to use web search

        Returns:
            StatelessOutlineResponse with generated outlines
        """
        (
            additional_context,
            source_chunks,
            source_summary,
            chunks_for_prompt,
        ) = await self._prepare_source_context(files, query=content)

        # Calculate slides to generate (accounting for TOC)
        n_slides_to_generate = n_slides
        if include_table_of_contents:
            needed_toc_count = math.ceil(
                ((n_slides - 1) if include_title_slide else n_slides) / 10
            )
            n_slides_to_generate -= math.ceil((n_slides - needed_toc_count) / 10)

        # Generate outlines
        outlines_text = ""
        async for chunk in generate_ppt_outline(
            content,
            n_slides_to_generate,
            language,
            additional_context,
            tone.value,
            verbosity.value,
            instructions,
            include_title_slide,
            web_search,
            chunks=chunks_for_prompt,
        ):
            if isinstance(chunk, HTTPException):
                raise chunk
            outlines_text += chunk

        try:
            outlines_json = dict(dirtyjson.loads(outlines_text))
        except Exception:
            traceback.print_exc()
            raise HTTPException(
                status_code=400,
                detail="Failed to generate presentation outlines. Please try again.",
            )

        presentation_outlines = PresentationOutlineModel(**outlines_json)
        total_outlines = n_slides_to_generate

        if include_table_of_contents:
            n_toc_slides = n_slides - total_outlines
            outline_index = 1 if include_title_slide else 0
            for i in range(n_toc_slides):
                outlines_to = outline_index + 10
                if total_outlines == outlines_to:
                    outlines_to -= 1

                toc_outline = "Table of Contents\n\n"
                for outline in presentation_outlines.slides[outline_index:outlines_to]:
                    page_number = (
                        outline_index - i + n_toc_slides + 1
                        if include_title_slide
                        else outline_index - i + n_toc_slides
                    )
                    toc_outline += f"Slide page number: {page_number}\n Slide Content: {outline.content[:100]}\n\n"
                    outline_index += 1

                outline_index += 1

                presentation_outlines.slides.insert(
                    i + 1 if include_title_slide else i,
                    SlideOutlineModel(
                        content=toc_outline,
                    ),
                )

        # Prompt chunks use local IDs for schema validation; map them back.
        self._remap_prompt_chunk_refs(presentation_outlines, chunks_for_prompt or [])
        # Backfill empty/invalid refs to reduce [] responses.
        self._assign_chunk_refs_to_outlines(
            presentation_outlines,
            source_chunks,
            query=content,
        )
        title = get_presentation_title_from_outlines(presentation_outlines)

        # Store full chunks in MinIO; return lightweight metadata only.
        source_context_id: Optional[str] = None
        lightweight_chunks: Optional[List[SourceChunk]] = None
        if source_chunks:
            source_context_id = await SOURCE_CHUNK_STORE.store(source_chunks)
            lightweight_chunks = [c.without_content() for c in source_chunks]

        return StatelessOutlineResponse(
            title=title or "Untitled Presentation",
            outlines=presentation_outlines,
            generation_context=StatelessGenerationContext(
                language=language,
                tone=tone.value,
                verbosity=verbosity.value,
                instructions=instructions,
                include_table_of_contents=include_table_of_contents,
                include_title_slide=include_title_slide,
                n_slides=n_slides,
                template=template,
                source_summary=source_summary,
                source_context_id=source_context_id,
                source_chunks=lightweight_chunks,
            ),
        )

    async def generate_pptx_from_outlines(
        self,
        outlines: PresentationOutlineModel,
        template: str,
        language: str,
        tone: Tone = Tone.DEFAULT,
        verbosity: Verbosity = Verbosity.STANDARD,
        instructions: Optional[str] = None,
        title: Optional[str] = None,
        source_summary: Optional[str] = None,
        source_chunks: Optional[List[SourceChunk]] = None,
        source_context_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> str:
        """
        Generate PPTX file from outlines.

        Args:
            outlines: Presentation outlines
            template: Template name
            language: Output language
            tone: Presentation tone
            verbosity: Content verbosity
            instructions: Custom instructions
            title: Optional presentation title
            source_summary: Optional source document summary
            source_chunks: Optional source chunks for slide context
            progress_callback: Optional callback for progress updates

        Returns:
            Path to generated PPTX file
        """

        def report_progress(message: str, progress: float) -> None:
            if progress_callback:
                progress_callback(message, progress)

        report_progress("Loading template...", 0.05)

        # Validate template
        if template not in DEFAULT_TEMPLATES:
            template = template.lower()
            if not template.startswith("custom-"):
                raise HTTPException(
                    status_code=400,
                    detail="Template not found. Please use a valid template.",
                )

        # Get layout
        layout_model = await get_layout_by_name(template)
        total_slide_layouts = len(layout_model.slides)
        total_outlines = len(outlines.slides)

        report_progress("Generating slide structure...", 0.1)

        # Generate structure
        if layout_model.ordered:
            presentation_structure = layout_model.to_presentation_structure()
        else:
            presentation_structure = await generate_presentation_structure(
                outlines,
                layout_model,
                instructions,
            )

        toc_layout_index = select_toc_or_list_slide_layout_index(layout_model)
        if toc_layout_index != -1:
            for index, outline in enumerate(outlines.slides):
                if not outline.content:
                    continue
                if outline.content.strip().lower().startswith("table of contents"):
                    if index < len(presentation_structure.slides):
                        presentation_structure.slides[index] = toc_layout_index

        # Ensure structure matches outlines
        presentation_structure.slides = presentation_structure.slides[:total_outlines]
        for index in range(total_outlines):
            random_slide_index = random.randint(0, total_slide_layouts - 1)
            if index >= len(presentation_structure.slides):
                presentation_structure.slides.append(random_slide_index)
            elif presentation_structure.slides[index] >= total_slide_layouts:
                presentation_structure.slides[index] = random_slide_index

        report_progress("Generating slide content...", 0.2)

        # Generate slide content
        slides = await self._generate_slides(
            outlines,
            layout_model,
            presentation_structure,
            language,
            tone.value,
            verbosity.value,
            instructions,
            source_summary,
            source_chunks,
            source_context_id=source_context_id,
            progress_callback=lambda p: report_progress(
                "Generating slide content...", 0.2 + p * 0.4
            ),
        )

        report_progress("Fetching images and icons...", 0.6)

        # Fetch assets
        await self._fetch_assets_for_slides(
            slides,
            progress_callback=lambda p: report_progress(
                "Fetching images and icons...", 0.6 + p * 0.25
            ),
        )

        report_progress("Creating PPTX file...", 0.85)

        # Convert to PPTX format
        slides_data = self._convert_slides_to_simple_json(slides)

        # Get template path
        template_path = await self._get_template_path(template)

        # Create PPTX
        pptx_creator = PptxPresentationCreator.from_simple_json(
            slides_data,
            self._temp_dir,
            template_path,
        )
        await pptx_creator.create_ppt()

        # Save file
        sanitized_title = sanitize_filename(
            title or get_presentation_title_from_outlines(outlines) or str(uuid.uuid4())
        ).replace(" ", "_")
        pptx_path = os.path.join(self._temp_dir, f"{sanitized_title}.pptx")
        pptx_creator.save(pptx_path)

        report_progress("Complete!", 1.0)

        return pptx_path

    async def generate_pdf_from_slides(
        self,
        slides_data: List[dict],
        title: Optional[str] = None,
        template: str = "general",
    ) -> str:
        """
        Generate PDF from slide data via NextJS.

        Args:
            slides_data: List of slide content dictionaries
            title: Optional presentation title
            template: Template name

        Returns:
            Path to generated PDF file
        """
        sanitized_title = sanitize_filename(title or str(uuid.uuid4())).replace(
            " ", "_"
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:3000/api/export-slides-as-pdf",
                json={
                    "slides": slides_data,
                    "title": sanitized_title,
                    "template": template,
                },
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to export PDF: {error_text}",
                    )

                # The response should be the PDF file
                pdf_content = await response.read()
                pdf_path = os.path.join(self._temp_dir, f"{sanitized_title}.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(pdf_content)

                return pdf_path

    async def _generate_slides(
        self,
        outlines: PresentationOutlineModel,
        layout_model: PresentationLayoutModel,
        structure: PresentationStructureModel,
        language: str,
        tone: str,
        verbosity: str,
        instructions: Optional[str],
        source_summary: Optional[str] = None,
        source_chunks: Optional[List[SourceChunk]] = None,
        source_context_id: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[StatelessSlideData]:
        """Generate slide content from outlines."""
        slides: List[StatelessSlideData] = []
        total_slides = len(structure.slides)

        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(5)

        # Cache fetched chunks across slides to avoid re-fetching the same
        # chunk from MinIO when multiple slides reference it.
        _chunk_cache: dict[int, SourceChunk] = {}

        # Pre-compute parts that are identical across all slides so we
        # don't regenerate the same strings for every slide.
        _model = get_model()
        _sys_prompt = get_slide_system_prompt(
            tone, verbosity, instructions, source_context=None
        )

        async def build_source_context(outline, max_chars: int = 0) -> Optional[str]:
            chunk_refs = getattr(outline, "chunk_refs", None)
            if not chunk_refs:
                if source_summary:
                    return f"## Source Summary\n{source_summary}"
                return None

            # Fetch only referenced chunks from MinIO (with cache)
            if source_context_id:
                missing = [r for r in chunk_refs if r not in _chunk_cache]
                if missing:
                    fetched = await SOURCE_CHUNK_STORE.get_chunks_by_ids(
                        source_context_id, missing
                    )
                    for c in fetched:
                        _chunk_cache[c.id] = c
                cached = [_chunk_cache[r] for r in chunk_refs if r in _chunk_cache]
                if cached:
                    return format_chunk_content_for_slide(
                        cached, chunk_refs, max_chars=max_chars
                    )

            # Fallback: use inline chunks
            if source_chunks:
                return format_chunk_content_for_slide(
                    source_chunks, chunk_refs, max_chars=max_chars
                )

            if source_summary:
                return f"## Source Summary\n{source_summary}"
            return None

        async def generate_with_semaphore(
            slide_layout,
            outline,
        ):
            async with semaphore:
                # Compute dynamic context budget for source content
                schema_json = str(slide_layout.json_schema)
                usr_prompt = get_slide_user_prompt(
                    outline.content, language, source_context=None
                )
                budget = estimate_source_budget(
                    _model, [_sys_prompt, usr_prompt, schema_json]
                )

                source_context = await build_source_context(outline, max_chars=budget)
                return await get_slide_content_from_type_and_outline(
                    slide_layout,
                    outline,
                    language,
                    tone,
                    verbosity,
                    instructions,
                    source_context,
                )

        # Generate content concurrently in batches
        batch_size = 10
        for start in range(0, total_slides, batch_size):
            end = min(start + batch_size, total_slides)

            tasks = []
            for i in range(start, end):
                slide_layout_index = structure.slides[i]
                slide_layout = layout_model.slides[slide_layout_index]
                tasks.append(
                    generate_with_semaphore(
                        slide_layout,
                        outlines.slides[i],
                    )
                )

            batch_contents = await asyncio.gather(*tasks)

            for offset, content in enumerate(batch_contents):
                i = start + offset
                slide_layout_index = structure.slides[i]
                slide_layout = layout_model.slides[slide_layout_index]

                slides.append(
                    StatelessSlideData(
                        layout_group=layout_model.name,
                        layout=slide_layout.id,
                        index=i,
                        content=content,
                        speaker_note=content.get("__speaker_note__"),
                    )
                )

            if progress_callback:
                progress_callback(end / total_slides)

        return slides

    async def _fetch_assets_for_slides(
        self,
        slides: List[StatelessSlideData],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> None:
        """Fetch images and icons for slides."""
        total_slides = len(slides)
        for i, slide in enumerate(slides):
            slide.content, _ = await process_slide_and_fetch_assets(
                self._image_service, slide.content
            )
            if progress_callback:
                progress_callback((i + 1) / total_slides)

    def _convert_slides_to_simple_json(
        self,
        slides: List[StatelessSlideData],
    ) -> List[dict]:
        """Convert StatelessSlideData to simple JSON format for PPTX creator."""
        slides_data = []

        for slide in slides:
            slide_dict = {
                **slide.content,
                "__speaker_note__": slide.speaker_note,
            }

            # Map layout to layout_index if needed
            # The layout ID format is like "template_1", "template_2", etc.
            layout_id = slide.layout
            if layout_id.startswith("template_"):
                try:
                    layout_index = int(layout_id.replace("template_", ""))
                    slide_dict["layout_index"] = layout_index
                except ValueError:
                    slide_dict["layout_index"] = 1
            else:
                slide_dict["layout_index"] = 1

            slides_data.append(slide_dict)

        return slides_data

    async def _get_template_path(self, template: str) -> str:
        """Get the path to the template PPTX file."""
        # Standard templates are in a known location
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        templates_dir = os.path.join(base_path, "templates")

        template_file = os.path.join(templates_dir, f"{template}.pptx")
        if os.path.exists(template_file):
            return template_file

        # Fall back to default template
        default_template = os.path.join(templates_dir, "general.pptx")
        if os.path.exists(default_template):
            return default_template

        # If no template found, return empty string (PptxPresentationCreator will create blank)
        return ""

    async def generate_full_presentation(
        self,
        content: str,
        n_slides: int,
        language: str,
        template: str = "general",
        slides_markdown: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        tone: Tone = Tone.DEFAULT,
        verbosity: Verbosity = Verbosity.STANDARD,
        instructions: Optional[str] = None,
        include_table_of_contents: bool = False,
        include_title_slide: bool = True,
        web_search: bool = False,
        export_as: Literal["pptx", "pdf"] = "pptx",
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> str:
        """
        Generate a complete presentation file (one-step flow).

        Args:
            content: Main presentation topic/content
            n_slides: Target number of slides
            language: Output language
            template: Template name
            slides_markdown: Optional pre-defined markdown for slides
            files: Optional file paths for additional context
            tone: Presentation tone
            verbosity: Content verbosity
            instructions: Custom instructions
            include_table_of_contents: Whether to include TOC
            include_title_slide: Whether to include title slide
            web_search: Whether to use web search
            export_as: Export format (pptx or pdf)
            progress_callback: Optional callback for progress updates

        Returns:
            Path to generated file
        """

        def report_progress(message: str, progress: float) -> None:
            if progress_callback:
                progress_callback(message, progress)

        # If slides_markdown is provided, use it directly as outlines
        if slides_markdown:
            outlines = PresentationOutlineModel(
                slides=[SlideOutlineModel(content=md) for md in slides_markdown]
            )
            title = None
            source_summary = None
            source_chunks = None
            ctx_id = None
        else:
            report_progress("Generating outlines...", 0.0)
            outline_response = await self.generate_outlines(
                content=content,
                n_slides=n_slides,
                language=language,
                template=template,
                files=files,
                tone=tone,
                verbosity=verbosity,
                instructions=instructions,
                include_table_of_contents=include_table_of_contents,
                include_title_slide=include_title_slide,
                web_search=web_search,
            )
            outlines = outline_response.outlines
            title = outline_response.title
            source_summary = outline_response.generation_context.source_summary
            # For one-step flow, pass context_id so _generate_slides
            # fetches only the chunks each slide needs from MinIO.
            ctx_id = outline_response.generation_context.source_context_id
            source_chunks = outline_response.generation_context.source_chunks

        # Generate PPTX
        pptx_path = await self.generate_pptx_from_outlines(
            outlines=outlines,
            template=template,
            language=language,
            tone=tone,
            verbosity=verbosity,
            instructions=instructions,
            title=title,
            source_summary=source_summary,
            source_chunks=source_chunks,
            source_context_id=ctx_id,
            progress_callback=lambda msg, prog: report_progress(
                msg, 0.15 + prog * 0.85 if not slides_markdown else prog
            ),
        )

        if export_as == "pdf":
            # For PDF, we need to convert via NextJS
            # For now, return the PPTX path and note that PDF needs additional handling
            report_progress("PDF export requires NextJS integration...", 0.95)
            # TODO: Implement PDF export via NextJS
            # pdf_path = await self.generate_pdf_from_slides(...)
            # return pdf_path
            pass

        return pptx_path
