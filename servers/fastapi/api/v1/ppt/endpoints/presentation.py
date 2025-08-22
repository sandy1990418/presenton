"""
Fully refactored presentation endpoints using handler pattern.
All business logic moved to PresentationHandler, replaced all print() with proper logging.
"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Models
from models.generate_presentation_request import GeneratePresentationRequest
from models.presentation_and_path import PresentationPathAndEditPath
from models.presentation_from_template import GetPresentationUsingTemplateRequest
from models.presentation_outline_model import SlideOutlineModel
from models.pptx_models import PptxPresentationModel
from models.presentation_layout import PresentationLayoutModel
from models.presentation_with_slides import PresentationWithSlides
from models.sql.slide import SlideModel
from models.sql.presentation import PresentationModel

from services.database import get_async_session

# Note: validate_files import removed - not used in refactored version

# Import logging and handler
from utils.logging_config import get_logger
from handlers.presentation_handler import PresentationHandler

# Get logger for this module
logger = get_logger("presentation_endpoints")

PRESENTATION_ROUTER = APIRouter(prefix="/presentation", tags=["Presentation"])

# Note: Active streams are now tracked in PresentationHandler


def convert_slide_image_urls(slides: List[SlideModel]) -> List[SlideModel]:
    """Convert all image URLs in slide content to web-accessible paths."""
    # This function is kept for backward compatibility but is now handled in the handler
    logger.debug("Converting slide image URLs", slide_count=len(slides))
    for slide in slides:
        if slide.content:
            slide.content = convert_urls_in_dict(slide.content)
    return slides


def convert_urls_in_dict(data) -> any:
    """Recursively convert image URLs in a dictionary structure."""
    from utils.process_slides import convert_file_path_to_web_url
    
    if isinstance(data, dict):
        converted = {}
        for key, value in data.items():
            if key == "__image_url__" and isinstance(value, str):
                converted[key] = convert_file_path_to_web_url(value)
            elif key == "__icon_url__" and isinstance(value, str):
                converted[key] = convert_file_path_to_web_url(value)
            else:
                converted[key] = convert_urls_in_dict(value)
        return converted
    elif isinstance(data, list):
        return [convert_urls_in_dict(item) for item in data]
    else:
        return data


@PRESENTATION_ROUTER.get("", response_model=PresentationWithSlides)
async def get_presentation(
    id: str, sql_session: AsyncSession = Depends(get_async_session)
):
    """Get a presentation with all its slides."""
    handler = PresentationHandler(sql_session)
    return await handler.get_presentation(id)


@PRESENTATION_ROUTER.delete("", status_code=204)
async def delete_presentation(
    id: str, sql_session: AsyncSession = Depends(get_async_session)
):
    """Delete a presentation and all its slides."""
    handler = PresentationHandler(sql_session)
    await handler.delete_presentation(id)


@PRESENTATION_ROUTER.get("/all", response_model=List[PresentationWithSlides])
async def get_all_presentations(sql_session: AsyncSession = Depends(get_async_session)):
    """Get all presentations with their first slide."""
    handler = PresentationHandler(sql_session)
    return await handler.get_all_presentations()


@PRESENTATION_ROUTER.post("/create", response_model=PresentationModel)
async def create_presentation(
    prompt: Annotated[str, Body()],
    n_slides: Annotated[int, Body()],
    language: Annotated[str, Body()],
    file_paths: Annotated[Optional[List[str]], Body()] = None,
    web_search_enabled: Annotated[bool, Body()] = False,
    sql_session: AsyncSession = Depends(get_async_session),
):
    """Create a new presentation."""
    handler = PresentationHandler(sql_session)
    return await handler.create_presentation(
        prompt=prompt,
        n_slides=n_slides,
        language=language,
        file_paths=file_paths,
        web_search_enabled=web_search_enabled
    )


@PRESENTATION_ROUTER.post("/prepare", response_model=PresentationModel)
async def prepare_presentation(
    presentation_id: Annotated[str, Body()],
    outlines: Annotated[List[SlideOutlineModel], Body()],
    layout: Annotated[PresentationLayoutModel, Body()],
    title: Annotated[Optional[str], Body()] = None,
    sql_session: AsyncSession = Depends(get_async_session),
):
    """Prepare a presentation with outlines and layout."""
    handler = PresentationHandler(sql_session)
    return await handler.prepare_presentation(
        presentation_id=presentation_id,
        outlines=outlines,
        layout=layout,
        title=title
    )


@PRESENTATION_ROUTER.get("/stream", response_model=PresentationWithSlides)
async def stream_presentation(
    presentation_id: str, sql_session: AsyncSession = Depends(get_async_session)
):
    """Stream presentation generation with real-time updates."""
    handler = PresentationHandler(sql_session)
    generator = handler.stream_presentation_generator(presentation_id)
    return handler.create_streaming_response(generator)


@PRESENTATION_ROUTER.put("/update", response_model=PresentationWithSlides)
async def update_presentation(
    presentation_with_slides: Annotated[PresentationWithSlides, Body()],
    sql_session: AsyncSession = Depends(get_async_session),
):
    """Update a presentation and its slides."""
    handler = PresentationHandler(sql_session)
    return await handler.update_presentation(presentation_with_slides)


@PRESENTATION_ROUTER.post("/export/pptx", response_model=str)
async def create_pptx(
    pptx_model: Annotated[PptxPresentationModel, Body()],
):
    """Export presentation as PPTX file."""
    # Create temporary handler for PPTX export (doesn't need database session)
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from utils.db_utils import get_database_url_and_connect_args
    
    database_url, connect_args = get_database_url_and_connect_args()
    engine = create_async_engine(database_url, connect_args=connect_args)
    async with AsyncSession(engine) as session:
        handler = PresentationHandler(session)
        return await handler.create_pptx_export(pptx_model)


@PRESENTATION_ROUTER.post("/generate", response_model=PresentationPathAndEditPath)
async def generate_presentation_api(
    request: GeneratePresentationRequest,
    sql_session: AsyncSession = Depends(get_async_session),
):
    """Generate a complete presentation from request."""
    handler = PresentationHandler(sql_session)
    result = await handler.generate_complete_presentation(request)
    return PresentationPathAndEditPath(**result)


@PRESENTATION_ROUTER.post("/from-template", response_model=PresentationPathAndEditPath)
async def from_template(
    data: Annotated[GetPresentationUsingTemplateRequest, Body()],
    sql_session: AsyncSession = Depends(get_async_session),
):
    """Create presentation from template."""
    handler = PresentationHandler(sql_session)
    result = await handler.create_from_template(data)
    return PresentationPathAndEditPath(**result)