import asyncio
import time
import traceback
from typing import AsyncGenerator, Callable, Optional

from fastapi import Request
from fastapi.responses import StreamingResponse

from enums.tone import Tone
from enums.verbosity import Verbosity
from models.stateless_models import (
    SSECompleteMessage,
    SSEErrorMessage,
    SSEProgressMessage,
    StatelessGenerateFromOutlineRequest,
)
from services.stateless_pptx_service import StatelessPptxService
from services.stateless_task_store import STATELESS_TASK_STORE
from api.v2.ppt.stateless_responses import resolve_file_metadata


def _create_progress_queue(
    maxsize: int = 100,
) -> tuple[asyncio.Queue[tuple[str, float]], Callable[[str, float], None]]:
    progress_queue: asyncio.Queue[tuple[str, float]] = asyncio.Queue(maxsize=maxsize)

    def progress_callback(message: str, progress: float) -> None:
        try:
            progress_queue.put_nowait((message, progress))
        except asyncio.QueueFull:
            pass

    return progress_queue, progress_callback


async def _stream_progress_updates(
    request: Request,
    generation_task: asyncio.Task,
    progress_queue: asyncio.Queue[tuple[str, float]],
    keepalive_interval: float,
) -> AsyncGenerator[str, None]:
    last_keepalive = time.monotonic()

    while not generation_task.done():
        if await request.is_disconnected():
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
            last_keepalive = time.monotonic()
        except asyncio.TimeoutError:
            now = time.monotonic()
            if now - last_keepalive >= keepalive_interval:
                yield ": keepalive\n\n"
                last_keepalive = now


def build_sse_response(event_generator: AsyncGenerator[str, None]) -> StreamingResponse:
    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def stream_generate_presentation(
    request: Request,
    *,
    content: str,
    n_slides: int,
    language: str,
    template: str,
    tone: Tone,
    verbosity: Verbosity,
    instructions: Optional[str],
    include_table_of_contents: bool,
    include_title_slide: bool,
    web_search: bool,
    export_as: str,
) -> AsyncGenerator[str, None]:
    task_id = STATELESS_TASK_STORE.create_task_id()
    progress_queue, progress_callback = _create_progress_queue()

    try:
        service = StatelessPptxService()

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
                export_as=export_as,
                progress_callback=progress_callback,
            )
        )

        async for update in _stream_progress_updates(
            request,
            generation_task,
            progress_queue,
            keepalive_interval=15.0,
        ):
            yield update

        file_path = await generation_task
        filename, media_type = resolve_file_metadata(file_path)

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
    except Exception as exc:
        traceback.print_exc()
        error_msg = SSEErrorMessage(detail=str(exc))
        yield f"data: {error_msg.model_dump_json()}\n\n"


async def stream_generate_from_outline(
    http_request: Request,
    *,
    request: StatelessGenerateFromOutlineRequest,
    template: str,
) -> AsyncGenerator[str, None]:
    language = request.get_language()
    tone = request.get_tone()
    verbosity = request.get_verbosity()
    instructions = request.get_instructions()
    source_summary = request.get_source_summary()

    task_id = STATELESS_TASK_STORE.create_task_id()
    progress_queue, progress_callback = _create_progress_queue()

    try:
        service = StatelessPptxService()

        generation_task = asyncio.create_task(
            service.generate_pptx_from_outlines(
                outlines=request.outlines,
                template=template,
                language=language,
                tone=tone,
                verbosity=verbosity,
                instructions=instructions,
                title=request.title,
                source_summary=source_summary,
                source_chunks=request.get_source_chunks(),
                source_context_id=request.get_source_context_id(),
                progress_callback=progress_callback,
            )
        )

        async for update in _stream_progress_updates(
            http_request,
            generation_task,
            progress_queue,
            keepalive_interval=1.0,
        ):
            yield update

        file_path = await generation_task
        filename, media_type = resolve_file_metadata(file_path)

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
    except Exception as exc:
        traceback.print_exc()
        error_msg = SSEErrorMessage(detail=str(exc))
        yield f"data: {error_msg.model_dump_json()}\n\n"
