from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import get_async_session
from handlers.outline_handler import OutlineHandler

OUTLINES_ROUTER = APIRouter(prefix="/outlines", tags=["Outlines"])


@OUTLINES_ROUTER.get("/stream")
async def stream_outlines(
    presentation_id: str, sql_session: AsyncSession = Depends(get_async_session)
):
    """Stream presentation outline generation with real-time updates."""
    handler = OutlineHandler(sql_session)
    generator = handler.stream_outlines_generator(presentation_id)
    return handler.create_streaming_response(generator)
