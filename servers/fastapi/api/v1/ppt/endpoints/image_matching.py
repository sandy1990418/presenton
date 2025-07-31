"""
Image Matching API Endpoints

Handles intelligent image placement based on semantic similarity
between extracted images and presentation content.
"""

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json
import base64

from services.database import get_async_session
from services.image_embedding_service import ImageEmbeddingService
from models.sql.presentation import PresentationModel
from utils.asset_directory_utils import get_images_directory

logger = logging.getLogger(__name__)

IMAGE_MATCHING_ROUTER = APIRouter(prefix="/image-matching", tags=["Image Matching"])

# Initialize the embedding service
image_embedding_service = ImageEmbeddingService()

@IMAGE_MATCHING_ROUTER.post("/process-extracted-images")
async def process_extracted_images(
    presentation_id: str = Form(...),
    images_data: str = Form(...),  # JSON string of extracted images
    sql_session: AsyncSession = Depends(get_async_session)
):
    """
    Process extracted images and match them to presentation slides
    """
    try:
        # Get presentation
        presentation = await sql_session.get(PresentationModel, presentation_id)
        if not presentation:
            raise HTTPException(status_code=404, detail="Presentation not found")
        
        # Parse images data
        try:
            images_list = json.loads(images_data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid images data format")
        
        if not images_list:
            return JSONResponse({
                "success": True,
                "message": "No images to process",
                "matches": []
            })
        
        # Initialize embedding service if needed
        if not image_embedding_service.model_loaded:
            await image_embedding_service.initialize_models()
        
        # Process extracted images
        processed_images = await image_embedding_service.process_extracted_images(images_list)
        
        if not processed_images:
            return JSONResponse({
                "success": True,
                "message": "No images could be processed",
                "matches": []
            })
        
        # Get slide outlines
        slide_outlines = presentation.outlines or []
        
        if not slide_outlines:
            return JSONResponse({
                "success": True,
                "message": "No slide outlines available for matching",
                "matches": []
            })
        
        # Match images to slides
        image_matches = await image_embedding_service.match_images_to_slides(
            processed_images, slide_outlines
        )
        
        # Optimize distribution
        optimized_matches = await image_embedding_service.optimize_image_distribution(image_matches)
        
        # Convert matches to serializable format
        serialized_matches = []
        for match in optimized_matches:
            serialized_matches.append({
                "slideIndex": match.slide_index,
                "slideTitle": match.slide_title,
                "imageData": {
                    "fileName": match.image_data.get("fileName"),
                    "imageSrc": match.image_data.get("imageSrc"),
                    "contextText": match.image_data.get("contextText"),
                    "position": match.image_data.get("position"),
                    "altText": match.image_data.get("altText"),
                    "caption": match.image_data.get("caption")
                },
                "similarityScore": float(match.similarity_score),
                "placementSuggestion": match.placement_suggestion,
                "confidence": float(match.confidence)
            })
        
        logger.info(f"Successfully matched {len(optimized_matches)} images to slides")
        
        return JSONResponse({
            "success": True,
            "message": f"Successfully processed {len(images_list)} images and found {len(optimized_matches)} matches",
            "matches": serialized_matches,
            "totalImagesProcessed": len(images_list),
            "totalMatches": len(optimized_matches)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing extracted images: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to process extracted images: {str(e)}"
        )

@IMAGE_MATCHING_ROUTER.post("/upload-image-blobs")
async def upload_image_blobs(
    presentation_id: str = Form(...),
    image_files: List[UploadFile] = File(...),
    sql_session: AsyncSession = Depends(get_async_session)
):
    """
    Upload image blobs extracted from documents
    """
    try:
        # Get presentation
        presentation = await sql_session.get(PresentationModel, presentation_id)
        if not presentation:
            raise HTTPException(status_code=404, detail="Presentation not found")
        
        uploaded_files = []
        images_dir = get_images_directory()
        
        for i, file in enumerate(image_files):
            try:
                # Generate unique filename
                file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'png'
                unique_filename = f"{presentation_id}_extracted_{i}.{file_extension}"
                file_path = f"{images_dir}/{unique_filename}"
                
                # Save file
                content = await file.read()
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                uploaded_files.append({
                    "originalName": file.filename,
                    "savedName": unique_filename,
                    "path": file_path,
                    "size": len(content)
                })
                
            except Exception as e:
                logger.error(f"Failed to upload image {file.filename}: {e}")
        
        return JSONResponse({
            "success": True,
            "message": f"Successfully uploaded {len(uploaded_files)} images",
            "uploadedFiles": uploaded_files
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading image blobs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload image blobs: {str(e)}"
        )

@IMAGE_MATCHING_ROUTER.get("/embedding-status")
async def get_embedding_status():
    """
    Get the status of the embedding service
    """
    try:
        if not image_embedding_service.model_loaded:
            await image_embedding_service.initialize_models()
        
        # Determine AI provider and method
        model_name = "Keyword-based fallback"
        ai_provider = "Fallback"
        embedding_method = "keyword"
        
        if image_embedding_service.model_loaded:
            if image_embedding_service.text_model == "gemini":
                model_name = "Gemini AI (keyword fallback)"
                ai_provider = "Google Gemini"
                embedding_method = "keyword"
            elif image_embedding_service.text_model:
                model_name = "OpenAI text-embedding-3-small"
                ai_provider = "OpenAI"
                embedding_method = "semantic_embeddings"
        
        return JSONResponse({
            "success": True,
            "modelLoaded": image_embedding_service.model_loaded,
            "modelName": model_name,
            "aiProvider": ai_provider,
            "embeddingMethod": embedding_method
        })
        
    except Exception as e:
        logger.error(f"Error checking embedding status: {e}")
        return JSONResponse({
            "success": False,
            "modelLoaded": False,
            "modelName": "Error - using fallback",
            "aiProvider": "Fallback",
            "embeddingMethod": "keyword",
            "error": str(e)
        })

@IMAGE_MATCHING_ROUTER.post("/match-single-image")
async def match_single_image(
    presentation_id: str = Form(...),
    image_data: str = Form(...),  # JSON string of single image data
    sql_session: AsyncSession = Depends(get_async_session)
):
    """
    Match a single image to the best slide
    """
    try:
        # Get presentation
        presentation = await sql_session.get(PresentationModel, presentation_id)
        if not presentation:
            raise HTTPException(status_code=404, detail="Presentation not found")
        
        # Parse image data
        try:
            image_info = json.loads(image_data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid image data format")
        
        # Initialize embedding service if needed
        if not image_embedding_service.model_loaded:
            await image_embedding_service.initialize_models()
        
        # Process single image
        processed_images = await image_embedding_service.process_extracted_images([image_info])
        
        if not processed_images:
            raise HTTPException(status_code=400, detail="Failed to process image")
        
        # Get slide outlines
        slide_outlines = presentation.outlines or []
        
        if not slide_outlines:
            raise HTTPException(status_code=400, detail="No slide outlines available")
        
        # Match image to slides
        matches = await image_embedding_service.match_images_to_slides(
            processed_images, slide_outlines
        )
        
        if not matches:
            return JSONResponse({
                "success": True,
                "message": "No suitable matches found",
                "match": None
            })
        
        # Return best match
        best_match = matches[0]
        
        return JSONResponse({
            "success": True,
            "message": "Successfully matched image",
            "match": {
                "slideIndex": best_match.slide_index,
                "slideTitle": best_match.slide_title,
                "similarityScore": float(best_match.similarity_score),
                "placementSuggestion": best_match.placement_suggestion,
                "confidence": float(best_match.confidence)
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error matching single image: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to match image: {str(e)}"
        )