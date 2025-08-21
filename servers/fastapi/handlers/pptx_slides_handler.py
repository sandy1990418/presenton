"""
PptxSlidesHandler contains all business logic for PPTX slide processing and font analysis operations.
Uses mixins for common functionality like database operations, logging, and validation.
"""

import os
import shutil
import zipfile
import tempfile
import subprocess
import uuid
from typing import List, Optional, Dict, Tuple

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
import aiohttp
import asyncio
import xml.etree.ElementTree as ET
import re

from utils.asset_directory_utils import get_images_directory
from utils.randomizers import get_random_uuid
from constants.documents import POWERPOINT_TYPES

# Mixins
from mixins import DatabaseMixin, ValidationMixin


class PptxSlidesHandler(DatabaseMixin, ValidationMixin):
    """Handler for all PPTX slide processing and font analysis operations."""
    
    def __init__(self, sql_session: AsyncSession):
        super().__init__(sql_session)
        self.log_request_start("handler_initialization", handler="PptxSlidesHandler")
    
    # Font normalization constants
    _STYLE_TOKENS = {
        # styles
        "italic", "italics", "ital", "oblique", "roman",
        # combined style shortcuts
        "bolditalic", "bolditalics",
        # weights
        "thin", "hairline", "extralight", "ultralight", "light", "demilight", "semilight", "book",
        "regular", "normal", "medium", "semibold", "demibold", "bold", "extrabold", "ultrabold",
        "black", "extrablack", "ultrablack", "heavy",
        # width/stretch
        "narrow", "condensed", "semicondensed", "extracondensed", "ultracondensed",
        "expanded", "semiexpanded", "extraexpanded", "ultraexpanded",
    }
    _STYLE_MODIFIERS = {"semi", "demi", "extra", "ultra"}
    
    def _insert_spaces_in_camel_case(self, value: str) -> str:
        """Insert spaces in camel case strings."""
        # Insert space before capital letters preceded by lowercase or digits
        value = re.sub(r"(?<=[a-z0-9])([A-Z])", r" \\1", value)
        # Handle sequences like BoldItalic -> Bold Italic
        value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\\1 \\2", value)
        return value
    
    def normalize_font_family_name(self, raw_name: str) -> str:
        """Normalize font family names by removing style/weight descriptors."""
        if not raw_name:
            return raw_name
        
        # Replace separators with spaces
        name = raw_name.replace("_", " ").replace("-", " ")
        # Insert spaces in camel case
        name = self._insert_spaces_in_camel_case(name)
        # Collapse multiple spaces
        name = re.sub(r"\\s+", " ", name).strip()
        # Lowercase helper for matching but keep original casing for output
        lower_name = name.lower()
        
        # Quick cut: if the full string ends with a pure style suffix, trim it
        for style in sorted(self._STYLE_TOKENS, key=len, reverse=True):
            if lower_name.endswith(" " + style):
                name = name[: -(len(style) + 1)]
                lower_name = lower_name[: -(len(style) + 1)]
                break
        
        # Tokenize
        tokens_original = name.split(" ")
        tokens_filtered: List[str] = []
        for index, tok in enumerate(tokens_original):
            lower_tok = tok.lower()
            # Always keep the first token to avoid stripping families like "Black Ops One"
            if index == 0:
                tokens_filtered.append(tok)
                continue
            # Drop style tokens and standalone modifiers
            if lower_tok in self._STYLE_TOKENS or lower_tok in self._STYLE_MODIFIERS:
                continue
            tokens_filtered.append(tok)
        
        return " ".join(tokens_filtered).strip()
    
    def extract_fonts_from_oxml(self, oxml_content: str) -> List[str]:
        """Extract font names from OXML content."""
        try:
            # Parse the XML content
            root = ET.fromstring(oxml_content)
            font_names = set()
            
            # Look for font references in the XML
            # PowerPoint XML typically uses typeface attributes
            for elem in root.iter():
                # Check for typeface attribute
                typeface = elem.get('typeface')
                if typeface and typeface not in ['+mn-lt', '+mj-lt', '+mn-ea', '+mj-ea', '+mn-cs', '+mj-cs']:
                    font_names.add(typeface)
                
                # Check for other font-related attributes
                for attr_name, attr_value in elem.attrib.items():
                    if 'font' in attr_name.lower() and attr_value:
                        font_names.add(attr_value)
            
            return list(font_names)
            
        except ET.XMLSyntaxError as e:
            self.logger.warning("Failed to parse OXML content", error=str(e))
            return []
        except Exception as e:
            self.logger.exception("Error extracting fonts from OXML")
            return []
    
    async def check_google_font_availability(self, font_name: str) -> bool:
        """Check if a font is available on Google Fonts."""
        self.log_external_service_call("GoogleFonts", "check_availability", font_name=font_name)
        
        try:
            # Check Google Fonts API for font availability
            url = f"https://fonts.googleapis.com/css?family={font_name.replace(' ', '+')}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        # If the response contains font-face definitions, the font exists
                        return "@font-face" in content
                    return False
                    
        except Exception as e:
            self.logger.exception("Error checking Google Font availability", font_name=font_name)
            return False
    
    async def analyze_fonts_in_all_slides(self, slide_xmls: List[str]) -> Dict[str, any]:
        """Analyze fonts across all slides."""
        self.log_request_start("analyze_fonts_in_all_slides", slide_count=len(slide_xmls))
        
        try:
            all_raw_fonts = set()
            
            # Extract all fonts from all slides
            for xml_content in slide_xmls:
                slide_fonts = self.extract_fonts_from_oxml(xml_content)
                all_raw_fonts.update(slide_fonts)
            
            # Normalize font names
            normalized_fonts = {self.normalize_font_family_name(font) for font in all_raw_fonts if font}
            
            # Analyze each unique normalized font
            internally_supported_fonts = []
            not_supported_fonts = []
            
            for font_name in normalized_fonts:
                if await self.check_google_font_availability(font_name):
                    internally_supported_fonts.append({
                        "name": font_name,
                        "google_fonts_url": f"https://fonts.googleapis.com/css?family={font_name.replace(' ', '+')}"
                    })
                else:
                    not_supported_fonts.append(font_name)
            
            result = {
                "internally_supported_fonts": internally_supported_fonts,
                "not_supported_fonts": not_supported_fonts
            }
            
            self.log_request_success("analyze_fonts_in_all_slides", 
                                   supported_count=len(internally_supported_fonts),
                                   unsupported_count=len(not_supported_fonts))
            
            return result
            
        except Exception as e:
            self.log_request_error("analyze_fonts_in_all_slides", e, slide_count=len(slide_xmls))
            # Return empty result on error
            return {
                "internally_supported_fonts": [],
                "not_supported_fonts": []
            }
    
    def _extract_slide_xmls(self, pptx_path: str, temp_dir: str) -> List[str]:
        """Extract slide XML content from PPTX file."""
        try:
            slide_xmls = []
            
            with zipfile.ZipFile(pptx_path, 'r') as zip_ref:
                # Extract all files to temporary directory
                zip_ref.extractall(temp_dir)
                
                # Look for slide XML files
                slides_dir = os.path.join(temp_dir, "ppt", "slides")
                if os.path.exists(slides_dir):
                    # Get all slide XML files sorted by number
                    slide_files = [f for f in os.listdir(slides_dir) if f.startswith("slide") and f.endswith(".xml")]
                    slide_files.sort(key=lambda x: int(re.findall(r'\\d+', x)[0]) if re.findall(r'\\d+', x) else 0)
                    
                    for slide_file in slide_files:
                        slide_path = os.path.join(slides_dir, slide_file)
                        with open(slide_path, 'r', encoding='utf-8') as f:
                            slide_xmls.append(f.read())
            
            self.logger.info("Extracted slide XMLs", slide_count=len(slide_xmls))
            return slide_xmls
            
        except Exception as e:
            self.logger.exception("Failed to extract slide XMLs from PPTX", pptx_path=pptx_path)
            return []
    
    async def _install_fonts(self, fonts: List[UploadFile], temp_dir: str) -> None:
        """Install uploaded font files."""
        self.log_request_start("install_fonts", font_count=len(fonts))
        
        try:
            for font_file in fonts:
                if not font_file.filename:
                    continue
                    
                # Save font file to temp directory
                font_path = os.path.join(temp_dir, font_file.filename)
                
                with open(font_path, "wb") as f:
                    font_content = await font_file.read()
                    f.write(font_content)
                
                # Copy to system fonts directory (Linux)
                try:
                    fonts_dir = os.path.expanduser("~/.fonts")
                    os.makedirs(fonts_dir, exist_ok=True)
                    shutil.copy2(font_path, fonts_dir)
                    self.logger.debug("Installed font", filename=font_file.filename)
                except Exception as e:
                    self.logger.warning("Failed to install font", filename=font_file.filename, error=str(e))
            
            # Refresh font cache
            try:
                subprocess.run(["fc-cache", "-fv"], check=False, capture_output=True)
                self.logger.debug("Refreshed font cache")
            except Exception as e:
                self.logger.warning("Failed to refresh font cache", error=str(e))
                
        except Exception as e:
            self.log_request_error("install_fonts", e, font_count=len(fonts))
    
    async def _generate_screenshots(self, pptx_path: str, temp_dir: str) -> List[str]:
        """Generate slide screenshots using LibreOffice."""
        self.log_external_service_call("LibreOffice", "generate_screenshots", pptx_path=pptx_path)
        
        try:
            # Count slides in presentation
            slide_count = 0
            with zipfile.ZipFile(pptx_path, 'r') as zip_ref:
                slide_files = [name for name in zip_ref.namelist() 
                             if name.startswith('ppt/slides/slide') and name.endswith('.xml')]
                slide_count = len(slide_files)
            
            self.logger.info("Generating screenshots", slide_count=slide_count, pptx_path=pptx_path)
            
            # Convert PPTX to PDF using LibreOffice
            self.logger.debug("Starting LibreOffice PDF conversion")
            libreoffice_cmd = [
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", temp_dir, pptx_path
            ]
            
            result = subprocess.run(
                libreoffice_cmd,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.stdout:
                self.logger.debug("LibreOffice conversion output", output=result.stdout)
            if result.stderr:
                self.logger.debug("LibreOffice conversion warnings", warnings=result.stderr)
            
            # Find the generated PDF
            pdf_name = os.path.splitext(os.path.basename(pptx_path))[0] + ".pdf"
            pdf_path = os.path.join(temp_dir, pdf_name)
            actual_pdf_path = None
            
            # Check for PDF in temp directory
            for file in os.listdir(temp_dir):
                if file.endswith('.pdf'):
                    actual_pdf_path = os.path.join(temp_dir, file)
                    break
            
            if not actual_pdf_path or not os.path.exists(actual_pdf_path):
                raise Exception(f"LibreOffice failed to generate PDF from {pptx_path}")
            
            self.logger.info("Generated PDF", pdf_path=actual_pdf_path)
            
            # Convert PDF pages to PNG using ImageMagick
            self.logger.debug("Starting ImageMagick PNG conversion")
            convert_cmd = [
                "convert", "-density", "150", "-quality", "90",
                actual_pdf_path, os.path.join(temp_dir, "slide_%d.png")
            ]
            
            result = subprocess.run(
                convert_cmd,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.stdout:
                self.logger.debug("ImageMagick conversion output", output=result.stdout)
            if result.stderr:
                self.logger.debug("ImageMagick conversion warnings", warnings=result.stderr)
            
            # Check for generated PNG files
            self.logger.debug("Checking for generated PNG files")
            png_files = [f for f in os.listdir(temp_dir) if f.startswith("slide_") and f.endswith(".png")]
            png_files.sort()
            self.logger.info("Generated PNG files", files=png_files)
            
            # Rename files to expected format
            screenshot_paths = []
            self.logger.debug("Renaming PNG files to expected format")
            
            for i in range(1, slide_count + 1):
                # ImageMagick creates files like slide_0.png, slide_1.png, etc.
                source_file = os.path.join(temp_dir, f"slide_{i-1}.png")
                target_file = os.path.join(temp_dir, f"slide_{i}.png")
                
                if os.path.exists(source_file):
                    if source_file != target_file:
                        shutil.move(source_file, target_file)
                    screenshot_paths.append(target_file)
                    self.logger.debug("Renamed screenshot file", source=f"slide_{i-1}.png", target=f"slide_{i}.png")
                else:
                    # Create placeholder if file doesn't exist
                    self.logger.warning("Expected screenshot file not found, creating placeholder", expected=f"slide_{i-1}.png")
                    with open(target_file, 'w') as f:
                        f.write("")  # Empty placeholder file
                    screenshot_paths.append(target_file)
            
            self.logger.info("Generated slide screenshots", count=len(screenshot_paths))
            return screenshot_paths
            
        except subprocess.TimeoutExpired:
            self.log_external_service_error("LibreOffice", "generate_screenshots", "Process timeout")
            raise HTTPException(status_code=500, detail="Screenshot generation timed out")
        except Exception as e:
            self.log_external_service_error("LibreOffice", "generate_screenshots", str(e))
            raise HTTPException(status_code=500, detail=f"Failed to generate screenshots: {str(e)}")
    
    async def process_pptx_slides(
        self, 
        pptx_file: UploadFile, 
        fonts: Optional[List[UploadFile]] = None
    ) -> Dict[str, any]:
        """
        Process a PPTX file to extract slide screenshots and XML content.
        
        Args:
            pptx_file: PPTX file to process
            fonts: Optional font files to install
            
        Returns:
            Dictionary with slides data, total count, and font analysis
        """
        self.log_request_start("process_pptx_slides", filename=pptx_file.filename)
        
        try:
            # Validate PPTX file
            if pptx_file.content_type not in POWERPOINT_TYPES:
                self.log_validation_error("pptx_file", "invalid_type", 
                                        f"Expected PPTX file, got {pptx_file.content_type}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type. Expected PPTX file, got {pptx_file.content_type}"
                )
            
            # Enforce 100MB size limit
            if hasattr(pptx_file, "size") and pptx_file.size and pptx_file.size > (100 * 1024 * 1024):
                self.log_validation_error("pptx_file", "size_exceeded", f"File size: {pptx_file.size}")
                raise HTTPException(
                    status_code=400,
                    detail="PPTX file exceeded max upload size of 100 MB",
                )
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save uploaded PPTX file
                pptx_path = os.path.join(temp_dir, "presentation.pptx")
                with open(pptx_path, "wb") as f:
                    pptx_content = await pptx_file.read()
                    f.write(pptx_content)
                
                # Install fonts if provided
                if fonts:
                    await self._install_fonts(fonts, temp_dir)
                
                # Extract slide XMLs from PPTX
                slide_xmls = self._extract_slide_xmls(pptx_path, temp_dir)
                
                # Generate screenshots using LibreOffice
                screenshot_paths = await self._generate_screenshots(pptx_path, temp_dir)
                self.logger.info("Generated screenshots", count=len(screenshot_paths))
                
                # Analyze fonts across all slides
                font_analysis = await self.analyze_fonts_in_all_slides(slide_xmls)
                self.logger.info("Font analysis completed", 
                               supported=len(font_analysis["internally_supported_fonts"]),
                               unsupported=len(font_analysis["not_supported_fonts"]))
                
                # Move screenshots to images directory and generate URLs
                images_dir = get_images_directory()
                presentation_id = get_random_uuid()
                presentation_images_dir = os.path.join(images_dir, presentation_id)
                os.makedirs(presentation_images_dir, exist_ok=True)
                
                slides_data = []
                
                for i, (xml_content, screenshot_path) in enumerate(zip(slide_xmls, screenshot_paths), 1):
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
                    
                    # Compute normalized fonts for this slide
                    raw_slide_fonts = self.extract_fonts_from_oxml(xml_content)
                    normalized_fonts = sorted({self.normalize_font_family_name(f) for f in raw_slide_fonts if f})
                    
                    slides_data.append({
                        "slide_number": i,
                        "screenshot_url": screenshot_url,
                        "xml_content": xml_content,
                        "normalized_fonts": normalized_fonts
                    })
                
                self.log_request_success("process_pptx_slides", 
                                       filename=pptx_file.filename,
                                       slides_processed=len(slides_data))
                
                return {
                    "success": True,
                    "slides": slides_data,
                    "total_slides": len(slides_data),
                    "fonts": font_analysis
                }
                
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("process_pptx_slides", e, filename=pptx_file.filename)
            raise HTTPException(
                status_code=500,
                detail=f"Error processing PPTX slides: {str(e)}"
            )
    
    async def process_pptx_fonts(self, pptx_file: UploadFile) -> Dict[str, any]:
        """
        Analyze a PPTX file and return only the fonts used in the document.
        
        Args:
            pptx_file: PPTX file to analyze
            
        Returns:
            Dictionary with font analysis results
        """
        self.log_request_start("process_pptx_fonts", filename=pptx_file.filename)
        
        try:
            # Validate PPTX file
            if pptx_file.content_type not in POWERPOINT_TYPES:
                self.log_validation_error("pptx_file", "invalid_type", 
                                        f"Expected PPTX file, got {pptx_file.content_type}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type. Expected PPTX file, got {pptx_file.content_type}"
                )
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save uploaded PPTX file
                pptx_path = os.path.join(temp_dir, "presentation.pptx")
                with open(pptx_path, "wb") as f:
                    pptx_content = await pptx_file.read()
                    f.write(pptx_content)
                
                # Extract slide XMLs from PPTX
                slide_xmls = self._extract_slide_xmls(pptx_path, temp_dir)
                
                # Analyze fonts across all slides
                font_analysis = await self.analyze_fonts_in_all_slides(slide_xmls)
                
                self.log_request_success("process_pptx_fonts", 
                                       filename=pptx_file.filename,
                                       supported=len(font_analysis["internally_supported_fonts"]),
                                       unsupported=len(font_analysis["not_supported_fonts"]))
                
                return {
                    "success": True,
                    "fonts": font_analysis
                }
                
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("process_pptx_fonts", e, filename=pptx_file.filename)
            raise HTTPException(
                status_code=500,
                detail=f"Error processing PPTX fonts: {str(e)}"
            )