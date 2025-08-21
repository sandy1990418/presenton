import asyncio
from typing import Annotated, List, Optional
from fastapi import APIRouter, Body, File, UploadFile, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models.decomposed_file_info import DecomposedFileInfo
from services.database import get_async_session
from handlers.files_handler import FilesHandler

FILES_ROUTER = APIRouter(prefix="/files", tags=["Files"])


@FILES_ROUTER.post("/upload", response_model=List[str])
async def upload_files(
    files: Optional[List[UploadFile]],
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Upload files and save them to temporary directory."""
    handler = FilesHandler(sql_session)
    return await handler.upload_files(files)


@FILES_ROUTER.post("/decompose", response_model=List[DecomposedFileInfo])
async def decompose_files(
    file_paths: Annotated[List[str], Body(embed=True)],
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Decompose files into text format for processing."""
    handler = FilesHandler(sql_session)
    return await handler.decompose_files(file_paths)


@FILES_ROUTER.post("/update")
async def update_files(
    file_path: Annotated[str, Body()],
    file: Annotated[UploadFile, File()],
    sql_session: AsyncSession = Depends(get_async_session)
):
    """Update an existing file with new content."""
    handler = FilesHandler(sql_session)
    return await handler.update_file(file_path, file)


# All helper functions and business logic have been moved to FilesHandler