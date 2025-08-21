from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import get_async_session
from handlers.pdf_slides_handler import PdfSlidesHandler


PDF_SLIDES_ROUTER = APIRouter(prefix="/pdf-slides", tags=["PDF Slides"])


class PdfSlideData(BaseModel):
    slide_number: int
    screenshot_url: str


class PdfSlidesResponse(BaseModel):
    success: bool
    slides: List[PdfSlideData]
    total_slides: int


@PDF_SLIDES_ROUTER.post("/process", response_model=PdfSlidesResponse)
async def process_pdf_slides(
    pdf_file: UploadFile = File(..., description="PDF file to process"),
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Process a PDF file to extract slide screenshots."""
    handler = PdfSlidesHandler(sql_session)
    result = await handler.process_pdf_slides(pdf_file)
    
    # Convert to response model
    slides_data = []
    for slide in result["slides"]:
        slides_data.append(PdfSlideData(
            slide_number=slide["slide_number"],
            screenshot_url=slide["screenshot_url"]
        ))
    
    return PdfSlidesResponse(
        success=result["success"],
        slides=slides_data,
        total_slides=result["total_slides"]
    )


# All helper functions have been moved to PdfSlidesHandler for better organization and logging