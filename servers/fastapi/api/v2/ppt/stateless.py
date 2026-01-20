"""
Stateless PPT Generation API v2

Provides database-free presentation generation with two paths:
1. Quick path: One-step generation (outline → slides → export)
2. Two-step path: Generate outline first, user adjusts, then generate

All data is passed via JSON - no database storage required.
"""

import asyncio
import json
import os
import traceback
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse

from constants.presentation import DEFAULT_TEMPLATES
from enums.tone import Tone
from enums.verbosity import Verbosity
from models.presentation_outline_model import PresentationOutlineModel
from models.stateless_models import (
    SSECompleteMessage,
    SSEErrorMessage,
    SSEProgressMessage,
    StatelessGenerateFromOutlineRequest,
    StatelessGenerateRequest,
    StatelessOutlineRequest,
    StatelessOutlineResponse,
)
from services.stateless_pptx_service import StatelessPptxService
from services.stateless_task_store import STATELESS_TASK_STORE
from services.temp_file_service import TEMP_FILE_SERVICE


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
    # Validate input
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

    # Validate template
    if request.template not in DEFAULT_TEMPLATES:
        template_lower = request.template.lower()
        if not template_lower.startswith("custom-"):
            raise HTTPException(
                status_code=400,
                detail="Template not found. Please use a valid template.",
            )
        request.template = template_lower

    try:
        service = StatelessPptxService()

        file_path = await service.generate_full_presentation(
            content=request.content,
            n_slides=request.n_slides,
            language=request.language,
            template=request.template,
            slides_markdown=request.slides_markdown,
            files=request.files,
            tone=request.tone,
            verbosity=request.verbosity,
            instructions=request.instructions,
            include_table_of_contents=request.include_table_of_contents,
            include_title_slide=request.include_title_slide,
            web_search=request.web_search,
            export_as=request.export_as,
        )

        filename = os.path.basename(file_path)
        media_type = (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            if request.export_as == "pptx"
            else "application/pdf"
        )

        return FileResponse(
            file_path,
            media_type=media_type,
            filename=filename,
        )

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

    if template not in DEFAULT_TEMPLATES:
        template_lower = template.lower()
        if not template_lower.startswith("custom-"):
            raise HTTPException(
                status_code=400,
                detail="Template not found. Please use a valid template.",
            )
        template = template_lower

    async def event_generator():
        task_id = STATELESS_TASK_STORE.create_task_id()
        last_progress_message = ""

        def progress_callback(message: str, progress: float):
            nonlocal last_progress_message
            last_progress_message = message
            # We'll yield this in the next iteration

        try:
            service = StatelessPptxService()

            # Start generation in a task so we can yield progress
            generation_task = asyncio.create_task(
                service.generate_full_presentation(
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
                    export_as=export_as if export_as in ("pptx", "pdf") else "pptx",
                    progress_callback=progress_callback,
                )
            )

            # Poll for progress while generation runs
            last_sent_message = ""
            while not generation_task.done():
                if await request.is_disconnected():
                    generation_task.cancel()
                    return

                if last_progress_message != last_sent_message:
                    progress_msg = SSEProgressMessage(
                        message=last_progress_message,
                        progress=0.5,  # Approximate progress
                    )
                    yield f"data: {progress_msg.model_dump_json()}\n\n"
                    last_sent_message = last_progress_message

                await asyncio.sleep(0.5)

            file_path = await generation_task
            filename = os.path.basename(file_path)

            # Determine media type
            media_type = (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                if export_as == "pptx"
                else "application/pdf"
            )

            # Store file for download
            await STATELESS_TASK_STORE.store_file(
                task_id=task_id,
                file_path=file_path,
                filename=filename,
                media_type=media_type,
            )

            # Send completion message
            complete_msg = SSECompleteMessage(
                download_url=f"/api/v2/ppt/stateless/download/{task_id}",
            )
            yield f"data: {complete_msg.model_dump_json()}\n\n"

        except asyncio.CancelledError:
            return
        except Exception as e:
            traceback.print_exc()
            error_msg = SSEErrorMessage(detail=str(e))
            yield f"data: {error_msg.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
    """
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

    try:
        service = StatelessPptxService()
        response = await service.generate_outlines(
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
        )
        return response

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
    """
    if not request.outlines.slides:
        raise HTTPException(
            status_code=400,
            detail="Outlines are required",
        )

    # Validate template
    if request.template not in DEFAULT_TEMPLATES:
        template_lower = request.template.lower()
        if not template_lower.startswith("custom-"):
            raise HTTPException(
                status_code=400,
                detail="Template not found. Please use a valid template.",
            )
        request.template = template_lower

    try:
        service = StatelessPptxService()

        file_path = await service.generate_pptx_from_outlines(
            outlines=request.outlines,
            template=request.template,
            language=request.language,
            tone=request.tone,
            verbosity=request.verbosity,
            instructions=request.instructions,
            title=request.title,
        )

        filename = os.path.basename(file_path)
        media_type = (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            if request.export_as == "pptx"
            else "application/pdf"
        )

        return FileResponse(
            file_path,
            media_type=media_type,
            filename=filename,
        )

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
    """
    if not request.outlines.slides:
        raise HTTPException(
            status_code=400,
            detail="Outlines are required",
        )

    # Validate template
    if request.template not in DEFAULT_TEMPLATES:
        template_lower = request.template.lower()
        if not template_lower.startswith("custom-"):
            raise HTTPException(
                status_code=400,
                detail="Template not found. Please use a valid template.",
            )
        request.template = template_lower

    async def event_generator():
        task_id = STATELESS_TASK_STORE.create_task_id()
        progress_queue: asyncio.Queue[tuple[str, float]] = asyncio.Queue()

        def progress_callback(message: str, progress: float):
            try:
                progress_queue.put_nowait((message, progress))
            except asyncio.QueueFull:
                pass

        try:
            service = StatelessPptxService()

            # Start generation task
            generation_task = asyncio.create_task(
                service.generate_pptx_from_outlines(
                    outlines=request.outlines,
                    template=request.template,
                    language=request.language,
                    tone=request.tone,
                    verbosity=request.verbosity,
                    instructions=request.instructions,
                    title=request.title,
                    progress_callback=progress_callback,
                )
            )

            # Send progress updates
            while not generation_task.done():
                if await http_request.is_disconnected():
                    generation_task.cancel()
                    return

                try:
                    message, progress = await asyncio.wait_for(
                        progress_queue.get(),
                        timeout=1.0,
                    )
                    progress_msg = SSEProgressMessage(
                        message=message,
                        progress=progress,
                    )
                    yield f"data: {progress_msg.model_dump_json()}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"

            file_path = await generation_task
            filename = os.path.basename(file_path)

            media_type = (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                if request.export_as == "pptx"
                else "application/pdf"
            )

            await STATELESS_TASK_STORE.store_file(
                task_id=task_id,
                file_path=file_path,
                filename=filename,
                media_type=media_type,
            )

            complete_msg = SSECompleteMessage(
                download_url=f"/api/v2/ppt/stateless/download/{task_id}",
            )
            yield f"data: {complete_msg.model_dump_json()}\n\n"

        except asyncio.CancelledError:
            return
        except Exception as e:
            traceback.print_exc()
            error_msg = SSEErrorMessage(detail=str(e))
            yield f"data: {error_msg.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
