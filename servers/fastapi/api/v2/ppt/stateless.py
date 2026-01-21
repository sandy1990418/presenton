"""
Stateless PPT Generation API v2

Provides database-free presentation generation with two paths:
1. Quick path: One-step generation (outline -> slides -> export)
2. Two-step path: Generate outline first, user adjusts, then generate

All data is passed via JSON - no database storage required.
"""

import os
import traceback
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from enums.tone import Tone
from enums.verbosity import Verbosity
from models.stateless_models import (
    StatelessGenerateFromOutlineRequest,
    StatelessGenerateRequest,
    StatelessOutlineRequest,
    StatelessOutlineResponse,
)
from services.stateless_flow_service import StatelessFlowService
from services.stateless_task_store import STATELESS_TASK_STORE
from api.v2.ppt.stateless_responses import build_file_response
from api.v2.ppt.stateless_streaming import (
    build_sse_response,
    stream_generate_from_outline,
    stream_generate_presentation,
)


STATELESS_ROUTER = APIRouter(prefix="/stateless", tags=["Stateless PPT"])


# ====================
# Quick Path - One-step generation
# ====================


@STATELESS_ROUTER.post("/generate")
async def generate_presentation_stateless(
    request: StatelessGenerateRequest,
):
    """
    Generate a complete presentation in one step.

    This endpoint handles the full flow:
    1. Generate outlines from content
    2. Generate slide content
    3. Fetch assets (images, icons)
    4. Export to PPTX (or PDF)

    Returns the file directly as a download.
    """
    try:
        file_path = await StatelessFlowService.generate_full_presentation(request)
        return build_file_response(file_path)

    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Failed to generate presentation",
        )


@STATELESS_ROUTER.get("/generate/stream")
async def generate_presentation_stateless_stream(
    request: Request,
    content: str = Query(default="", description="Presentation content/topic"),
    n_slides: int = Query(default=8, ge=1, le=50, description="Number of slides"),
    language: str = Query(default="English", description="Output language"),
    template: str = Query(default="general", description="Template name"),
    tone: Tone = Query(default=Tone.DEFAULT, description="Presentation tone"),
    verbosity: Verbosity = Query(
        default=Verbosity.STANDARD, description="Content verbosity"
    ),
    instructions: Optional[str] = Query(default=None, description="Custom instructions"),
    include_table_of_contents: bool = Query(default=False, description="Include TOC"),
    include_title_slide: bool = Query(default=True, description="Include title slide"),
    web_search: bool = Query(default=False, description="Use web search"),
    export_as: str = Query(default="pptx", description="Export format (pptx or pdf)"),
):
    """
    Generate a presentation with SSE progress updates.

    Streams progress messages and returns a download URL when complete.
    """
    if not content:
        raise HTTPException(
            status_code=400,
            detail="Content is required",
        )

    template = StatelessFlowService.normalize_template(template)
    export_as = StatelessFlowService.normalize_export_as(export_as)

    return build_sse_response(
        stream_generate_presentation(
            request,
            content=content,
            n_slides=n_slides,
            language=language,
            template=template,
            tone=tone,
            verbosity=verbosity,
            instructions=instructions,
            include_table_of_contents=include_table_of_contents,
            include_title_slide=include_title_slide,
            web_search=web_search,
            export_as=export_as,
        )
    )


# ====================
# Two-step Path
# ====================


@STATELESS_ROUTER.post("/outline", response_model=StatelessOutlineResponse)
async def generate_outline_stateless(
    request: StatelessOutlineRequest,
):
    """
    Step 1: Generate presentation outlines.

    Returns outlines that can be reviewed and adjusted by the user
    before generating the full presentation.

    The response includes generation_context which carries all settings
    to Step 2, so frontend only needs to pass the response back with
    any outline adjustments.
    """
    try:
        return await StatelessFlowService.generate_outlines(request)

    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Failed to generate outlines",
        )


@STATELESS_ROUTER.post("/generate-from-outline")
async def generate_from_outline_stateless(
    request: StatelessGenerateFromOutlineRequest,
):
    """
    Step 2: Generate presentation from user-adjusted outlines.

    Takes the (potentially modified) outlines from step 1 and
    generates the complete presentation.

    Frontend can pass the entire Step 1 response back:
    ```json
    {
        "title": "My Presentation",
        "outlines": {...},
        "generation_context": {"language": "English", "tone": "professional", "template": "general", "source_summary": "...", ...},
        "export_as": "pptx"
    }
    ```

    The generation_context from Step 1 carries all settings including template and source_summary.
    The source_summary is used to prevent hallucination when generating slide content.
    """
    try:
        file_path = await StatelessFlowService.generate_from_outline(request)
        return build_file_response(file_path)

    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Failed to generate presentation from outlines",
        )


@STATELESS_ROUTER.post("/generate-from-outline/stream")
async def generate_from_outline_stateless_stream(
    request: StatelessGenerateFromOutlineRequest,
    http_request: Request,
):
    """
    Step 2 with SSE: Generate presentation from outlines with progress updates.

    Supports passing generation_context from Step 1 response, including source_chunks
    for per-slide context and hallucination prevention.
    """
    StatelessFlowService.validate_from_outline_request(request)
    template = StatelessFlowService.normalize_template(request.get_template())

    return build_sse_response(
        stream_generate_from_outline(
            http_request,
            request=request,
            template=template,
        )
    )


# ====================
# Download endpoint
# ====================


@STATELESS_ROUTER.get("/download/{task_id}")
async def download_generated_file(task_id: str):
    """
    Download a generated file by task ID.

    Files are stored temporarily and expire after 30 minutes.
    """
    task_info = await STATELESS_TASK_STORE.get_task(task_id)

    if task_info is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found or expired",
        )

    if not os.path.exists(task_info.file_path):
        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    return FileResponse(
        task_info.file_path,
        media_type=task_info.media_type,
        filename=task_info.filename,
    )
