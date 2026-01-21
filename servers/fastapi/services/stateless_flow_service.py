"""
Stateless flow service for v2 PPT generation.

Centralizes validation and normalization for stateless endpoints.
"""

from typing import Literal

from fastapi import HTTPException

from constants.presentation import DEFAULT_TEMPLATES
from models.stateless_models import (
    StatelessGenerateFromOutlineRequest,
    StatelessGenerateRequest,
    StatelessOutlineRequest,
    StatelessOutlineResponse,
)
from services.stateless_pptx_service import StatelessPptxService


class StatelessFlowService:
    @classmethod
    def normalize_template(cls, template: str) -> str:
        if template not in DEFAULT_TEMPLATES:
            template_lower = template.lower()
            if not template_lower.startswith("custom-"):
                raise HTTPException(
                    status_code=400,
                    detail="Template not found. Please use a valid template.",
                )
            return template_lower
        return template

    @classmethod
    def normalize_export_as(cls, export_as: str) -> Literal["pptx", "pdf"]:
        return export_as if export_as in ("pptx", "pdf") else "pptx"

    @classmethod
    def validate_generate_request(cls, request: StatelessGenerateRequest) -> None:
        if not (request.content or request.slides_markdown or request.files):
            raise HTTPException(
                status_code=400,
                detail="Either content, slides_markdown, or files is required",
            )

        if request.n_slides <= 0:
            raise HTTPException(
                status_code=400,
                detail="Number of slides must be greater than 0",
            )

    @classmethod
    def validate_outline_request(cls, request: StatelessOutlineRequest) -> None:
        if not request.content:
            raise HTTPException(
                status_code=400,
                detail="Content is required",
            )

        if request.n_slides <= 0:
            raise HTTPException(
                status_code=400,
                detail="Number of slides must be greater than 0",
            )

    @classmethod
    def validate_from_outline_request(
        cls, request: StatelessGenerateFromOutlineRequest
    ) -> None:
        if not request.outlines.slides:
            raise HTTPException(
                status_code=400,
                detail="Outlines are required",
            )

    @classmethod
    async def generate_full_presentation(
        cls, request: StatelessGenerateRequest
    ) -> str:
        cls.validate_generate_request(request)
        template = cls.normalize_template(request.template)
        export_as = cls.normalize_export_as(request.export_as)

        service = StatelessPptxService()
        return await service.generate_full_presentation(
            content=request.content,
            n_slides=request.n_slides,
            language=request.language,
            template=template,
            slides_markdown=request.slides_markdown,
            files=request.files,
            tone=request.tone,
            verbosity=request.verbosity,
            instructions=request.instructions,
            include_table_of_contents=request.include_table_of_contents,
            include_title_slide=request.include_title_slide,
            web_search=request.web_search,
            export_as=export_as,
        )

    @classmethod
    async def generate_outlines(
        cls, request: StatelessOutlineRequest
    ) -> StatelessOutlineResponse:
        cls.validate_outline_request(request)
        template = cls.normalize_template(request.template)

        service = StatelessPptxService()
        return await service.generate_outlines(
            content=request.content,
            n_slides=request.n_slides,
            language=request.language,
            files=request.files,
            tone=request.tone,
            verbosity=request.verbosity,
            instructions=request.instructions,
            include_table_of_contents=request.include_table_of_contents,
            include_title_slide=request.include_title_slide,
            web_search=request.web_search,
            template=template,
        )

    @classmethod
    async def generate_from_outline(
        cls, request: StatelessGenerateFromOutlineRequest
    ) -> str:
        cls.validate_from_outline_request(request)
        template = cls.normalize_template(request.get_template())

        service = StatelessPptxService()
        return await service.generate_pptx_from_outlines(
            outlines=request.outlines,
            template=template,
            language=request.get_language(),
            tone=request.get_tone(),
            verbosity=request.get_verbosity(),
            instructions=request.get_instructions(),
            title=request.title,
            source_summary=request.get_source_summary(),
            source_chunks=request.get_source_chunks(),
        )
