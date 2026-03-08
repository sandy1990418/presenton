from typing import List, Optional
from pydantic import Field, field_validator
from models.presentation_outline_model import (
    PresentationOutlineModel,
    SlideOutlineModel,
)
from models.presentation_structure_model import PresentationStructureModel


def get_presentation_outline_model_with_n_slides(n_slides: int):
    class SlideOutlineModelWithNSlides(SlideOutlineModel):
        content: str = Field(
            description="Markdown content for each slide",
            min_length=100,
            max_length=300,
        )

    class PresentationOutlineModelWithNSlides(PresentationOutlineModel):
        slides: List[SlideOutlineModelWithNSlides] = Field(
            description="List of slide outlines",
            min_items=n_slides,
            max_items=n_slides,
        )

    return PresentationOutlineModelWithNSlides


def get_presentation_outline_model_with_chunks(n_slides: int, n_chunks: int):
    """
    Get outline model that includes chunk_refs for each slide.

    Args:
        n_slides: Number of slides to generate
        n_chunks: Number of source chunks available (used for validation)
    """

    class SlideOutlineModelWithChunks(SlideOutlineModel):
        content: str = Field(
            description="Markdown content for each slide",
            min_length=100,
            max_length=300,
        )
        chunk_refs: Optional[List[int]] = Field(
            default=None,
            description=(
                f"List of source chunk IDs (0 to {n_chunks - 1}) that "
                "this slide should reference for facts and data. "
                "Only include chunks that are directly relevant "
                "to this slide's content."
            ),
        )

        @field_validator("chunk_refs", mode="before")
        @classmethod
        def filter_chunk_refs(cls, v: Optional[List[int]]) -> Optional[List[int]]:
            if v is None:
                return None
            return [ref for ref in v if 0 <= ref < n_chunks]

    class PresentationOutlineModelWithChunks(PresentationOutlineModel):
        slides: List[SlideOutlineModelWithChunks] = Field(
            description="List of slide outlines with source chunk references",
            min_items=n_slides,
            max_items=n_slides,
        )

    return PresentationOutlineModelWithChunks


def get_presentation_structure_model_with_n_slides(n_slides: int):
    class PresentationStructureModelWithNSlides(PresentationStructureModel):
        slides: List[int] = Field(
            description="List of slide layouts",
            min_items=n_slides,
            max_items=n_slides,
        )

    return PresentationStructureModelWithNSlides
