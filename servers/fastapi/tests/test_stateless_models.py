"""
Unit tests for stateless_models.py

Tests all data classes, Pydantic models, and their methods used in
stateless presentation generation.
"""

import pytest
from unittest.mock import Mock

from enums.tone import Tone
from enums.verbosity import Verbosity
from models.stateless_models import (
    ImageAssetData,
    SlideData,
    SourceChunk,
    StatelessGenerationContext,
    StatelessOutlineRequest,
    StatelessOutlineResponse,
    StatelessGenerateRequest,
    StatelessGenerateFromOutlineRequest,
    SSEProgressMessage,
    SSECompleteMessage,
    SSEErrorMessage,
)
from models.presentation_outline_model import PresentationOutlineModel, SlideOutlineModel


class TestImageAssetData:
    """Tests for ImageAssetData dataclass."""

    def test_initialization_with_required_fields(self):
        """Test initialization with only required fields."""
        asset = ImageAssetData(path="/path/to/image.jpg")
        assert asset.path == "/path/to/image.jpg"
        assert asset.is_uploaded is False
        assert asset.extras is None

    def test_initialization_with_all_fields(self):
        """Test initialization with all fields."""
        extras = {"prompt": "test prompt", "theme": "professional"}
        asset = ImageAssetData(
            path="/path/to/image.jpg",
            is_uploaded=True,
            extras=extras,
        )
        assert asset.path == "/path/to/image.jpg"
        assert asset.is_uploaded is True
        assert asset.extras == extras

    def test_to_dict_method(self):
        """Test to_dict serialization method."""
        extras = {"prompt": "sunset", "theme": "modern"}
        asset = ImageAssetData(
            path="/images/test.png",
            is_uploaded=True,
            extras=extras,
        )
        result = asset.to_dict()

        assert isinstance(result, dict)
        assert result["path"] == "/images/test.png"
        assert result["is_uploaded"] is True
        assert result["extras"] == extras

    def test_to_dict_with_defaults(self):
        """Test to_dict with default values."""
        asset = ImageAssetData(path="/images/default.jpg")
        result = asset.to_dict()

        assert result["path"] == "/images/default.jpg"
        assert result["is_uploaded"] is False
        assert result["extras"] is None


class TestSlideData:
    """Tests for SlideData dataclass."""

    def test_initialization_with_defaults(self):
        """Test initialization with default values."""
        slide = SlideData()
        assert slide.content == {}
        assert slide.layout_group == ""
        assert slide.layout == ""
        assert slide.index == 0
        assert slide.speaker_note is None

    def test_initialization_with_all_fields(self):
        """Test initialization with all fields."""
        content = {"title": "Test Slide", "body": "Content here"}
        slide = SlideData(
            content=content,
            layout_group="modern",
            layout="template_1",
            index=5,
            speaker_note="Speaker notes here",
        )
        assert slide.content == content
        assert slide.layout_group == "modern"
        assert slide.layout == "template_1"
        assert slide.index == 5
        assert slide.speaker_note == "Speaker notes here"

    def test_to_dict_method(self):
        """Test to_dict serialization method."""
        content = {"heading": "Introduction"}
        slide = SlideData(
            content=content,
            layout_group="general",
            layout="template_2",
            index=1,
            speaker_note="Welcome everyone",
        )
        result = slide.to_dict()

        assert isinstance(result, dict)
        assert result["content"] == content
        assert result["layout_group"] == "general"
        assert result["layout"] == "template_2"
        assert result["index"] == 1
        assert result["speaker_note"] == "Welcome everyone"

    def test_to_dict_with_defaults(self):
        """Test to_dict with default values."""
        slide = SlideData()
        result = slide.to_dict()

        assert result["content"] == {}
        assert result["layout_group"] == ""
        assert result["layout"] == ""
        assert result["index"] == 0
        assert result["speaker_note"] is None


class TestSourceChunk:
    """Tests for SourceChunk Pydantic model."""

    def test_initialization(self):
        """Test SourceChunk initialization."""
        chunk = SourceChunk(
            id=1,
            title="Introduction",
            summary="This section covers the basics",
            content="Full content of the introduction section...",
        )
        assert chunk.id == 1
        assert chunk.title == "Introduction"
        assert chunk.summary == "This section covers the basics"
        assert chunk.content == "Full content of the introduction section..."

    def test_model_dump(self):
        """Test Pydantic model_dump method."""
        chunk = SourceChunk(
            id=2,
            title="Methods",
            summary="Research methodology",
            content="Detailed methods description",
        )
        result = chunk.model_dump()

        assert result["id"] == 2
        assert result["title"] == "Methods"
        assert result["summary"] == "Research methodology"
        assert result["content"] == "Detailed methods description"

    def test_model_json_serialization(self):
        """Test JSON serialization."""
        chunk = SourceChunk(
            id=3,
            title="Results",
            summary="Key findings",
            content="Results content here",
        )
        json_str = chunk.model_dump_json()

        assert '"id":3' in json_str or '"id": 3' in json_str
        assert '"title":"Results"' in json_str or '"title": "Results"' in json_str


class TestStatelessGenerationContext:
    """Tests for StatelessGenerationContext model."""

    def test_default_values(self):
        """Test default values initialization."""
        context = StatelessGenerationContext()

        assert context.language == "English"
        assert context.tone == "default"
        assert context.verbosity == "standard"
        assert context.instructions is None
        assert context.include_table_of_contents is False
        assert context.include_title_slide is True
        assert context.n_slides == 8
        assert context.template == "general"
        assert context.source_chunks is None
        assert context.source_summary is None

    def test_custom_values(self):
        """Test custom values initialization."""
        chunks = [
            SourceChunk(id=1, title="Test", summary="Summary", content="Content")
        ]
        context = StatelessGenerationContext(
            language="Chinese",
            tone="professional",
            verbosity="concise",
            instructions="Custom instructions here",
            include_table_of_contents=True,
            include_title_slide=False,
            n_slides=15,
            template="modern",
            source_chunks=chunks,
            source_summary="Document summary",
        )

        assert context.language == "Chinese"
        assert context.tone == "professional"
        assert context.verbosity == "concise"
        assert context.instructions == "Custom instructions here"
        assert context.include_table_of_contents is True
        assert context.include_title_slide is False
        assert context.n_slides == 15
        assert context.template == "modern"
        assert len(context.source_chunks) == 1
        assert context.source_summary == "Document summary"

    def test_model_dump(self):
        """Test model_dump serialization."""
        context = StatelessGenerationContext(
            language="Japanese",
            tone="casual",
        )
        result = context.model_dump()

        assert result["language"] == "Japanese"
        assert result["tone"] == "casual"
        assert result["verbosity"] == "standard"


class TestStatelessOutlineRequest:
    """Tests for StatelessOutlineRequest model."""

    def test_required_content_field(self):
        """Test that content is required."""
        request = StatelessOutlineRequest(content="AI in Healthcare")
        assert request.content == "AI in Healthcare"

    def test_default_values(self):
        """Test default values."""
        request = StatelessOutlineRequest(content="Test topic")

        assert request.n_slides == 8
        assert request.language == "English"
        assert request.template == "general"
        assert request.tone == Tone.DEFAULT
        assert request.verbosity == Verbosity.STANDARD
        assert request.instructions is None
        assert request.include_table_of_contents is False
        assert request.include_title_slide is True
        assert request.web_search is False
        assert request.files is None

    def test_custom_values(self):
        """Test custom values."""
        request = StatelessOutlineRequest(
            content="Machine Learning",
            files=["/path/to/file1.pdf", "/path/to/file2.txt"],
            n_slides=12,
            language="Spanish",
            template="modern",
            tone=Tone.PROFESSIONAL,
            verbosity=Verbosity.TEXT_HEAVY,
            instructions="Focus on practical examples",
            include_table_of_contents=True,
            include_title_slide=False,
            web_search=True,
        )

        assert request.content == "Machine Learning"
        assert len(request.files) == 2
        assert request.n_slides == 12
        assert request.language == "Spanish"
        assert request.template == "modern"
        assert request.tone == Tone.PROFESSIONAL
        assert request.verbosity == Verbosity.TEXT_HEAVY
        assert request.instructions == "Focus on practical examples"
        assert request.include_table_of_contents is True
        assert request.include_title_slide is False
        assert request.web_search is True

    def test_n_slides_validation_min(self):
        """Test n_slides minimum validation."""
        with pytest.raises(ValueError):
            StatelessOutlineRequest(content="Test", n_slides=0)

    def test_n_slides_validation_max(self):
        """Test n_slides maximum validation."""
        with pytest.raises(ValueError):
            StatelessOutlineRequest(content="Test", n_slides=51)

    def test_n_slides_boundary_values(self):
        """Test n_slides boundary values."""
        request_min = StatelessOutlineRequest(content="Test", n_slides=1)
        assert request_min.n_slides == 1

        request_max = StatelessOutlineRequest(content="Test", n_slides=50)
        assert request_max.n_slides == 50


class TestStatelessOutlineResponse:
    """Tests for StatelessOutlineResponse model."""

    def test_initialization(self):
        """Test response initialization."""
        outlines = PresentationOutlineModel(
            slides=[SlideOutlineModel(content="Slide 1 content")]
        )
        context = StatelessGenerationContext(language="English")

        response = StatelessOutlineResponse(
            title="My Presentation",
            outlines=outlines,
            generation_context=context,
        )

        assert response.title == "My Presentation"
        assert len(response.outlines.slides) == 1
        assert response.generation_context.language == "English"

    def test_model_dump(self):
        """Test model_dump serialization."""
        outlines = PresentationOutlineModel(
            slides=[
                SlideOutlineModel(content="Introduction"),
                SlideOutlineModel(content="Body"),
            ]
        )
        context = StatelessGenerationContext(tone="professional")

        response = StatelessOutlineResponse(
            title="Tech Talk",
            outlines=outlines,
            generation_context=context,
        )
        result = response.model_dump()

        assert result["title"] == "Tech Talk"
        assert len(result["outlines"]["slides"]) == 2
        assert result["generation_context"]["tone"] == "professional"


class TestStatelessGenerateRequest:
    """Tests for StatelessGenerateRequest model."""

    def test_default_values(self):
        """Test default values."""
        request = StatelessGenerateRequest()

        assert request.content == ""
        assert request.slides_markdown is None
        assert request.files is None
        assert request.n_slides == 8
        assert request.language == "English"
        assert request.template == "general"
        assert request.tone == Tone.DEFAULT
        assert request.verbosity == Verbosity.STANDARD
        assert request.instructions is None
        assert request.include_table_of_contents is False
        assert request.include_title_slide is True
        assert request.web_search is False
        assert request.export_as == "pptx"

    def test_with_content(self):
        """Test with content provided."""
        request = StatelessGenerateRequest(content="Quantum Computing")
        assert request.content == "Quantum Computing"

    def test_with_slides_markdown(self):
        """Test with pre-defined markdown slides."""
        markdown_slides = [
            "# Slide 1\nIntroduction",
            "# Slide 2\nDetails",
        ]
        request = StatelessGenerateRequest(slides_markdown=markdown_slides)
        assert request.slides_markdown == markdown_slides

    def test_export_as_pdf(self):
        """Test PDF export option."""
        request = StatelessGenerateRequest(
            content="Test",
            export_as="pdf",
        )
        assert request.export_as == "pdf"

    def test_export_as_pptx(self):
        """Test PPTX export option (default)."""
        request = StatelessGenerateRequest(content="Test")
        assert request.export_as == "pptx"

    def test_n_slides_validation(self):
        """Test n_slides validation."""
        # Valid range
        request = StatelessGenerateRequest(content="Test", n_slides=25)
        assert request.n_slides == 25

        # Invalid: below minimum
        with pytest.raises(ValueError):
            StatelessGenerateRequest(content="Test", n_slides=0)

        # Invalid: above maximum
        with pytest.raises(ValueError):
            StatelessGenerateRequest(content="Test", n_slides=100)


class TestStatelessGenerateFromOutlineRequest:
    """Tests for StatelessGenerateFromOutlineRequest model."""

    @pytest.fixture
    def sample_outlines(self):
        """Create sample outlines for testing."""
        return PresentationOutlineModel(
            slides=[
                SlideOutlineModel(content="Introduction"),
                SlideOutlineModel(content="Main Content"),
                SlideOutlineModel(content="Conclusion"),
            ]
        )

    @pytest.fixture
    def sample_context(self):
        """Create sample generation context."""
        return StatelessGenerationContext(
            language="Japanese",
            tone="professional",
            verbosity="concise",
            instructions="Be detailed",
            template="modern",
            source_summary="Summary of source docs",
            source_chunks=[
                SourceChunk(id=1, title="Ch1", summary="Sum1", content="Cont1")
            ],
        )

    def test_minimal_initialization(self, sample_outlines):
        """Test minimal initialization with only required fields."""
        request = StatelessGenerateFromOutlineRequest(outlines=sample_outlines)

        assert len(request.outlines.slides) == 3
        assert request.title is None
        assert request.generation_context is None
        assert request.template == "general"
        assert request.export_as == "pptx"

    def test_full_initialization(self, sample_outlines, sample_context):
        """Test full initialization with all fields."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            title="My Presentation",
            generation_context=sample_context,
            template="swift",
            export_as="pdf",
            language="Korean",
            tone=Tone.CASUAL,
            verbosity=Verbosity.TEXT_HEAVY,
            instructions="Fallback instructions",
        )

        assert request.title == "My Presentation"
        assert request.generation_context is not None
        assert request.template == "swift"
        assert request.export_as == "pdf"

    def test_get_language_with_context(self, sample_outlines, sample_context):
        """Test get_language returns context value when present."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            generation_context=sample_context,
            language="Fallback",
        )
        assert request.get_language() == "Japanese"

    def test_get_language_without_context(self, sample_outlines):
        """Test get_language returns fallback when no context."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            language="German",
        )
        assert request.get_language() == "German"

    def test_get_tone_with_context(self, sample_outlines, sample_context):
        """Test get_tone returns context value when present."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            generation_context=sample_context,
            tone=Tone.FUNNY,
        )
        assert request.get_tone() == Tone.PROFESSIONAL

    def test_get_tone_without_context(self, sample_outlines):
        """Test get_tone returns fallback when no context."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            tone=Tone.EDUCATIONAL,
        )
        assert request.get_tone() == Tone.EDUCATIONAL

    def test_get_tone_invalid_context_value(self, sample_outlines):
        """Test get_tone returns DEFAULT for invalid context value."""
        context = StatelessGenerationContext(tone="invalid_tone")
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            generation_context=context,
        )
        assert request.get_tone() == Tone.DEFAULT

    def test_get_verbosity_with_context(self, sample_outlines, sample_context):
        """Test get_verbosity returns context value when present."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            generation_context=sample_context,
            verbosity=Verbosity.TEXT_HEAVY,
        )
        assert request.get_verbosity() == Verbosity.CONCISE

    def test_get_verbosity_without_context(self, sample_outlines):
        """Test get_verbosity returns fallback when no context."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            verbosity=Verbosity.TEXT_HEAVY,
        )
        assert request.get_verbosity() == Verbosity.TEXT_HEAVY

    def test_get_verbosity_invalid_context_value(self, sample_outlines):
        """Test get_verbosity returns STANDARD for invalid context value."""
        context = StatelessGenerationContext(verbosity="invalid")
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            generation_context=context,
        )
        assert request.get_verbosity() == Verbosity.STANDARD

    def test_get_instructions_with_context(self, sample_outlines, sample_context):
        """Test get_instructions returns context value when present."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            generation_context=sample_context,
            instructions="Fallback instructions",
        )
        assert request.get_instructions() == "Be detailed"

    def test_get_instructions_without_context(self, sample_outlines):
        """Test get_instructions returns fallback when no context."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            instructions="Direct instructions",
        )
        assert request.get_instructions() == "Direct instructions"

    def test_get_instructions_none(self, sample_outlines):
        """Test get_instructions returns None when not set."""
        request = StatelessGenerateFromOutlineRequest(outlines=sample_outlines)
        assert request.get_instructions() is None

    def test_get_template_with_context(self, sample_outlines, sample_context):
        """Test get_template returns context value when present."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            generation_context=sample_context,
            template="swift",
        )
        assert request.get_template() == "modern"

    def test_get_template_without_context(self, sample_outlines):
        """Test get_template returns fallback when no context."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            template="swift",
        )
        assert request.get_template() == "swift"

    def test_get_source_summary_with_context(self, sample_outlines, sample_context):
        """Test get_source_summary returns context value."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            generation_context=sample_context,
        )
        assert request.get_source_summary() == "Summary of source docs"

    def test_get_source_summary_without_context(self, sample_outlines):
        """Test get_source_summary returns None when no context."""
        request = StatelessGenerateFromOutlineRequest(outlines=sample_outlines)
        assert request.get_source_summary() is None

    def test_get_source_chunks_with_context(self, sample_outlines, sample_context):
        """Test get_source_chunks returns context value."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=sample_outlines,
            generation_context=sample_context,
        )
        chunks = request.get_source_chunks()
        assert chunks is not None
        assert len(chunks) == 1
        assert chunks[0].id == 1

    def test_get_source_chunks_without_context(self, sample_outlines):
        """Test get_source_chunks returns None when no context."""
        request = StatelessGenerateFromOutlineRequest(outlines=sample_outlines)
        assert request.get_source_chunks() is None


class TestSSEProgressMessage:
    """Tests for SSEProgressMessage model."""

    def test_initialization(self):
        """Test SSEProgressMessage initialization."""
        msg = SSEProgressMessage(
            message="Generating slides...",
            progress=0.5,
        )
        assert msg.type == "progress"
        assert msg.message == "Generating slides..."
        assert msg.progress == 0.5

    def test_progress_validation_min(self):
        """Test progress minimum validation."""
        msg = SSEProgressMessage(message="Test", progress=0)
        assert msg.progress == 0

    def test_progress_validation_max(self):
        """Test progress maximum validation."""
        msg = SSEProgressMessage(message="Test", progress=1)
        assert msg.progress == 1

    def test_progress_validation_out_of_range_min(self):
        """Test progress below minimum raises error."""
        with pytest.raises(ValueError):
            SSEProgressMessage(message="Test", progress=-0.1)

    def test_progress_validation_out_of_range_max(self):
        """Test progress above maximum raises error."""
        with pytest.raises(ValueError):
            SSEProgressMessage(message="Test", progress=1.1)

    def test_model_dump_json(self):
        """Test JSON serialization for SSE."""
        msg = SSEProgressMessage(
            message="Processing...",
            progress=0.75,
        )
        json_str = msg.model_dump_json()

        assert '"type":"progress"' in json_str or '"type": "progress"' in json_str
        assert "Processing..." in json_str
        assert "0.75" in json_str


class TestSSECompleteMessage:
    """Tests for SSECompleteMessage model."""

    def test_initialization(self):
        """Test SSECompleteMessage initialization."""
        msg = SSECompleteMessage(
            download_url="/api/v2/ppt/stateless/download/abc123",
        )
        assert msg.type == "complete"
        assert msg.download_url == "/api/v2/ppt/stateless/download/abc123"

    def test_model_dump_json(self):
        """Test JSON serialization for SSE."""
        msg = SSECompleteMessage(
            download_url="/api/v2/ppt/stateless/download/task-id-here",
        )
        json_str = msg.model_dump_json()

        assert '"type":"complete"' in json_str or '"type": "complete"' in json_str
        assert "task-id-here" in json_str


class TestSSEErrorMessage:
    """Tests for SSEErrorMessage model."""

    def test_initialization(self):
        """Test SSEErrorMessage initialization."""
        msg = SSEErrorMessage(detail="Something went wrong")
        assert msg.type == "error"
        assert msg.detail == "Something went wrong"

    def test_model_dump_json(self):
        """Test JSON serialization for SSE."""
        msg = SSEErrorMessage(detail="Generation failed: timeout")
        json_str = msg.model_dump_json()

        assert '"type":"error"' in json_str or '"type": "error"' in json_str
        assert "Generation failed: timeout" in json_str
