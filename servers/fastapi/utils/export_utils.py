import json
import os
import aiohttp
from typing import Literal
from fastapi import HTTPException
from pathvalidate import sanitize_filename

from models.pptx_models import PptxPresentationModel
from models.presentation_and_path import PresentationAndPath
from services.pptx_presentation_creator import PptxPresentationCreator
from services import TEMP_FILE_SERVICE
from utils.asset_directory_utils import get_exports_directory
from utils.randomizers import get_random_uuid


async def export_presentation(
    presentation_id: str, title: str, export_as: Literal["pptx", "pdf"]
) -> PresentationAndPath:
    if export_as == "pptx":

        # Get the converted PPTX model from the Next.js service
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://localhost:3000/api/presentation_to_pptx_model?id={presentation_id}"
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Failed to get PPTX model: {error_text}")
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to convert presentation to PPTX model",
                    )
                pptx_model_data = await response.json()

        # Create PPTX file using the converted model
        pptx_model = PptxPresentationModel(**pptx_model_data)
        temp_dir = TEMP_FILE_SERVICE.create_temp_dir()
        pptx_creator = PptxPresentationCreator(pptx_model, temp_dir)
        await pptx_creator.create_ppt()

        export_directory = get_exports_directory()
        sanitized_title = sanitize_filename(title or get_random_uuid()).replace(' ', '_')
        pptx_path = os.path.join(
            export_directory,
            f"{sanitized_title}.pptx",
        )
        pptx_creator.save(pptx_path)

        # Return download URL instead of file path
        filename = os.path.basename(pptx_path)
        download_url = f"/api/download/{filename}"
        
        return PresentationAndPath(
            presentation_id=presentation_id,
            path=download_url,
        )
    else:
        sanitized_title = sanitize_filename(title or get_random_uuid()).replace(' ', '_')
        pdf_filename = f"{sanitized_title}.pdf"
        export_directory = get_exports_directory()
        pdf_path = os.path.join(export_directory, pdf_filename)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:3000/api/export-as-pdf",
                json={
                    "id": presentation_id,
                    "title": title or "presentation",
                },
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Failed to export PDF: {error_text}")
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to export presentation as PDF",
                    )
                
                # The response is now JSON with the download URL
                response_json = await response.json()
                download_url = response_json["path"]
        
        return PresentationAndPath(
            presentation_id=presentation_id,
            path=download_url,
        )
