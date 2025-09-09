import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from utils.asset_directory_utils import get_exports_directory

DOWNLOAD_ROUTER = APIRouter(prefix="/download", tags=["Download"])


@DOWNLOAD_ROUTER.get("/{filename}")
async def download_file(filename: str):
    """Download a file from the exports directory"""
    export_directory = get_exports_directory()
    file_path = os.path.join(export_directory, filename)
    
    # Security check: ensure the file is within the exports directory
    if not os.path.abspath(file_path).startswith(os.path.abspath(export_directory)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine the media type based on file extension
    media_type = "application/octet-stream"
    if filename.endswith('.pptx'):
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif filename.endswith('.pdf'):
        media_type = "application/pdf"
    
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename
    )