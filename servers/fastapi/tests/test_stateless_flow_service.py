"""
Unit tests for stateless_flow_service.py

Tests the StatelessFlowService that handles validation and orchestration
for stateless presentation generation endpoints.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi import HTTPException

from enums.tone import Tone
from enums.verbosity import Verbosity
from models.stateless_models import (
    StatelessGenerateRequest,
    StatelessOutlineRequest,
    StatelessGenerateFromOutlineRequest,
    StatelessOutlineResponse,
    StatelessGenerationContext,
)
from models.presentation_outline_model import PresentationOutlineModel, SlideOutlineModel
from services.stateless_flow_service import StatelessFlowService


class TestStatelessFlowServiceNormalizeTemplate:
    """Tests for normalize_template method."""

    def test_normalize_template_valid_general(self):
        """Test normalizing valid 'general' template."""
        result = StatelessFlowService.normalize_template("general")
        assert result == "general"

    def test_normalize_template_valid_modern(self):
        """Test normalizing valid 'modern' template."""
        result = StatelessFlowService.normalize_template("modern")
        assert result == "modern"

    def test_normalize_template_valid_standard(self):
        """Test normalizing valid 'standard' template."""
        result = StatelessFlowService.normalize_template("standard")
        assert result == "standard"

    def test_normalize_template_valid_swift(self):
        """Test normalizing valid 'swift' template."""
        result = StatelessFlowService.normalize_template("swift")
        assert result == "swift"

    def test_normalize_template_custom_prefix(self):
        """Test normalizing custom template with 'custom-' prefix."""
        result = StatelessFlowService.normalize_template("custom-my-template")
        assert result == "custom-my-template"

    def test_normalize_template_custom_prefix_uppercase(self):
        """Test normalizing custom template with uppercase is lowercased."""
        result = StatelessFlowService.normalize_template("Custom-MyTemplate")
        assert result == "custom-mytemplate"

    def test_normalize_template_invalid_raises_exception(self):
        """Test that invalid template raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            StatelessFlowService.normalize_template("invalid-template")

        assert exc_info.value.status_code == 400
        assert "Template not found" in exc_info.value.detail

    def test_normalize_template_empty_string_raises_exception(self):
        """Test that empty string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            StatelessFlowService.normalize_template("")

        assert exc_info.value.status_code == 400

    def test_normalize_template_partial_custom_raises_exception(self):
        """Test that partial 'custom' without hyphen raises exception."""
        with pytest.raises(HTTPException) as exc_info:
            StatelessFlowService.normalize_template("customtemplate")

        assert exc_info.value.status_code == 400


class TestStatelessFlowServiceNormalizeExportAs:
    """Tests for normalize_export_as method."""

    def test_normalize_export_as_pptx(self):
        """Test normalizing 'pptx' export format."""
        result = StatelessFlowService.normalize_export_as("pptx")
        assert result == "pptx"

    def test_normalize_export_as_pdf(self):
        """Test normalizing 'pdf' export format."""
        result = StatelessFlowService.normalize_export_as("pdf")
        assert result == "pdf"

    def test_normalize_export_as_invalid_defaults_to_pptx(self):
        """Test that invalid format defaults to 'pptx'."""
        result = StatelessFlowService.normalize_export_as("docx")
        assert result == "pptx"

    def test_normalize_export_as_empty_defaults_to_pptx(self):
        """Test that empty string defaults to 'pptx'."""
        result = StatelessFlowService.normalize_export_as("")
        assert result == "pptx"

    def test_normalize_export_as_uppercase_defaults_to_pptx(self):
        """Test that uppercase 'PPTX' defaults to 'pptx' (case sensitive)."""
        result = StatelessFlowService.normalize_export_as("PPTX")
        assert result == "pptx"


class TestStatelessFlowServiceValidateGenerateRequest:
    """Tests for validate_generate_request method."""

    def test_validate_with_content(self):
        """Test validation passes with content."""
        request = StatelessGenerateRequest(content="Test topic")
        # Should not raise
        StatelessFlowService.validate_generate_request(request)

    def test_validate_with_slides_markdown(self):
        """Test validation passes with slides_markdown."""
        request = StatelessGenerateRequest(
            slides_markdown=["# Slide 1", "# Slide 2"]
        )
        # Should not raise
        StatelessFlowService.validate_generate_request(request)

    def test_validate_with_files(self):
        """Test validation passes with files."""
        request = StatelessGenerateRequest(
            files=["/path/to/file.pdf"]
        )
        # Should not raise
        StatelessFlowService.validate_generate_request(request)

    def test_validate_with_all_content_sources(self):
        """Test validation passes with all content sources."""
        request = StatelessGenerateRequest(
            content="Topic",
            slides_markdown=["# Slide"],
            files=["/path/to/file.pdf"],
        )
        # Should not raise
        StatelessFlowService.validate_generate_request(request)

    def test_validate_no_content_raises_exception(self):
        """Test that no content source raises HTTPException."""
        request = StatelessGenerateRequest()

        with pytest.raises(HTTPException) as exc_info:
            StatelessFlowService.validate_generate_request(request)

        assert exc_info.value.status_code == 400
        assert "content, slides_markdown, or files is required" in exc_info.value.detail

    def test_validate_empty_content_only_raises_exception(self):
        """Test that empty content string only raises exception."""
        request = StatelessGenerateRequest(content="")

        with pytest.raises(HTTPException) as exc_info:
            StatelessFlowService.validate_generate_request(request)

        assert exc_info.value.status_code == 400

    def test_validate_n_slides_zero_raises_exception(self):
        """Test that n_slides=0 raises HTTPException."""
        # Note: Pydantic validation should catch this first,
        # but the service also validates
        request = StatelessGenerateRequest(content="Test")
        request.n_slides = 0  # Bypass Pydantic

        with pytest.raises(HTTPException) as exc_info:
            StatelessFlowService.validate_generate_request(request)

        assert exc_info.value.status_code == 400
        assert "Number of slides must be greater than 0" in exc_info.value.detail

    def test_validate_n_slides_negative_raises_exception(self):
        """Test that negative n_slides raises HTTPException."""
        request = StatelessGenerateRequest(content="Test")
        request.n_slides = -5  # Bypass Pydantic

        with pytest.raises(HTTPException) as exc_info:
            StatelessFlowService.validate_generate_request(request)

        assert exc_info.value.status_code == 400


class TestStatelessFlowServiceValidateOutlineRequest:
    """Tests for validate_outline_request method."""

    def test_validate_with_content(self):
        """Test validation passes with content."""
        request = StatelessOutlineRequest(content="Test topic")
        # Should not raise
        StatelessFlowService.validate_outline_request(request)

    def test_validate_empty_content_raises_exception(self):
        """Test that empty content raises HTTPException."""
        request = StatelessOutlineRequest(content="")

        with pytest.raises(HTTPException) as exc_info:
            StatelessFlowService.validate_outline_request(request)

        assert exc_info.value.status_code == 400
        assert "Content is required" in exc_info.value.detail

    def test_validate_n_slides_zero_raises_exception(self):
        """Test that n_slides=0 raises HTTPException."""
        request = StatelessOutlineRequest(content="Test")
        request.n_slides = 0  # Bypass Pydantic

        with pytest.raises(HTTPException) as exc_info:
            StatelessFlowService.validate_outline_request(request)

        assert exc_info.value.status_code == 400
        assert "Number of slides must be greater than 0" in exc_info.value.detail

    def test_validate_n_slides_negative_raises_exception(self):
        """Test that negative n_slides raises HTTPException."""
        request = StatelessOutlineRequest(content="Test")
        request.n_slides = -1  # Bypass Pydantic

        with pytest.raises(HTTPException) as exc_info:
            StatelessFlowService.validate_outline_request(request)

        assert exc_info.value.status_code == 400


class TestStatelessFlowServiceValidateFromOutlineRequest:
    """Tests for validate_from_outline_request method."""

    @pytest.fixture
    def valid_outlines(self):
        """Create valid outlines for testing."""
        return PresentationOutlineModel(
            slides=[
                SlideOutlineModel(content="Slide 1"),
                SlideOutlineModel(content="Slide 2"),
            ]
        )

    def test_validate_with_outlines(self, valid_outlines):
        """Test validation passes with valid outlines."""
        request = StatelessGenerateFromOutlineRequest(outlines=valid_outlines)
        # Should not raise
        StatelessFlowService.validate_from_outline_request(request)

    def test_validate_empty_slides_raises_exception(self):
        """Test that empty slides list raises HTTPException."""
        outlines = PresentationOutlineModel(slides=[])
        request = StatelessGenerateFromOutlineRequest(outlines=outlines)

        with pytest.raises(HTTPException) as exc_info:
            StatelessFlowService.validate_from_outline_request(request)

        assert exc_info.value.status_code == 400
        assert "Outlines are required" in exc_info.value.detail


class TestStatelessFlowServiceGenerateFullPresentation:
    """Tests for generate_full_presentation method."""

    @pytest.fixture
    def valid_request(self):
        """Create a valid generate request."""
        return StatelessGenerateRequest(
            content="AI in Healthcare",
            n_slides=5,
            language="English",
            template="general",
            tone=Tone.PROFESSIONAL,
            verbosity=Verbosity.STANDARD,
        )

    @pytest.mark.anyio
    async def test_generate_full_presentation_success(self, valid_request):
        """Test successful full presentation generation."""
        mock_service = MagicMock()
        mock_service.generate_full_presentation = AsyncMock(
            return_value="/tmp/presentation.pptx"
        )

        with patch(
            'services.stateless_flow_service.StatelessPptxService',
            return_value=mock_service
        ):
            result = await StatelessFlowService.generate_full_presentation(valid_request)

        assert result == "/tmp/presentation.pptx"
        mock_service.generate_full_presentation.assert_called_once()

    @pytest.mark.anyio
    async def test_generate_full_presentation_validates_request(self):
        """Test that invalid request raises HTTPException."""
        invalid_request = StatelessGenerateRequest()

        with pytest.raises(HTTPException) as exc_info:
            await StatelessFlowService.generate_full_presentation(invalid_request)

        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_generate_full_presentation_validates_template(self):
        """Test that invalid template raises HTTPException."""
        request = StatelessGenerateRequest(
            content="Test",
            template="invalid-template",
        )

        with pytest.raises(HTTPException) as exc_info:
            await StatelessFlowService.generate_full_presentation(request)

        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_generate_full_presentation_normalizes_export_as(self, valid_request):
        """Test that export_as is normalized."""
        valid_request.export_as = "invalid"  # Should default to pptx

        mock_service = MagicMock()
        mock_service.generate_full_presentation = AsyncMock(
            return_value="/tmp/presentation.pptx"
        )

        with patch(
            'services.stateless_flow_service.StatelessPptxService',
            return_value=mock_service
        ):
            await StatelessFlowService.generate_full_presentation(valid_request)

        # Check that export_as was normalized to "pptx"
        call_kwargs = mock_service.generate_full_presentation.call_args[1]
        assert call_kwargs["export_as"] == "pptx"

    @pytest.mark.anyio
    async def test_generate_full_presentation_passes_all_parameters(self, valid_request):
        """Test that all parameters are passed to service."""
        valid_request.instructions = "Focus on benefits"
        valid_request.include_table_of_contents = True
        valid_request.include_title_slide = False
        valid_request.web_search = True

        mock_service = MagicMock()
        mock_service.generate_full_presentation = AsyncMock(
            return_value="/tmp/presentation.pptx"
        )

        with patch(
            'services.stateless_flow_service.StatelessPptxService',
            return_value=mock_service
        ):
            await StatelessFlowService.generate_full_presentation(valid_request)

        call_kwargs = mock_service.generate_full_presentation.call_args[1]
        assert call_kwargs["content"] == "AI in Healthcare"
        assert call_kwargs["n_slides"] == 5
        assert call_kwargs["language"] == "English"
        assert call_kwargs["template"] == "general"
        assert call_kwargs["tone"] == Tone.PROFESSIONAL
        assert call_kwargs["verbosity"] == Verbosity.STANDARD
        assert call_kwargs["instructions"] == "Focus on benefits"
        assert call_kwargs["include_table_of_contents"] is True
        assert call_kwargs["include_title_slide"] is False
        assert call_kwargs["web_search"] is True


class TestStatelessFlowServiceGenerateOutlines:
    """Tests for generate_outlines method."""

    @pytest.fixture
    def valid_request(self):
        """Create a valid outline request."""
        return StatelessOutlineRequest(
            content="Machine Learning Basics",
            n_slides=8,
            language="English",
            template="modern",
        )

    @pytest.fixture
    def mock_outline_response(self):
        """Create a mock outline response."""
        return StatelessOutlineResponse(
            title="Machine Learning Basics",
            outlines=PresentationOutlineModel(
                slides=[
                    SlideOutlineModel(content="Introduction"),
                    SlideOutlineModel(content="What is ML"),
                ]
            ),
            generation_context=StatelessGenerationContext(
                language="English",
                template="modern",
            ),
        )

    @pytest.mark.anyio
    async def test_generate_outlines_success(self, valid_request, mock_outline_response):
        """Test successful outline generation."""
        mock_service = MagicMock()
        mock_service.generate_outlines = AsyncMock(return_value=mock_outline_response)

        with patch(
            'services.stateless_flow_service.StatelessPptxService',
            return_value=mock_service
        ):
            result = await StatelessFlowService.generate_outlines(valid_request)

        assert result.title == "Machine Learning Basics"
        assert len(result.outlines.slides) == 2
        mock_service.generate_outlines.assert_called_once()

    @pytest.mark.anyio
    async def test_generate_outlines_validates_request(self):
        """Test that invalid request raises HTTPException."""
        invalid_request = StatelessOutlineRequest(content="")

        with pytest.raises(HTTPException) as exc_info:
            await StatelessFlowService.generate_outlines(invalid_request)

        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_generate_outlines_validates_template(self):
        """Test that invalid template raises HTTPException."""
        request = StatelessOutlineRequest(
            content="Test",
            template="invalid",
        )

        with pytest.raises(HTTPException) as exc_info:
            await StatelessFlowService.generate_outlines(request)

        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_generate_outlines_passes_all_parameters(self, valid_request, mock_outline_response):
        """Test that all parameters are passed to service."""
        valid_request.tone = Tone.EDUCATIONAL
        valid_request.verbosity = Verbosity.TEXT_HEAVY
        valid_request.instructions = "Be concise"
        valid_request.include_table_of_contents = True
        valid_request.include_title_slide = False
        valid_request.web_search = True
        valid_request.files = ["/path/to/file.pdf"]

        mock_service = MagicMock()
        mock_service.generate_outlines = AsyncMock(return_value=mock_outline_response)

        with patch(
            'services.stateless_flow_service.StatelessPptxService',
            return_value=mock_service
        ):
            await StatelessFlowService.generate_outlines(valid_request)

        call_kwargs = mock_service.generate_outlines.call_args[1]
        assert call_kwargs["content"] == "Machine Learning Basics"
        assert call_kwargs["n_slides"] == 8
        assert call_kwargs["language"] == "English"
        assert call_kwargs["template"] == "modern"
        assert call_kwargs["tone"] == Tone.EDUCATIONAL
        assert call_kwargs["verbosity"] == Verbosity.TEXT_HEAVY
        assert call_kwargs["instructions"] == "Be concise"
        assert call_kwargs["include_table_of_contents"] is True
        assert call_kwargs["include_title_slide"] is False
        assert call_kwargs["web_search"] is True
        assert call_kwargs["files"] == ["/path/to/file.pdf"]


class TestStatelessFlowServiceGenerateFromOutline:
    """Tests for generate_from_outline method."""

    @pytest.fixture
    def valid_outlines(self):
        """Create valid outlines."""
        return PresentationOutlineModel(
            slides=[
                SlideOutlineModel(content="Introduction"),
                SlideOutlineModel(content="Details"),
                SlideOutlineModel(content="Conclusion"),
            ]
        )

    @pytest.fixture
    def valid_request(self, valid_outlines):
        """Create a valid generate from outline request."""
        return StatelessGenerateFromOutlineRequest(
            outlines=valid_outlines,
            title="My Presentation",
            template="general",
        )

    @pytest.mark.anyio
    async def test_generate_from_outline_success(self, valid_request):
        """Test successful generation from outlines."""
        mock_service = MagicMock()
        mock_service.generate_pptx_from_outlines = AsyncMock(
            return_value="/tmp/presentation.pptx"
        )

        with patch(
            'services.stateless_flow_service.StatelessPptxService',
            return_value=mock_service
        ):
            result = await StatelessFlowService.generate_from_outline(valid_request)

        assert result == "/tmp/presentation.pptx"
        mock_service.generate_pptx_from_outlines.assert_called_once()

    @pytest.mark.anyio
    async def test_generate_from_outline_validates_request(self):
        """Test that empty outlines raises HTTPException."""
        outlines = PresentationOutlineModel(slides=[])
        request = StatelessGenerateFromOutlineRequest(outlines=outlines)

        with pytest.raises(HTTPException) as exc_info:
            await StatelessFlowService.generate_from_outline(request)

        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_generate_from_outline_validates_template(self, valid_outlines):
        """Test that invalid template raises HTTPException."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=valid_outlines,
            template="invalid-template",
        )

        with pytest.raises(HTTPException) as exc_info:
            await StatelessFlowService.generate_from_outline(request)

        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_generate_from_outline_uses_context_values(self, valid_outlines):
        """Test that generation_context values are used."""
        context = StatelessGenerationContext(
            language="Japanese",
            tone="professional",
            verbosity="concise",
            instructions="Context instructions",
            template="modern",
            source_summary="Summary from context",
        )
        request = StatelessGenerateFromOutlineRequest(
            outlines=valid_outlines,
            generation_context=context,
            title="Test Title",
        )

        mock_service = MagicMock()
        mock_service.generate_pptx_from_outlines = AsyncMock(
            return_value="/tmp/presentation.pptx"
        )

        with patch(
            'services.stateless_flow_service.StatelessPptxService',
            return_value=mock_service
        ):
            await StatelessFlowService.generate_from_outline(request)

        call_kwargs = mock_service.generate_pptx_from_outlines.call_args[1]
        assert call_kwargs["language"] == "Japanese"
        assert call_kwargs["tone"] == Tone.PROFESSIONAL
        assert call_kwargs["verbosity"] == Verbosity.CONCISE
        assert call_kwargs["instructions"] == "Context instructions"
        assert call_kwargs["template"] == "modern"
        assert call_kwargs["source_summary"] == "Summary from context"
        assert call_kwargs["title"] == "Test Title"

    @pytest.mark.anyio
    async def test_generate_from_outline_with_custom_template(self, valid_outlines):
        """Test generation with custom template."""
        request = StatelessGenerateFromOutlineRequest(
            outlines=valid_outlines,
            template="custom-my-template",
        )

        mock_service = MagicMock()
        mock_service.generate_pptx_from_outlines = AsyncMock(
            return_value="/tmp/presentation.pptx"
        )

        with patch(
            'services.stateless_flow_service.StatelessPptxService',
            return_value=mock_service
        ):
            result = await StatelessFlowService.generate_from_outline(request)

        assert result == "/tmp/presentation.pptx"
        call_kwargs = mock_service.generate_pptx_from_outlines.call_args[1]
        assert call_kwargs["template"] == "custom-my-template"


class TestStatelessFlowServiceIntegration:
    """Integration-style tests for StatelessFlowService."""

    @pytest.mark.anyio
    async def test_full_two_step_flow_simulation(self):
        """Test simulation of complete two-step flow."""
        # Step 1: Generate outlines
        outline_request = StatelessOutlineRequest(
            content="Introduction to Python",
            n_slides=5,
            language="English",
            template="general",
            tone=Tone.EDUCATIONAL,
        )

        mock_outline_response = StatelessOutlineResponse(
            title="Introduction to Python",
            outlines=PresentationOutlineModel(
                slides=[
                    SlideOutlineModel(content="What is Python?"),
                    SlideOutlineModel(content="Why Learn Python?"),
                    SlideOutlineModel(content="Getting Started"),
                ]
            ),
            generation_context=StatelessGenerationContext(
                language="English",
                tone="educational",
                verbosity="standard",
                template="general",
            ),
        )

        mock_service = MagicMock()
        mock_service.generate_outlines = AsyncMock(return_value=mock_outline_response)
        mock_service.generate_pptx_from_outlines = AsyncMock(
            return_value="/tmp/python_intro.pptx"
        )

        with patch(
            'services.stateless_flow_service.StatelessPptxService',
            return_value=mock_service
        ):
            # Step 1
            step1_result = await StatelessFlowService.generate_outlines(outline_request)

            assert step1_result.title == "Introduction to Python"
            assert len(step1_result.outlines.slides) == 3

            # Step 2: Use Step 1 response
            step2_request = StatelessGenerateFromOutlineRequest(
                outlines=step1_result.outlines,
                title=step1_result.title,
                generation_context=step1_result.generation_context,
            )

            step2_result = await StatelessFlowService.generate_from_outline(step2_request)

            assert step2_result == "/tmp/python_intro.pptx"
