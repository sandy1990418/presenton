"""
PdfSlidesHandler contains all business logic for PDF slide processing operations.
Uses mixins for common functionality like database operations, logging, and validation.
"""

import os
import shutil
import tempfile
import subprocess
from typing import List, Dict

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from utils.asset_directory_utils import get_images_directory
from utils.randomizers import get_random_uuid
from constants.documents import PDF_MIME_TYPES

# Mixins
from mixins import DatabaseMixin, ValidationMixin


class PdfSlidesHandler(DatabaseMixin, ValidationMixin):
    """Handler for all PDF slide processing operations."""
    
    def __init__(self, sql_session: AsyncSession):
        super().__init__(sql_session)
        self.log_request_start("handler_initialization", handler="PdfSlidesHandler")
    
    async def _generate_pdf_screenshots(self, pdf_path: str, temp_dir: str) -> List[str]:
        """Generate PNG screenshots of PDF pages using ImageMagick."""
        self.log_external_service_call("ImageMagick", "generate_pdf_screenshots", pdf_path=pdf_path)
        
        try:
            screenshots_dir = os.path.join(temp_dir, "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            
            # Convert PDF to individual PNG images using ImageMagick
            self.logger.debug("Starting ImageMagick PNG conversion")
            try:
                result = subprocess.run([
                    "convert",
                    "-density", "150",  # Same DPI as PPTX endpoint
                    pdf_path,
                    os.path.join(screenshots_dir, "slide_%03d.png")
                ], check=True, capture_output=True, text=True, timeout=500)
                
                if result.stdout:
                    self.logger.debug("ImageMagick conversion output", output=result.stdout)
                if result.stderr:
                    self.logger.debug("ImageMagick conversion warnings", warnings=result.stderr)
                    
            except subprocess.TimeoutExpired:
                self.log_external_service_error("ImageMagick", "generate_screenshots", "Process timeout")
                raise HTTPException(status_code=500, detail="ImageMagick PNG conversion timed out after 500 seconds")
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else str(e)
                self.log_external_service_error("ImageMagick", "generate_screenshots", error_msg)
                raise HTTPException(status_code=500, detail=f"ImageMagick PNG conversion failed: {error_msg}")
            
            # Find generated PNG files
            self.logger.debug("Checking for generated PNG files")
            png_files = sorted([f for f in os.listdir(screenshots_dir) if f.startswith("slide_") and f.endswith('.png')])
            self.logger.info("Generated PNG files", files=png_files, count=len(png_files))
            
            if not png_files:
                self.log_external_service_error("ImageMagick", "generate_screenshots", "No PNG files generated")
                raise HTTPException(status_code=500, detail="ImageMagick failed to generate any PNG files")
            
            # Determine page count from generated files
            page_count = len(png_files)
            self.logger.info("Determined page count from ImageMagick output", page_count=page_count)
            
            # Rename files from slide_000.png format to slide_1.png format expected by the API
            self.logger.debug("Renaming PNG files to expected format")
            screenshot_paths = []
            for i in range(page_count):
                # ImageMagick generates slide_000.png, slide_001.png, etc.
                source_file = f"slide_{i:03d}.png"
                source_path = os.path.join(screenshots_dir, source_file)
                
                # We need slide_1.png, slide_2.png, etc.
                target_file = f"slide_{i+1}.png"
                target_path = os.path.join(screenshots_dir, target_file)
                
                if os.path.exists(source_path):
                    # Rename to expected format
                    shutil.move(source_path, target_path)
                    screenshot_paths.append(target_path)
                    self.logger.debug("Renamed screenshot file", source=source_file, target=target_file)
                else:
                    self.logger.warning("Expected screenshot file not found, creating placeholder", 
                                      expected=source_file)
                    # Create empty placeholder
                    with open(target_path, 'w') as f:
                        f.write("")
                    screenshot_paths.append(target_path)
            
            self.logger.info("Generated PDF page screenshots", count=len(screenshot_paths))
            return screenshot_paths
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_external_service_error("ImageMagick", "generate_screenshots", str(e))
            # Re-raise the specific exceptions we've already handled
            if "timed out" in str(e) or "failed:" in str(e):
                raise HTTPException(status_code=500, detail=str(e))
            # Handle any other unexpected exceptions
            raise HTTPException(status_code=500, detail=f"PDF screenshot generation failed: {str(e)}")
    
    async def process_pdf_slides(self, pdf_file: UploadFile) -> Dict[str, any]:
        """
        Process a PDF file to extract slide screenshots.
        
        Args:
            pdf_file: PDF file to process
            
        Returns:
            Dictionary with slides data and total count
        """
        self.log_request_start("process_pdf_slides", filename=pdf_file.filename)
        
        try:
            # Validate PDF file
            if pdf_file.content_type not in PDF_MIME_TYPES:
                self.log_validation_error("pdf_file", "invalid_type", 
                                        f"Expected PDF file, got {pdf_file.content_type}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type. Expected PDF file, got {pdf_file.content_type}"
                )
            
            # Enforce 100MB size limit
            if hasattr(pdf_file, "size") and pdf_file.size and pdf_file.size > (100 * 1024 * 1024):
                self.log_validation_error("pdf_file", "size_exceeded", f"File size: {pdf_file.size}")
                raise HTTPException(
                    status_code=400,
                    detail="PDF file exceeded max upload size of 100 MB",
                )
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save uploaded PDF file
                pdf_path = os.path.join(temp_dir, "presentation.pdf")
                with open(pdf_path, "wb") as f:
                    pdf_content = await pdf_file.read()
                    f.write(pdf_content)
                
                # Generate screenshots from PDF using ImageMagick
                screenshot_paths = await self._generate_pdf_screenshots(pdf_path, temp_dir)
                self.logger.info("Generated PDF screenshots", count=len(screenshot_paths))
                
                # Move screenshots to images directory and generate URLs
                images_dir = get_images_directory()
                presentation_id = get_random_uuid()
                presentation_images_dir = os.path.join(images_dir, presentation_id)
                os.makedirs(presentation_images_dir, exist_ok=True)
                
                slides_data = []
                
                for i, screenshot_path in enumerate(screenshot_paths, 1):
                    # Move screenshot to permanent location
                    screenshot_filename = f"slide_{i}.png"
                    permanent_screenshot_path = os.path.join(presentation_images_dir, screenshot_filename)
                    
                    if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                        # Use shutil.copy2 instead of os.rename to handle cross-device moves
                        shutil.copy2(screenshot_path, permanent_screenshot_path)
                        screenshot_url = f"/app_data/images/{presentation_id}/{screenshot_filename}"
                    else:
                        # Fallback if screenshot generation failed or file is empty placeholder
                        screenshot_url = "/static/images/placeholder.jpg"
                    
                    slides_data.append({
                        "slide_number": i,
                        "screenshot_url": screenshot_url
                    })
                
                self.log_request_success("process_pdf_slides", 
                                       filename=pdf_file.filename,
                                       slides_processed=len(slides_data))
                
                return {
                    "success": True,
                    "slides": slides_data,
                    "total_slides": len(slides_data)
                }
                
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("process_pdf_slides", e, filename=pdf_file.filename)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process PDF: {str(e)}"
            )