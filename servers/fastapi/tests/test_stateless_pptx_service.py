"""
Unit tests for stateless_pptx_service.py

Tests the StatelessPptxService that handles database-free presentation generation.
"""

import asyncio
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, Mock

from fastapi import HTTPException

from enums.tone import Tone
from enums.verbosity import Verbosity
from models.stateless_models import (
    SourceChunk,
    StatelessGenerationContext,
    StatelessOutlineResponse,
)
from models.presentation_outline_model import (
    PresentationOutlineModel,
    SlideOutlineModel,
)
from models.presentation_layout import PresentationLayoutModel, SlideLayoutModel
from models.presentation_structure_model import PresentationStructureModel
from services.document_chunker import DocumentChunk
from services.stateless_pptx_service import (
    StatelessSlideData,
    StatelessPptxService,
)


class TestStatelessSlideData:
    """Tests for StatelessSlideData class."""

    def test_initialization_with_required_fields(self):
        """Test initialization with required fields."""
        slide = StatelessSlideData(
            layout_group="general",
            layout="template_1",
            index=0,
            content={"title": "Test"},
        )

        assert slide.layout_group == "general"
        assert slide.layout == "template_1"
        assert slide.index == 0
        assert slide.content == {"title": "Test"}
        assert slide.speaker_note is None

    def test_initialization_with_speaker_note(self):
        """Test initialization with speaker note."""
        slide = StatelessSlideData(
            layout_group="modern",
            layout="template_2",
            index=1,
            content={"heading": "Introduction"},
            speaker_note="Welcome the audience",
        )

        assert slide.speaker_note == "Welcome the audience"

    def test_content_as_empty_dict(self):
        """Test slide with empty content dict."""
        slide = StatelessSlideData(
            layout_group="standard",
            layout="template_1",
            index=0,
            content={},
        )

        assert slide.content == {}


class TestStatelessPptxServiceInit:
    """Tests for StatelessPptxService initialization."""

    def test_initialization_with_default_temp_dir(self):
        """Test initialization creates temp directory."""
        with patch("services.stateless_pptx_service.TEMP_FILE_SERVICE") as mock_temp:
            mock_temp.create_temp_dir.return_value = "/tmp/test_dir"

            service = StatelessPptxService()

            assert service._temp_dir == "/tmp/test_dir"
            mock_temp.create_temp_dir.assert_called_once()

    def test_initialization_with_custom_temp_dir(self, tmp_path):
        """Test initialization with provided temp directory."""
        custom_dir = str(tmp_path / "custom")

        with patch("services.stateless_pptx_service.ImageGenerationService"):
            service = StatelessPptxService(temp_dir=custom_dir)

        assert service._temp_dir == custom_dir

    def test_image_service_initialization(self, tmp_path):
        """Test ImageGenerationService is initialized."""
        with patch(
            "services.stateless_pptx_service.ImageGenerationService"
        ) as mock_img_service:
            service = StatelessPptxService(temp_dir=str(tmp_path))

            mock_img_service.assert_called_once_with(str(tmp_path))


class TestStatelessPptxServicePrepareSourceContext:
    """Tests for _prepare_source_context method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a service instance for testing."""
        with patch("services.stateless_pptx_service.ImageGenerationService"):
            return StatelessPptxService(temp_dir=str(tmp_path))

    @pytest.mark.anyio
    async def test_prepare_source_context_no_files(self, service):
        """Test with no files provided."""
        result = await service._prepare_source_context(None)

        additional_context, source_chunks, source_summary, chunks_for_prompt = result
        assert additional_context == ""
        assert source_chunks is None
        assert source_summary is None
        assert chunks_for_prompt is None

    @pytest.mark.anyio
    async def test_prepare_source_context_empty_files(self, service):
        """Test with empty files list."""
        result = await service._prepare_source_context([])

        additional_context, source_chunks, source_summary, chunks_for_prompt = result
        assert additional_context == ""
        assert source_chunks is None

    @pytest.mark.anyio
    async def test_prepare_source_context_with_files(self, service):
        """Test with files containing content."""
        mock_chunk = MagicMock()
        mock_chunk.to_dict.return_value = {
            "id": 1,
            "title": "Test",
            "summary": "Test summary",
            "content": "Test content",
        }
        mock_chunk.summary = "Test summary"

        with patch(
            "services.stateless_pptx_service.DocumentsLoader"
        ) as mock_loader_class:
            mock_loader = AsyncMock()
            mock_loader.documents = ["Document 1 content", "Document 2 content"]
            mock_loader.load_documents = AsyncMock()
            mock_loader_class.return_value = mock_loader

            with patch(
                "services.stateless_pptx_service.DocumentChunker"
            ) as mock_chunker_class:
                mock_chunker = MagicMock()
                mock_chunker.chunk_documents = AsyncMock(return_value=[mock_chunk])
                mock_chunker_class.return_value = mock_chunker

                result = await service._prepare_source_context(["/path/to/file.pdf"])

        additional_context, source_chunks, source_summary, chunks_for_prompt = result

        assert additional_context == ""
        assert source_chunks is not None
        assert len(source_chunks) == 2
        assert source_summary is not None
        assert "Test summary" in source_summary

    @pytest.mark.anyio
    async def test_prepare_source_context_empty_documents(self, service):
        """Test with files that yield empty documents."""
        with patch(
            "services.stateless_pptx_service.DocumentsLoader"
        ) as mock_loader_class:
            mock_loader = AsyncMock()
            mock_loader.documents = ["", "  ", None]
            mock_loader.load_documents = AsyncMock()
            mock_loader_class.return_value = mock_loader

            result = await service._prepare_source_context(["/path/to/empty.pdf"])

        additional_context, source_chunks, source_summary, chunks_for_prompt = result
        assert additional_context == ""
        assert source_chunks is None

    @pytest.mark.anyio
    async def test_prepare_source_context_truncates_long_summary(self, service):
        """Test that very long summaries are truncated."""
        mock_chunk = MagicMock()
        long_summary = "x" * 3000
        mock_chunk.to_dict.return_value = {
            "id": 1,
            "title": "Test",
            "summary": long_summary,
            "content": "Content",
        }
        mock_chunk.summary = long_summary

        with patch(
            "services.stateless_pptx_service.DocumentsLoader"
        ) as mock_loader_class:
            mock_loader = AsyncMock()
            mock_loader.documents = ["Document content"]
            mock_loader.load_documents = AsyncMock()
            mock_loader_class.return_value = mock_loader

            with patch(
                "services.stateless_pptx_service.DocumentChunker"
            ) as mock_chunker_class:
                mock_chunker = MagicMock()
                mock_chunker.chunk_documents = AsyncMock(return_value=[mock_chunk])
                mock_chunker_class.return_value = mock_chunker

                result = await service._prepare_source_context(["/path/to/file.pdf"])

        _, _, source_summary, _ = result
        assert len(source_summary) <= 2000
        assert source_summary.endswith("...")

    @pytest.mark.anyio
    async def test_prepare_source_context_rejects_too_many_files(self, service):
        """Test file count hard limit validation."""
        service._max_source_files = 1

        with pytest.raises(HTTPException) as exc:
            await service._prepare_source_context(["/a.pdf", "/b.pdf"])

        assert exc.value.status_code == 400

    @pytest.mark.anyio
    async def test_prepare_source_context_rejects_oversize_total_bytes(
        self, service, tmp_path
    ):
        """Test total upload size hard limit validation."""
        oversized = tmp_path / "large.txt"
        oversized.write_text("abc")
        service._max_source_total_bytes = 2

        with pytest.raises(HTTPException) as exc:
            await service._prepare_source_context([str(oversized)])

        assert exc.value.status_code == 413

    @pytest.mark.anyio
    async def test_prepare_source_context_uses_extractive_summary_when_budget_exceeded(
        self, service
    ):
        """Test summary falls back to extractive mode for large contexts."""
        service._summary_llm_max_chars = 10
        chunk = DocumentChunk(
            id=0,
            title="Chunk",
            summary="",
            content="This is an extractive summary test. More details here.",
        )

        with patch(
            "services.stateless_pptx_service.DocumentsLoader"
        ) as mock_loader_class:
            mock_loader = AsyncMock()
            mock_loader.documents = ["x" * 100]
            mock_loader.load_documents = AsyncMock()
            mock_loader_class.return_value = mock_loader

            with patch(
                "services.stateless_pptx_service.DocumentChunker"
            ) as mock_chunker_class:
                mock_chunker = MagicMock()
                mock_chunker.chunk_documents = AsyncMock(return_value=[chunk])
                mock_chunker_class.return_value = mock_chunker

                (
                    _,
                    _,
                    source_summary,
                    chunks_for_prompt,
                ) = await service._prepare_source_context(["/path/to/file.pdf"])

        assert source_summary is not None
        assert "extractive summary test" in source_summary.lower()
        assert chunks_for_prompt is not None
        assert chunks_for_prompt[0]["summary"]

    @pytest.mark.anyio
    async def test_prepare_source_context_selects_relevant_prompt_chunks(self, service):
        """Test prompt chunks are relevance-ranked and capped."""
        service._max_outline_prompt_chunks = 2
        chunks = [
            DocumentChunk(
                id=0,
                title="Finance Baseline",
                summary="General financial overview",
                content="Revenue baseline and operating costs.",
            ),
            DocumentChunk(
                id=1,
                title="Marketing Campaign",
                summary="Brand and social content",
                content="Ad channels and brand activities.",
            ),
            DocumentChunk(
                id=2,
                title="Market Growth Outlook",
                summary="Market growth trends and CAGR",
                content="Strong market growth with expansion signals.",
            ),
        ]

        with patch(
            "services.stateless_pptx_service.DocumentsLoader"
        ) as mock_loader_class:
            mock_loader = AsyncMock()
            mock_loader.documents = ["source doc"]
            mock_loader.load_documents = AsyncMock()
            mock_loader_class.return_value = mock_loader

            with patch(
                "services.stateless_pptx_service.DocumentChunker"
            ) as mock_chunker_class:
                mock_chunker = MagicMock()
                mock_chunker.chunk_documents = AsyncMock(return_value=chunks)
                mock_chunker_class.return_value = mock_chunker

                (
                    _,
                    source_chunks,
                    _,
                    chunks_for_prompt,
                ) = await service._prepare_source_context(
                    ["/path/to/file.pdf"],
                    query="market growth strategy",
                )

        assert source_chunks is not None
        assert len(source_chunks) == 3
        assert chunks_for_prompt is not None
        assert len(chunks_for_prompt) == 2
        prompt_ids = {chunk["id"] for chunk in chunks_for_prompt}
        assert 2 in prompt_ids


class TestStatelessPptxServiceGenerateOutlines:
    """Tests for generate_outlines method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a service instance for testing."""
        with patch("services.stateless_pptx_service.ImageGenerationService"):
            return StatelessPptxService(temp_dir=str(tmp_path))

    @pytest.mark.anyio
    async def test_generate_outlines_success(self, service):
        """Test successful outline generation."""
        mock_outline_json = '{"slides": [{"content": "Intro"}, {"content": "Body"}]}'

        async def mock_generate(*args, **kwargs):
            yield mock_outline_json

        with patch.object(
            service, "_prepare_source_context", new_callable=AsyncMock
        ) as mock_prep:
            mock_prep.return_value = ("", None, None, None)

            with patch(
                "services.stateless_pptx_service.generate_ppt_outline", mock_generate
            ):
                with patch(
                    "services.stateless_pptx_service.get_presentation_title_from_outlines"
                ) as mock_title:
                    mock_title.return_value = "Test Presentation"

                    result = await service.generate_outlines(
                        content="Test topic",
                        n_slides=5,
                        language="English",
                    )

        assert isinstance(result, StatelessOutlineResponse)
        assert result.title == "Test Presentation"
        assert len(result.outlines.slides) == 2

    @pytest.mark.anyio
    async def test_generate_outlines_with_toc(self, service):
        """Test outline generation with table of contents."""
        mock_outline_json = '{"slides": [{"content": "Title"}, {"content": "Topic 1"}, {"content": "Topic 2"}]}'

        async def mock_generate(*args, **kwargs):
            yield mock_outline_json

        with patch.object(
            service, "_prepare_source_context", new_callable=AsyncMock
        ) as mock_prep:
            mock_prep.return_value = ("", None, None, None)

            with patch(
                "services.stateless_pptx_service.generate_ppt_outline", mock_generate
            ):
                with patch(
                    "services.stateless_pptx_service.get_presentation_title_from_outlines"
                ) as mock_title:
                    mock_title.return_value = "Test"

                    result = await service.generate_outlines(
                        content="Test topic",
                        n_slides=5,
                        language="English",
                        include_table_of_contents=True,
                        include_title_slide=True,
                    )

        assert isinstance(result, StatelessOutlineResponse)

    @pytest.mark.anyio
    async def test_generate_outlines_invalid_json(self, service):
        """Test outline generation with invalid JSON response."""

        async def mock_generate(*args, **kwargs):
            yield "invalid json {{"

        with patch.object(
            service, "_prepare_source_context", new_callable=AsyncMock
        ) as mock_prep:
            mock_prep.return_value = ("", None, None, None)

            with patch(
                "services.stateless_pptx_service.generate_ppt_outline", mock_generate
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await service.generate_outlines(
                        content="Test topic",
                        n_slides=5,
                        language="English",
                    )

        assert exc_info.value.status_code == 400
        assert "Failed to generate presentation outlines" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_generate_outlines_http_exception_from_llm(self, service):
        """Test that HTTPException from LLM is propagated."""

        async def mock_generate(*args, **kwargs):
            yield HTTPException(status_code=429, detail="Rate limited")

        with patch.object(
            service, "_prepare_source_context", new_callable=AsyncMock
        ) as mock_prep:
            mock_prep.return_value = ("", None, None, None)

            with patch(
                "services.stateless_pptx_service.generate_ppt_outline", mock_generate
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await service.generate_outlines(
                        content="Test topic",
                        n_slides=5,
                        language="English",
                    )

        assert exc_info.value.status_code == 429

    @pytest.mark.anyio
    async def test_generate_outlines_context_includes_settings(self, service):
        """Test that generation context includes all settings."""
        mock_outline_json = '{"slides": [{"content": "Test"}]}'

        async def mock_generate(*args, **kwargs):
            yield mock_outline_json

        with patch.object(
            service, "_prepare_source_context", new_callable=AsyncMock
        ) as mock_prep:
            mock_prep.return_value = ("", None, "Summary", None)

            with patch(
                "services.stateless_pptx_service.generate_ppt_outline", mock_generate
            ):
                with patch(
                    "services.stateless_pptx_service.get_presentation_title_from_outlines"
                ) as mock_title:
                    mock_title.return_value = "Test"

                    result = await service.generate_outlines(
                        content="Test topic",
                        n_slides=10,
                        language="Japanese",
                        template="modern",
                        tone=Tone.PROFESSIONAL,
                        verbosity=Verbosity.CONCISE,
                        instructions="Be detailed",
                        include_table_of_contents=True,
                        include_title_slide=False,
                    )

        ctx = result.generation_context
        assert ctx.language == "Japanese"
        assert ctx.tone == "professional"
        assert ctx.verbosity == "concise"
        assert ctx.instructions == "Be detailed"
        assert ctx.include_table_of_contents is True
        assert ctx.include_title_slide is False
        assert ctx.n_slides == 10
        assert ctx.template == "modern"
        assert ctx.source_summary == "Summary"


class TestStatelessPptxServiceGeneratePptxFromOutlines:
    """Tests for generate_pptx_from_outlines method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a service instance for testing."""
        with patch("services.stateless_pptx_service.ImageGenerationService"):
            return StatelessPptxService(temp_dir=str(tmp_path))

    @pytest.fixture
    def sample_outlines(self):
        """Create sample outlines."""
        return PresentationOutlineModel(
            slides=[
                SlideOutlineModel(content="Introduction"),
                SlideOutlineModel(content="Main Content"),
                SlideOutlineModel(content="Conclusion"),
            ]
        )

    @pytest.fixture
    def mock_layout_model(self):
        """Create mock layout model."""
        slide_layout = SlideLayoutModel(
            id="template_1",
            name="Title and Content",
            json_schema={"title": "Title and Content"},
        )
        return PresentationLayoutModel(
            name="general",
            slides=[slide_layout, slide_layout, slide_layout],
            ordered=False,
        )

    @pytest.mark.anyio
    async def test_generate_pptx_invalid_template(self, service, sample_outlines):
        """Test that invalid template raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            await service.generate_pptx_from_outlines(
                outlines=sample_outlines,
                template="invalid-template",
                language="English",
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_generate_pptx_success(
        self, service, sample_outlines, mock_layout_model, tmp_path
    ):
        """Test successful PPTX generation."""
        mock_structure = PresentationStructureModel(slides=[0, 1, 2])

        with patch(
            "services.stateless_pptx_service.get_layout_by_name", new_callable=AsyncMock
        ) as mock_get_layout:
            mock_get_layout.return_value = mock_layout_model

            with patch(
                "services.stateless_pptx_service.generate_presentation_structure",
                new_callable=AsyncMock,
            ) as mock_gen_structure:
                mock_gen_structure.return_value = mock_structure

                with patch.object(
                    service, "_generate_slides", new_callable=AsyncMock
                ) as mock_gen_slides:
                    mock_slides = [
                        StatelessSlideData(
                            "general", "template_1", 0, {"title": "Intro"}
                        ),
                        StatelessSlideData(
                            "general", "template_1", 1, {"title": "Main"}
                        ),
                        StatelessSlideData(
                            "general", "template_1", 2, {"title": "End"}
                        ),
                    ]
                    mock_gen_slides.return_value = mock_slides

                    with patch.object(
                        service, "_fetch_assets_for_slides", new_callable=AsyncMock
                    ):
                        with patch.object(
                            service, "_get_template_path", new_callable=AsyncMock
                        ) as mock_get_path:
                            mock_get_path.return_value = ""

                            with patch(
                                "services.stateless_pptx_service.PptxPresentationCreator"
                            ) as mock_creator_class:
                                mock_creator = MagicMock()
                                mock_creator.create_ppt = AsyncMock()
                                mock_creator.save = MagicMock()
                                mock_creator_class.from_simple_json.return_value = (
                                    mock_creator
                                )

                                result = await service.generate_pptx_from_outlines(
                                    outlines=sample_outlines,
                                    template="general",
                                    language="English",
                                )

        assert result.endswith(".pptx")

    @pytest.mark.anyio
    async def test_generate_pptx_with_progress_callback(
        self, service, sample_outlines, mock_layout_model
    ):
        """Test that progress callback is called."""
        mock_structure = PresentationStructureModel(slides=[0, 1, 2])
        progress_calls = []

        def progress_callback(message, progress):
            progress_calls.append((message, progress))

        with patch(
            "services.stateless_pptx_service.get_layout_by_name", new_callable=AsyncMock
        ) as mock_get_layout:
            mock_get_layout.return_value = mock_layout_model

            with patch(
                "services.stateless_pptx_service.generate_presentation_structure",
                new_callable=AsyncMock,
            ) as mock_gen_structure:
                mock_gen_structure.return_value = mock_structure

                with patch.object(
                    service, "_generate_slides", new_callable=AsyncMock
                ) as mock_gen_slides:
                    mock_gen_slides.return_value = [
                        StatelessSlideData("general", "template_1", 0, {}),
                    ]

                    with patch.object(
                        service, "_fetch_assets_for_slides", new_callable=AsyncMock
                    ):
                        with patch.object(
                            service, "_get_template_path", new_callable=AsyncMock
                        ) as mock_get_path:
                            mock_get_path.return_value = ""

                            with patch(
                                "services.stateless_pptx_service.PptxPresentationCreator"
                            ) as mock_creator_class:
                                mock_creator = MagicMock()
                                mock_creator.create_ppt = AsyncMock()
                                mock_creator.save = MagicMock()
                                mock_creator_class.from_simple_json.return_value = (
                                    mock_creator
                                )

                                await service.generate_pptx_from_outlines(
                                    outlines=sample_outlines,
                                    template="general",
                                    language="English",
                                    progress_callback=progress_callback,
                                )

        assert len(progress_calls) > 0
        # Should include loading template, generating structure, etc.
        messages = [call[0] for call in progress_calls]
        assert any("Loading template" in msg for msg in messages)

    @pytest.mark.anyio
    async def test_generate_pptx_with_custom_template(
        self, service, sample_outlines, mock_layout_model
    ):
        """Test generation with custom template prefix."""
        mock_structure = PresentationStructureModel(slides=[0])

        with patch(
            "services.stateless_pptx_service.get_layout_by_name", new_callable=AsyncMock
        ) as mock_get_layout:
            mock_get_layout.return_value = mock_layout_model

            with patch(
                "services.stateless_pptx_service.generate_presentation_structure",
                new_callable=AsyncMock,
            ) as mock_gen_structure:
                mock_gen_structure.return_value = mock_structure

                with patch.object(
                    service, "_generate_slides", new_callable=AsyncMock
                ) as mock_gen_slides:
                    mock_gen_slides.return_value = [
                        StatelessSlideData("custom", "template_1", 0, {}),
                    ]

                    with patch.object(
                        service, "_fetch_assets_for_slides", new_callable=AsyncMock
                    ):
                        with patch.object(
                            service, "_get_template_path", new_callable=AsyncMock
                        ) as mock_get_path:
                            mock_get_path.return_value = ""

                            with patch(
                                "services.stateless_pptx_service.PptxPresentationCreator"
                            ) as mock_creator_class:
                                mock_creator = MagicMock()
                                mock_creator.create_ppt = AsyncMock()
                                mock_creator.save = MagicMock()
                                mock_creator_class.from_simple_json.return_value = (
                                    mock_creator
                                )

                                result = await service.generate_pptx_from_outlines(
                                    outlines=sample_outlines,
                                    template="custom-my-template",
                                    language="English",
                                )

        assert result.endswith(".pptx")


class TestStatelessPptxServiceGenerateSlides:
    """Tests for _generate_slides method."""

    @pytest.fixture(autouse=True)
    def mock_budget_deps(self):
        """Mock get_model and estimate_source_budget used by generate_with_semaphore."""
        with (
            patch("services.stateless_pptx_service.get_model", return_value="gpt-4.1"),
            patch(
                "services.stateless_pptx_service.estimate_source_budget",
                return_value=200_000,
            ),
        ):
            yield

    @pytest.fixture
    def service(self, tmp_path):
        """Create a service instance for testing."""
        with patch("services.stateless_pptx_service.ImageGenerationService"):
            return StatelessPptxService(temp_dir=str(tmp_path))

    @pytest.fixture
    def sample_outlines(self):
        """Create sample outlines."""
        return PresentationOutlineModel(
            slides=[
                SlideOutlineModel(content="Slide 1"),
                SlideOutlineModel(content="Slide 2"),
            ]
        )

    @pytest.fixture
    def mock_layout_model(self):
        """Create mock layout model."""
        slide_layout = SlideLayoutModel(
            id="template_1",
            name="Title and Content",
            json_schema={"title": "Title and Content"},
        )
        return PresentationLayoutModel(
            name="general",
            slides=[slide_layout],
        )

    @pytest.fixture
    def mock_structure(self):
        """Create mock structure."""
        return PresentationStructureModel(slides=[0, 0])

    @pytest.mark.anyio
    async def test_generate_slides_success(
        self, service, sample_outlines, mock_layout_model, mock_structure
    ):
        """Test successful slide generation."""
        with patch(
            "services.stateless_pptx_service.get_slide_content_from_type_and_outline",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = {"title": "Generated Title", "body": "Content"}

            slides = await service._generate_slides(
                outlines=sample_outlines,
                layout_model=mock_layout_model,
                structure=mock_structure,
                language="English",
                tone="default",
                verbosity="standard",
                instructions=None,
            )

        assert len(slides) == 2
        assert all(isinstance(s, StatelessSlideData) for s in slides)
        assert slides[0].content["title"] == "Generated Title"

    @pytest.mark.anyio
    async def test_generate_slides_with_source_context(
        self, service, sample_outlines, mock_layout_model, mock_structure
    ):
        """Test slide generation with source chunks context."""
        source_chunks = [
            SourceChunk(id=1, title="Ch1", summary="Sum1", content="Content1"),
            SourceChunk(id=2, title="Ch2", summary="Sum2", content="Content2"),
        ]

        # Add chunk_refs to outlines
        sample_outlines.slides[0].chunk_refs = [1]
        sample_outlines.slides[1].chunk_refs = [2]

        with patch(
            "services.stateless_pptx_service.get_slide_content_from_type_and_outline",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = {"title": "Test"}

            with patch(
                "services.stateless_pptx_service.format_chunk_content_for_slide"
            ) as mock_format:
                mock_format.return_value = "Formatted chunk content"

                slides = await service._generate_slides(
                    outlines=sample_outlines,
                    layout_model=mock_layout_model,
                    structure=mock_structure,
                    language="English",
                    tone="default",
                    verbosity="standard",
                    instructions=None,
                    source_chunks=source_chunks,
                )

        assert len(slides) == 2
        # format_chunk_content_for_slide should be called for slides with chunk_refs
        assert mock_format.call_count == 2

    @pytest.mark.anyio
    async def test_generate_slides_with_source_summary_fallback(
        self, service, sample_outlines, mock_layout_model, mock_structure
    ):
        """Test slide generation with source summary as fallback."""
        with patch(
            "services.stateless_pptx_service.get_slide_content_from_type_and_outline",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = {"title": "Test"}

            slides = await service._generate_slides(
                outlines=sample_outlines,
                layout_model=mock_layout_model,
                structure=mock_structure,
                language="English",
                tone="default",
                verbosity="standard",
                instructions=None,
                source_summary="Document summary content",
            )

        # Should pass source_summary to generate function
        call_args = mock_gen.call_args_list
        for call in call_args:
            # source_context should include summary
            source_ctx = (
                call[0][6] if len(call[0]) > 6 else call[1].get("source_context")
            )
            if source_ctx:
                assert "Document summary content" in source_ctx

    @pytest.mark.anyio
    async def test_generate_slides_extracts_speaker_note(
        self, service, sample_outlines, mock_layout_model, mock_structure
    ):
        """Test that speaker notes are extracted from content."""
        with patch(
            "services.stateless_pptx_service.get_slide_content_from_type_and_outline",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = {
                "title": "Test",
                "__speaker_note__": "Speaker notes here",
            }

            slides = await service._generate_slides(
                outlines=sample_outlines,
                layout_model=mock_layout_model,
                structure=mock_structure,
                language="English",
                tone="default",
                verbosity="standard",
                instructions=None,
            )

        assert slides[0].speaker_note == "Speaker notes here"

    @pytest.mark.anyio
    async def test_generate_slides_progress_callback(
        self, service, sample_outlines, mock_layout_model, mock_structure
    ):
        """Test progress callback is called during generation."""
        progress_values = []

        def callback(progress):
            progress_values.append(progress)

        with patch(
            "services.stateless_pptx_service.get_slide_content_from_type_and_outline",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = {"title": "Test"}

            await service._generate_slides(
                outlines=sample_outlines,
                layout_model=mock_layout_model,
                structure=mock_structure,
                language="English",
                tone="default",
                verbosity="standard",
                instructions=None,
                progress_callback=callback,
            )

        assert len(progress_values) > 0
        assert progress_values[-1] == 1.0  # Final progress should be 100%


class TestStatelessPptxServiceFetchAssets:
    """Tests for _fetch_assets_for_slides method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a service instance for testing."""
        with patch("services.stateless_pptx_service.ImageGenerationService"):
            return StatelessPptxService(temp_dir=str(tmp_path))

    @pytest.mark.anyio
    async def test_fetch_assets_for_slides(self, service):
        """Test fetching assets for slides."""
        slides = [
            StatelessSlideData("general", "template_1", 0, {"image_prompt": "sunset"}),
            StatelessSlideData(
                "general", "template_1", 1, {"image_prompt": "mountain"}
            ),
        ]

        with patch(
            "services.stateless_pptx_service.process_slide_and_fetch_assets",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = (
                {"image_prompt": "sunset", "image_url": "/img/1.jpg"},
                None,
            )

            await service._fetch_assets_for_slides(slides)

        assert mock_fetch.call_count == 2

    @pytest.mark.anyio
    async def test_fetch_assets_with_progress_callback(self, service):
        """Test progress callback during asset fetching."""
        slides = [
            StatelessSlideData("general", "template_1", 0, {}),
            StatelessSlideData("general", "template_1", 1, {}),
        ]

        progress_values = []

        def callback(progress):
            progress_values.append(progress)

        with patch(
            "services.stateless_pptx_service.process_slide_and_fetch_assets",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = ({}, None)

            await service._fetch_assets_for_slides(slides, progress_callback=callback)

        assert len(progress_values) == 2
        assert progress_values[0] == 0.5
        assert progress_values[1] == 1.0


class TestStatelessPptxServiceConvertSlidesToJson:
    """Tests for _convert_slides_to_simple_json method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a service instance for testing."""
        with patch("services.stateless_pptx_service.ImageGenerationService"):
            return StatelessPptxService(temp_dir=str(tmp_path))

    def test_convert_slides_with_template_layout(self, service):
        """Test conversion with template_N layout format."""
        slides = [
            StatelessSlideData("general", "template_1", 0, {"title": "Slide 1"}),
            StatelessSlideData("general", "template_2", 1, {"title": "Slide 2"}),
        ]

        result = service._convert_slides_to_simple_json(slides)

        assert len(result) == 2
        assert result[0]["layout_index"] == 1
        assert result[1]["layout_index"] == 2
        assert result[0]["title"] == "Slide 1"

    def test_convert_slides_with_speaker_note(self, service):
        """Test conversion preserves speaker notes."""
        slides = [
            StatelessSlideData(
                "general",
                "template_1",
                0,
                {"title": "Slide 1"},
                speaker_note="Notes here",
            ),
        ]

        result = service._convert_slides_to_simple_json(slides)

        assert result[0]["__speaker_note__"] == "Notes here"

    def test_convert_slides_invalid_layout_format(self, service):
        """Test conversion with non-standard layout format."""
        slides = [
            StatelessSlideData("general", "custom_layout", 0, {"title": "Test"}),
        ]

        result = service._convert_slides_to_simple_json(slides)

        assert result[0]["layout_index"] == 1  # Defaults to 1

    def test_convert_slides_invalid_layout_number(self, service):
        """Test conversion with invalid layout number."""
        slides = [
            StatelessSlideData("general", "template_abc", 0, {"title": "Test"}),
        ]

        result = service._convert_slides_to_simple_json(slides)

        assert result[0]["layout_index"] == 1  # Defaults to 1


class TestStatelessPptxServiceGetTemplatePath:
    """Tests for _get_template_path method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a service instance for testing."""
        with patch("services.stateless_pptx_service.ImageGenerationService"):
            return StatelessPptxService(temp_dir=str(tmp_path))

    @pytest.mark.anyio
    async def test_get_template_path_exists(self, service, tmp_path):
        """Test getting path for existing template."""
        # Create a mock templates directory structure
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_file = templates_dir / "general.pptx"
        template_file.write_text("mock pptx content")

        with patch("os.path.dirname") as mock_dirname:
            mock_dirname.return_value = str(tmp_path)

            result = await service._get_template_path("general")

        assert "general.pptx" in result

    @pytest.mark.anyio
    async def test_get_template_path_not_exists_fallback(self, service, tmp_path):
        """Test fallback to default template when specific template not found."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        default_file = templates_dir / "general.pptx"
        default_file.write_text("default content")

        with patch("os.path.dirname") as mock_dirname:
            mock_dirname.return_value = str(tmp_path)

            result = await service._get_template_path("nonexistent")

        assert "general.pptx" in result

    @pytest.mark.anyio
    async def test_get_template_path_no_templates(self, service, tmp_path):
        """Test when no templates exist."""
        with patch("os.path.dirname") as mock_dirname:
            mock_dirname.return_value = str(tmp_path)

            result = await service._get_template_path("general")

        assert result == ""


class TestStatelessPptxServiceGenerateFullPresentation:
    """Tests for generate_full_presentation method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a service instance for testing."""
        with patch("services.stateless_pptx_service.ImageGenerationService"):
            return StatelessPptxService(temp_dir=str(tmp_path))

    @pytest.mark.anyio
    async def test_generate_full_presentation_with_content(self, service):
        """Test full presentation generation with content."""
        mock_outline_response = StatelessOutlineResponse(
            title="Test Presentation",
            outlines=PresentationOutlineModel(
                slides=[SlideOutlineModel(content="Test")]
            ),
            generation_context=StatelessGenerationContext(),
        )

        with patch.object(
            service, "generate_outlines", new_callable=AsyncMock
        ) as mock_gen_outlines:
            mock_gen_outlines.return_value = mock_outline_response

            with patch.object(
                service, "generate_pptx_from_outlines", new_callable=AsyncMock
            ) as mock_gen_pptx:
                mock_gen_pptx.return_value = "/tmp/presentation.pptx"

                result = await service.generate_full_presentation(
                    content="Test topic",
                    n_slides=5,
                    language="English",
                )

        assert result == "/tmp/presentation.pptx"
        mock_gen_outlines.assert_called_once()
        mock_gen_pptx.assert_called_once()

    @pytest.mark.anyio
    async def test_generate_full_presentation_with_slides_markdown(self, service):
        """Test full presentation generation with pre-defined markdown."""
        with patch.object(
            service, "generate_pptx_from_outlines", new_callable=AsyncMock
        ) as mock_gen_pptx:
            mock_gen_pptx.return_value = "/tmp/presentation.pptx"

            result = await service.generate_full_presentation(
                content="",
                n_slides=3,
                language="English",
                slides_markdown=["# Slide 1", "# Slide 2", "# Slide 3"],
            )

        assert result == "/tmp/presentation.pptx"
        # generate_outlines should NOT be called when slides_markdown is provided
        call_kwargs = mock_gen_pptx.call_args[1]
        assert len(call_kwargs["outlines"].slides) == 3

    @pytest.mark.anyio
    async def test_generate_full_presentation_with_progress_callback(self, service):
        """Test progress callback is forwarded."""
        progress_calls = []

        def callback(message, progress):
            progress_calls.append((message, progress))

        mock_outline_response = StatelessOutlineResponse(
            title="Test",
            outlines=PresentationOutlineModel(
                slides=[SlideOutlineModel(content="Test")]
            ),
            generation_context=StatelessGenerationContext(),
        )

        with patch.object(
            service, "generate_outlines", new_callable=AsyncMock
        ) as mock_gen_outlines:
            mock_gen_outlines.return_value = mock_outline_response

            with patch.object(
                service, "generate_pptx_from_outlines", new_callable=AsyncMock
            ) as mock_gen_pptx:
                mock_gen_pptx.return_value = "/tmp/presentation.pptx"

                await service.generate_full_presentation(
                    content="Test",
                    n_slides=5,
                    language="English",
                    progress_callback=callback,
                )

        assert len(progress_calls) > 0
        assert any("Generating outlines" in call[0] for call in progress_calls)


class TestStatelessPptxServiceGeneratePdfFromSlides:
    """Tests for generate_pdf_from_slides method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a service instance for testing."""
        with patch("services.stateless_pptx_service.ImageGenerationService"):
            return StatelessPptxService(temp_dir=str(tmp_path))

    @pytest.mark.anyio
    async def test_generate_pdf_success(self, service, tmp_path):
        """Test successful PDF generation."""
        slides_data = [
            {"title": "Slide 1", "body": "Content 1"},
            {"title": "Slide 2", "body": "Content 2"},
        ]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"%PDF-1.4 mock content")

        with patch("aiohttp.ClientSession") as mock_session_class:
            post_context = AsyncMock()
            post_context.__aenter__.return_value = mock_response
            post_context.__aexit__.return_value = None

            session = MagicMock()
            session.post.return_value = post_context

            session_context = AsyncMock()
            session_context.__aenter__.return_value = session
            session_context.__aexit__.return_value = None
            mock_session_class.return_value = session_context

            result = await service.generate_pdf_from_slides(
                slides_data=slides_data,
                title="Test Presentation",
                template="general",
            )

        assert result.endswith(".pdf")
        assert "Test_Presentation" in result

    @pytest.mark.anyio
    async def test_generate_pdf_api_error(self, service):
        """Test PDF generation when API returns error."""
        slides_data = [{"title": "Test"}]

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        with patch("aiohttp.ClientSession") as mock_session_class:
            post_context = AsyncMock()
            post_context.__aenter__.return_value = mock_response
            post_context.__aexit__.return_value = None

            session = MagicMock()
            session.post.return_value = post_context

            session_context = AsyncMock()
            session_context.__aenter__.return_value = session
            session_context.__aexit__.return_value = None
            mock_session_class.return_value = session_context

            with pytest.raises(HTTPException) as exc_info:
                await service.generate_pdf_from_slides(
                    slides_data=slides_data,
                    title="Test",
                )

        assert exc_info.value.status_code == 500
        assert "Failed to export PDF" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_generate_pdf_sanitizes_title(self, service, tmp_path):
        """Test that filename is sanitized."""
        slides_data = [{"title": "Test"}]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"%PDF content")

        with patch("aiohttp.ClientSession") as mock_session_class:
            post_context = AsyncMock()
            post_context.__aenter__.return_value = mock_response
            post_context.__aexit__.return_value = None

            session = MagicMock()
            session.post.return_value = post_context

            session_context = AsyncMock()
            session_context.__aenter__.return_value = session
            session_context.__aexit__.return_value = None
            mock_session_class.return_value = session_context

            result = await service.generate_pdf_from_slides(
                slides_data=slides_data,
                title="Test/With:Special*Characters",
            )

        # Should sanitize and not contain special characters
        assert "/" not in os.path.basename(result)
        assert ":" not in os.path.basename(result)
        assert "*" not in os.path.basename(result)
