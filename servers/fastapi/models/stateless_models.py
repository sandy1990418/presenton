"""
Stateless API models for v2 PPT generation.

These models support database-free presentation generation where
all data is passed via JSON in request/response bodies.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from enums.tone import Tone
from enums.verbosity import Verbosity
from models.presentation_outline_model import PresentationOutlineModel


@dataclass
class ImageAssetData:
    """
    Image asset data without database dependency.
    Replaces models.sql.image_asset.ImageAsset for stateless operations.
    """

    path: str
    is_uploaded: bool = False
    extras: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SlideData:
    """
    Slide data without database dependency.
    Replaces models.sql.slide.SlideModel for stateless operations.
    """

    content: Dict[str, Any] = field(default_factory=dict)
    layout_group: str = ""
    layout: str = ""
    index: int = 0
    speaker_note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SourceChunk(BaseModel):
    """
    A chunk of source document content.

    Used to pass relevant document excerpts between Step 1 (outline) and Step 2 (slide generation).
    Each slide can reference specific chunks by ID to ensure accurate content generation.

    In Step 1 responses, ``content`` is stripped (empty string) to keep
    payloads small.  Full content is stored server-side and retrieved in
    Step 2 via ``source_context_id``.
    """

    id: int = Field(description="Unique chunk identifier")
    document_id: int = Field(default=0, description="Source document identifier")
    title: str = Field(description="Short title/topic for this chunk")
    summary: str = Field(description="Brief summary of the chunk content")
    content: str = Field(
        default="",
        description="Original content (may be empty in Step 1 response)",
    )

    def without_content(self) -> "SourceChunk":
        """Return a lightweight copy with content stripped."""
        return SourceChunk(
            id=self.id,
            document_id=self.document_id,
            title=self.title,
            summary=self.summary,
            content="",
        )


class StatelessGenerationContext(BaseModel):
    """
    Context information for generation, passed between steps in two-step flow.

    This context is returned in Step 1 response and can be passed back to Step 2
    to maintain all settings without frontend needing to re-specify them.
    """

    language: str = Field(default="English", description="Output language")
    tone: str = Field(default="default", description="Presentation tone")
    verbosity: str = Field(default="standard", description="Content verbosity level")
    instructions: Optional[str] = Field(
        default=None, description="Custom instructions for generation"
    )
    include_table_of_contents: bool = Field(
        default=False, description="Whether to include table of contents"
    )
    include_title_slide: bool = Field(
        default=True, description="Whether to include title slide"
    )
    n_slides: int = Field(default=8, description="Number of slides")
    template: str = Field(default="general", description="Presentation template name")

    # Source document context for Step 2 (chunked approach)
    source_context_id: Optional[str] = Field(
        default=None,
        description=(
            "Opaque key for retrieving full source chunks from server-side "
            "storage. Returned in Step 1 and passed back in Step 2."
        ),
    )
    source_chunks: Optional[List[SourceChunk]] = Field(
        default=None,
        description=(
            "Lightweight chunk metadata (content stripped). "
            "Full content is fetched via source_context_id in Step 2."
        ),
    )

    # Legacy: kept for backward compatibility
    source_summary: Optional[str] = Field(
        default=None,
        description=(
            "[Deprecated] Use source_chunks instead. "
            "Condensed summary of source documents."
        ),
    )


class StatelessOutlineRequest(BaseModel):
    """Request model for generating presentation outlines (Step 1 of two-step flow)."""

    content: str = Field(description="The main content/topic for the presentation")
    files: Optional[List[str]] = Field(
        default=None, description="File paths to include as additional context"
    )

    n_slides: int = Field(default=8, ge=1, le=50, description="Number of slides")
    language: str = Field(default="English", description="Output language")
    template: str = Field(
        default="general",
        description="Presentation template name (passed to Step 2 via context)",
    )

    tone: Tone = Field(default=Tone.DEFAULT, description="Presentation tone")
    verbosity: Verbosity = Field(
        default=Verbosity.STANDARD, description="Content verbosity"
    )
    instructions: Optional[str] = Field(
        default=None, description="Custom instructions for generation"
    )

    include_table_of_contents: bool = Field(
        default=False, description="Whether to include table of contents"
    )
    include_title_slide: bool = Field(
        default=True, description="Whether to include title slide"
    )
    web_search: bool = Field(
        default=False, description="Whether to use web search for content"
    )


class StatelessOutlineResponse(BaseModel):
    """Response model containing generated outlines for user review."""

    title: str = Field(description="Presentation title extracted from outlines")
    outlines: PresentationOutlineModel = Field(description="Generated slide outlines")
    generation_context: StatelessGenerationContext = Field(
        description="Context to pass to generation step"
    )


class StatelessGenerateRequest(BaseModel):
    """Request model for one-step (quick) generation."""

    content: str = Field(
        default="", description="The main content/topic for the presentation"
    )
    slides_markdown: Optional[List[str]] = Field(
        default=None, description="Pre-defined markdown content for each slide"
    )
    files: Optional[List[str]] = Field(
        default=None, description="File paths to include as additional context"
    )

    n_slides: int = Field(default=8, ge=1, le=50, description="Number of slides")
    language: str = Field(default="English", description="Output language")
    template: str = Field(default="general", description="Presentation template name")

    tone: Tone = Field(default=Tone.DEFAULT, description="Presentation tone")
    verbosity: Verbosity = Field(
        default=Verbosity.STANDARD, description="Content verbosity"
    )
    instructions: Optional[str] = Field(
        default=None, description="Custom instructions for generation"
    )

    include_table_of_contents: bool = Field(
        default=False, description="Whether to include table of contents"
    )
    include_title_slide: bool = Field(
        default=True, description="Whether to include title slide"
    )
    web_search: bool = Field(
        default=False, description="Whether to use web search for content"
    )

    export_as: Literal["pptx", "pdf"] = Field(
        default="pptx", description="Export format"
    )


class StatelessGenerateFromOutlineRequest(BaseModel):
    """
    Request model for generating from user-adjusted outlines (Step 2).

    Frontend can pass the entire Step 1 response back, only modifying the outlines.
    The generation_context from Step 1 carries all the settings.

    Usage:
        # Frontend receives Step 1 response:
        step1_response = {
            "title": "My Presentation",
            "outlines": {...},
            "generation_context": {"language": "English", "tone": "professional", ...}
        }

        # Frontend adjusts outlines and sends back:
        step2_request = {
            **step1_response,  # Include everything from Step 1
            "template": "general",  # Only need to add Step 2 specific fields
            "export_as": "pptx"
        }
    """

    # From Step 1 response (can be passed directly)
    outlines: PresentationOutlineModel = Field(
        description="User-adjusted slide outlines"
    )
    title: Optional[str] = Field(
        default=None, description="Presentation title (from Step 1 or user override)"
    )
    generation_context: Optional[StatelessGenerationContext] = Field(
        default=None,
        description="Context from Step 1 response. If provided, overrides individual settings below.",
    )

    # Step 2 specific settings
    template: str = Field(default="general", description="Presentation template name")
    export_as: Literal["pptx", "pdf"] = Field(
        default="pptx", description="Export format"
    )

    # Fallback individual settings (used if generation_context not provided)
    language: str = Field(default="English", description="Output language")
    tone: Tone = Field(default=Tone.DEFAULT, description="Presentation tone")
    verbosity: Verbosity = Field(
        default=Verbosity.STANDARD, description="Content verbosity"
    )
    instructions: Optional[str] = Field(
        default=None, description="Custom instructions for generation"
    )

    def get_language(self) -> str:
        """Get language from context or fallback."""
        if self.generation_context:
            return self.generation_context.language
        return self.language

    def get_tone(self) -> Tone:
        """Get tone from context or fallback."""
        if self.generation_context:
            # Convert string back to Tone enum
            try:
                return Tone(self.generation_context.tone)
            except ValueError:
                return Tone.DEFAULT
        return self.tone

    def get_verbosity(self) -> Verbosity:
        """Get verbosity from context or fallback."""
        if self.generation_context:
            try:
                return Verbosity(self.generation_context.verbosity)
            except ValueError:
                return Verbosity.STANDARD
        return self.verbosity

    def get_instructions(self) -> Optional[str]:
        """Get instructions from context or fallback."""
        if self.generation_context:
            return self.generation_context.instructions
        return self.instructions

    def get_template(self) -> str:
        """Get template from context or fallback."""
        if self.generation_context and self.generation_context.template:
            return self.generation_context.template
        return self.template

    def get_source_summary(self) -> Optional[str]:
        """Get source document summary from context (legacy)."""
        if self.generation_context:
            return self.generation_context.source_summary
        return None

    def get_source_chunks(self) -> Optional[List["SourceChunk"]]:
        """Get source document chunks from context."""
        if self.generation_context:
            return self.generation_context.source_chunks
        return None

    def get_source_context_id(self) -> Optional[str]:
        """Get source context ID for retrieving full chunks from store."""
        if self.generation_context:
            return self.generation_context.source_context_id
        return None


class SSEProgressMessage(BaseModel):
    """SSE progress update message."""

    type: Literal["progress"] = "progress"
    message: str = Field(description="Progress message")
    progress: float = Field(ge=0, le=1, description="Progress percentage (0-1)")


class SSECompleteMessage(BaseModel):
    """SSE completion message with download URL."""

    type: Literal["complete"] = "complete"
    download_url: str = Field(description="URL to download the generated file")


class SSEErrorMessage(BaseModel):
    """SSE error message."""

    type: Literal["error"] = "error"
    detail: str = Field(description="Error details")
