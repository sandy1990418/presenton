from typing import Annotated, Optional
from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models.sql.slide import SlideModel
from services.database import get_async_session
from handlers.slide_handler import SlideHandler


SLIDE_ROUTER = APIRouter(prefix="/slide", tags=["Slide"])


@SLIDE_ROUTER.post("/edit")
async def edit_slide(
    id: Annotated[str, Body()],
    prompt: Annotated[str, Body()],
    sql_session: AsyncSession = Depends(get_async_session),
):
    """Edit a slide with AI-generated content."""
    handler = SlideHandler(sql_session)
    return await handler.edit_slide(id, prompt)


@SLIDE_ROUTER.post("/edit-html", response_model=SlideModel)
async def edit_slide_html(
    id: Annotated[str, Body()],
    prompt: Annotated[str, Body()],
    html: Annotated[Optional[str], Body()] = None,
    sql_session: AsyncSession = Depends(get_async_session),
):
    """Edit slide HTML content directly."""
    handler = SlideHandler(sql_session)
    return await handler.edit_slide_html(id, prompt, html)
