from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import get_async_session
from handlers.slide_to_html_handler import SlideToHtmlHandler


# Create separate routers for each functionality
SLIDE_TO_HTML_ROUTER = APIRouter(prefix="/slide-to-html", tags=["slide-to-html"])
HTML_TO_REACT_ROUTER = APIRouter(prefix="/html-to-react", tags=["html-to-react"])
HTML_EDIT_ROUTER = APIRouter(prefix="/html-edit", tags=["html-edit"])
LAYOUT_MANAGEMENT_ROUTER = APIRouter(prefix="/template-management", tags=["template-management"])


# Request/Response models for slide-to-html endpoint
class SlideToHtmlRequest(BaseModel):
    image: str  # Partial path to image file (e.g., "/app_data/images/uuid/slide_1.png")
    xml: str    # OXML content as text
    fonts: Optional[List[str]] = None  # Optional normalized root fonts for this slide


class SlideToHtmlResponse(BaseModel):
    success: bool
    html: str


# Request/Response models for html-edit endpoint
class HtmlEditResponse(BaseModel):
    success: bool
    edited_html: str
    message: Optional[str] = None


# Request/Response models for html-to-react endpoint
class HtmlToReactRequest(BaseModel):
    html: str   # HTML content to convert to React component
    image: Optional[str] = None  # Optional image path to provide visual context


class HtmlToReactResponse(BaseModel):
    success: bool
    react_component: str
    message: Optional[str] = None


# Request/Response models for layout management endpoints
class LayoutData(BaseModel):
    presentation_id: str  # UUID of the presentation
    layout_id: str        # Unique identifier for the layout
    layout_name: str      # Display name of the layout
    layout_code: str      # TSX/React component code for the layout
    fonts: Optional[List[str]] = None  # Optional list of font links


class SaveLayoutsRequest(BaseModel):
    layouts: list[LayoutData]


class SaveLayoutsResponse(BaseModel):
    success: bool
    saved_count: int
    message: Optional[str] = None


class GetLayoutsResponse(BaseModel):
    success: bool
    layouts: list[LayoutData]
    message: Optional[str] = None
    template: Optional[dict] = None
    fonts: Optional[List[str]] = None


class PresentationSummary(BaseModel):
    presentation_id: str
    layout_count: int
    last_updated_at: Optional[datetime] = None
    template: Optional[dict] = None


class GetPresentationSummaryResponse(BaseModel):
    success: bool
    presentations: List[PresentationSummary]
    total_presentations: int
    total_layouts: int
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    detail: str
    error_code: Optional[str] = None


class TemplateCreateRequest(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class TemplateCreateResponse(BaseModel):
    success: bool
    template: dict
    message: Optional[str] = None


class TemplateInfo(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None


# ENDPOINT 1: Slide to HTML conversion
@SLIDE_TO_HTML_ROUTER.post("/", response_model=SlideToHtmlResponse)
async def convert_slide_to_html(
    request: SlideToHtmlRequest, 
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Convert a slide image and its OXML data to HTML."""
    handler = SlideToHtmlHandler(sql_session)
    html_content = await handler.convert_slide_to_html(
        image_path=request.image,
        xml_content=request.xml,
        fonts=request.fonts
    )
    return SlideToHtmlResponse(success=True, html=html_content)


# ENDPOINT 2: HTML to React component conversion
@HTML_TO_REACT_ROUTER.post("/", response_model=HtmlToReactResponse)
async def convert_html_to_react(
    request: HtmlToReactRequest,
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Convert HTML content to TSX React component."""
    handler = SlideToHtmlHandler(sql_session)
    react_component = await handler.convert_html_to_react(
        html_content=request.html,
        image_path=request.image
    )
    return HtmlToReactResponse(
        success=True,
        react_component=react_component,
        message="React component generated successfully"
    )


# ENDPOINT 3: HTML editing with images
@HTML_EDIT_ROUTER.post("/", response_model=HtmlEditResponse)
async def edit_html_with_images_endpoint(
    current_ui_image: UploadFile = File(..., description="Current UI image file"),
    sketch_image: Optional[UploadFile] = File(None, description="Sketch/indication image file (optional)"),
    html: str = Form(..., description="Current HTML content to edit"),
    prompt: str = Form(..., description="Text prompt describing the changes"),
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Edit HTML content based on uploaded images and text prompt."""
    handler = SlideToHtmlHandler(sql_session)
    edited_html = await handler.edit_html_with_uploaded_images(
        current_ui_image=current_ui_image,
        sketch_image=sketch_image,
        html_content=html,
        prompt=prompt
    )
    return HtmlEditResponse(
        success=True,
        edited_html=edited_html,
        message="HTML edited successfully"
    ) 


# ENDPOINT 4: Save layouts for a presentation
@LAYOUT_MANAGEMENT_ROUTER.post(
    "/save-templates", 
    response_model=SaveLayoutsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def save_layouts(
    request: SaveLayoutsRequest,
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Save multiple layouts for presentations."""
    if not request.layouts:
        raise HTTPException(status_code=400, detail="Layouts array cannot be empty")
    
    if len(request.layouts) > 50:
        raise HTTPException(status_code=400, detail="Cannot save more than 50 layouts at once")
    
    handler = SlideToHtmlHandler(sql_session)
    layouts_data = [layout.model_dump() for layout in request.layouts]
    saved_count, message = await handler.save_layouts(layouts_data)
    
    return SaveLayoutsResponse(
        success=True,
        saved_count=saved_count,
        message=message
    )


# ENDPOINT 5: Get layouts for a presentation
@LAYOUT_MANAGEMENT_ROUTER.get(
    "/get-templates/{presentation_id}", 
    response_model=GetLayoutsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid presentation ID"},
        404: {"model": ErrorResponse, "description": "No layouts found for presentation"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_layouts(
    presentation_id: str,
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Retrieve all layouts for a specific presentation."""
    handler = SlideToHtmlHandler(sql_session)
    layouts, template, fonts = await handler.get_layouts(presentation_id)
    
    if not layouts:
        raise HTTPException(
            status_code=404,
            detail=f"No layouts found for presentation ID: {presentation_id}"
        )
    
    # Convert to LayoutData objects for response
    layout_data = [
        LayoutData(
            presentation_id=layout["presentation_id"],
            layout_id=layout["layout_id"],
            layout_name=layout["layout_name"],
            layout_code=layout["layout_code"],
            fonts=layout.get("fonts")
        )
        for layout in layouts
    ]
    
    return GetLayoutsResponse(
        success=True,
        layouts=layout_data,
        message=f"Retrieved {len(layouts)} layout(s) for presentation {presentation_id}",
        template=template,
        fonts=fonts,
    )


# ENDPOINT 6: Get all presentations with layout counts
@LAYOUT_MANAGEMENT_ROUTER.get(
    "/summary",
    response_model=GetPresentationSummaryResponse,
    summary="Get all presentations with layout counts",
    description="Retrieve a summary of all presentations and the number of layouts in each",
    responses={
        200: {"model": GetPresentationSummaryResponse, "description": "Presentations summary retrieved successfully"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_presentations_summary(
    sql_session: AsyncSession = Depends(get_async_session),
):
    """Get summary of all presentations with their layout counts."""
    handler = SlideToHtmlHandler(sql_session)
    presentations_data, total_presentations, total_layouts = await handler.get_presentations_summary()
    
    # Convert to response format
    presentations = [
        PresentationSummary(
            presentation_id=p["presentation_id"],
            layout_count=p["layout_count"],
            last_updated_at=p.get("last_updated_at"),
            template=p.get("template")
        )
        for p in presentations_data
    ]
    
    return GetPresentationSummaryResponse(
        success=True,
        presentations=presentations,
        total_presentations=total_presentations,
        total_layouts=total_layouts,
        message=f"Retrieved {total_presentations} presentation(s) with {total_layouts} total layout(s)",
    ) 


# ENDPOINT 7: Create template
@LAYOUT_MANAGEMENT_ROUTER.post(
    "/templates",
    response_model=TemplateCreateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_template(
    request: TemplateCreateRequest,
    sql_session: AsyncSession = Depends(get_async_session),
):
    """Create or update a template."""
    handler = SlideToHtmlHandler(sql_session)
    template_dict = await handler.create_template(
        template_id=request.id,
        name=request.name,
        description=request.description
    )
    
    return TemplateCreateResponse(
        success=True,
        template=template_dict,
        message="Template saved",
    )


# All helper functions have been moved to SlideToHtmlHandler for better organization and logging