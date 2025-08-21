from typing import List, Optional, Dict
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import get_async_session
from handlers.pptx_slides_handler import PptxSlidesHandler


PPTX_SLIDES_ROUTER = APIRouter(prefix="/pptx-slides", tags=["PPTX Slides"])


class SlideData(BaseModel):
    slide_number: int
    screenshot_url: str
    xml_content: str
    normalized_fonts: List[str]


class FontAnalysisResult(BaseModel):
    internally_supported_fonts: List[Dict[str, str]]  # [{"name": "Open Sans", "google_fonts_url": "..."}]
    not_supported_fonts: List[str]  # ["Custom Font Name"]


class PptxSlidesResponse(BaseModel):
    success: bool
    slides: List[SlideData]
    total_slides: int
    fonts: Optional[FontAnalysisResult] = None

# NEW: Fonts-only router and response for PPTX
class PptxFontsResponse(BaseModel):
    success: bool
    fonts: FontAnalysisResult

PPTX_FONTS_ROUTER = APIRouter(prefix="/pptx-fonts", tags=["PPTX Fonts"])











@PPTX_SLIDES_ROUTER.post("/process", response_model=PptxSlidesResponse)
async def process_pptx_slides(
    pptx_file: UploadFile = File(..., description="PPTX file to process"),
    fonts: Optional[List[UploadFile]] = File(None, description="Optional font files"),
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Process a PPTX file to extract slide screenshots and XML content."""
    handler = PptxSlidesHandler(sql_session)
    result = await handler.process_pptx_slides(pptx_file, fonts)
    
    # Convert to response model
    slides_data = []
    for slide in result["slides"]:
        slides_data.append(SlideData(
            slide_number=slide["slide_number"],
            screenshot_url=slide["screenshot_url"],
            xml_content=slide["xml_content"],
            normalized_fonts=slide["normalized_fonts"]
        ))
    
    return PptxSlidesResponse(
        success=result["success"],
        slides=slides_data,
        total_slides=result["total_slides"],
        fonts=FontAnalysisResult(
            internally_supported_fonts=result["fonts"]["internally_supported_fonts"],
            not_supported_fonts=result["fonts"]["not_supported_fonts"]
        )
    )

# NEW: Fonts-only endpoint leveraging the same font extraction/analysis
@PPTX_FONTS_ROUTER.post("/process", response_model=PptxFontsResponse)
async def process_pptx_fonts(
    pptx_file: UploadFile = File(..., description="PPTX file to analyze fonts from"),
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Analyze a PPTX file and return only the fonts used in the document."""
    handler = PptxSlidesHandler(sql_session)
    result = await handler.process_pptx_fonts(pptx_file)
    
    return PptxFontsResponse(
        success=result["success"],
        fonts=FontAnalysisResult(
            internally_supported_fonts=result["fonts"]["internally_supported_fonts"],
            not_supported_fonts=result["fonts"]["not_supported_fonts"]
        )
    )

# All helper functions have been moved to PptxSlidesHandler for better organization and logging