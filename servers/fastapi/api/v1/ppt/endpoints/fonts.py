from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, File, UploadFile, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import get_async_session
from handlers.fonts_handler import FontsHandler

FONTS_ROUTER = APIRouter(prefix="/fonts", tags=["fonts"])


class FontUploadResponse(BaseModel):
    success: bool
    font_name: str
    font_url: str
    font_path: str
    message: Optional[str] = None


class FontListResponse(BaseModel):
    success: bool
    fonts: List[Dict]
    message: Optional[str] = None


@FONTS_ROUTER.post("/upload", response_model=FontUploadResponse)
async def upload_font(
    font_file: UploadFile = File(..., description="Font file to upload (.ttf, .otf, .woff, .woff2, .eot)"),
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Upload a font file and save it to the fonts directory."""
    handler = FontsHandler(sql_session)
    result = await handler.upload_font(font_file)
    
    return FontUploadResponse(
        success=result["success"],
        font_name=result["font_name"],
        font_url=result["font_url"],
        font_path=result["font_path"],
        message=result["message"]
    )


@FONTS_ROUTER.get("/list", response_model=FontListResponse)
async def list_fonts(sql_session: AsyncSession = Depends(get_async_session)):
    """List all uploaded fonts with their accessible URLs."""
    handler = FontsHandler(sql_session)
    result = await handler.list_fonts()
    
    return FontListResponse(
        success=result["success"],
        fonts=result["fonts"],
        message=result["message"]
    )


@FONTS_ROUTER.delete("/delete/{filename}")
async def delete_font(
    filename: str,
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Delete a font file."""
    handler = FontsHandler(sql_session)
    result = await handler.delete_font(filename)
    
    return {
        "success": result["success"],
        "message": result["message"]
    }


# All helper functions have been moved to FontsHandler for better organization and logging