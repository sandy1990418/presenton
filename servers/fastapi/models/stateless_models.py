"""
Stateless API models for v2 PPT generation.

These models support database-free presentation generation where
all data is passed via JSON in request/response bodies.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from enums.tone import Tone
from enums.verbosity import Verbosity
from models.presentation_outline_model import PresentationOutlineModel


class StatelessGenerationContext(BaseModel):
    """Context information for generation, passed between steps in two-step flow."""

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


class StatelessOutlineRequest(BaseModel):
    """Request model for generating presentation outlines (Step 1 of two-step flow)."""

    content: str = Field(description="The main content/topic for the presentation")
    files: Optional[List[str]] = Field(
        default=None, description="File paths to include as additional context"
    )

    n_slides: int = Field(default=8, ge=1, le=50, description="Number of slides")
    language: str = Field(default="English", description="Output language")

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
    outlines: PresentationOutlineModel = Field(
        description="Generated slide outlines"
    )
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
    """Request model for generating from user-adjusted outlines (Step 2)."""

    outlines: PresentationOutlineModel = Field(
        description="User-adjusted slide outlines"
    )
    title: Optional[str] = Field(
        default=None, description="Optional presentation title override"
    )

    template: str = Field(default="general", description="Presentation template name")
    language: str = Field(default="English", description="Output language")
    tone: Tone = Field(default=Tone.DEFAULT, description="Presentation tone")
    verbosity: Verbosity = Field(
        default=Verbosity.STANDARD, description="Content verbosity"
    )
    instructions: Optional[str] = Field(
        default=None, description="Custom instructions for generation"
    )

    export_as: Literal["pptx", "pdf"] = Field(
        default="pptx", description="Export format"
    )


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
