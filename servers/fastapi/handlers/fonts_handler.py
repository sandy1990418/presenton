"""
FontsHandler contains all business logic for font management operations.
Uses mixins for common functionality like database operations, logging, and validation.
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from utils.asset_directory_utils import get_app_data_directory_env
from utils.randomizers import get_random_uuid

# Try to import fontTools for font metadata reading
try:
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables._n_a_m_e import table__n_a_m_e
    FONTTOOLS_AVAILABLE = True
except ImportError:
    FONTTOOLS_AVAILABLE = False

# Mixins
from mixins import DatabaseMixin, ValidationMixin


class FontsHandler(DatabaseMixin, ValidationMixin):
    """Handler for all font management operations."""
    
    # Supported font file extensions
    SUPPORTED_FONT_EXTENSIONS = {
        '.ttf': 'font/ttf',
        '.otf': 'font/otf', 
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.eot': 'application/vnd.ms-fontobject'
    }
    
    def __init__(self, sql_session: AsyncSession):
        super().__init__(sql_session)
        self.log_request_start("handler_initialization", handler="FontsHandler")
    
    def get_fonts_directory(self) -> str:
        """Get the fonts directory path, create if it doesn't exist."""
        app_data_dir = get_app_data_directory_env() or "/tmp/presenton"
        fonts_dir = os.path.join(app_data_dir, "fonts")
        os.makedirs(fonts_dir, exist_ok=True)
        return fonts_dir
    
    def is_valid_font_file(self, file: UploadFile) -> bool:
        """Check if the uploaded file is a valid font file."""
        if not file.filename:
            return False
        
        file_extension = Path(file.filename).suffix.lower()
        return file_extension in self.SUPPORTED_FONT_EXTENSIONS
    
    def get_font_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from font file using fontTools."""
        if not FONTTOOLS_AVAILABLE:
            self.logger.warning("fontTools not available, returning basic metadata")
            return {
                "family_name": Path(file_path).stem,
                "full_name": Path(file_path).stem,
                "style_name": "Regular",
                "version": "Unknown"
            }
        
        try:
            font = TTFont(file_path)
            name_table = font['name']
            
            # Extract font names
            family_name = name_table.getDebugName(1) or "Unknown"  # Family name
            full_name = name_table.getDebugName(4) or family_name  # Full font name
            style_name = name_table.getDebugName(2) or "Regular"   # Style name
            version = name_table.getDebugName(5) or "1.0"          # Version
            
            return {
                "family_name": family_name,
                "full_name": full_name,
                "style_name": style_name,
                "version": version
            }
            
        except Exception as e:
            self.logger.exception("Error reading font metadata", file_path=file_path)
            # Return fallback metadata
            return {
                "family_name": Path(file_path).stem,
                "full_name": Path(file_path).stem,
                "style_name": "Regular",
                "version": "Unknown"
            }
    
    async def upload_font(self, font_file: UploadFile) -> Dict[str, Any]:
        """
        Upload and save a font file.
        
        Args:
            font_file: Font file to upload
            
        Returns:
            Dictionary with upload result and font information
        """
        self.log_request_start("upload_font", filename=font_file.filename)
        
        try:
            # Validate font file
            if not self.is_valid_font_file(font_file):
                self.log_validation_error("font_file", "invalid_type", 
                                        f"Unsupported font file: {font_file.filename}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported font file type. Supported: {list(self.SUPPORTED_FONT_EXTENSIONS.keys())}"
                )
            
            # Generate unique filename to avoid conflicts
            original_name = Path(font_file.filename).stem
            file_extension = Path(font_file.filename).suffix.lower()
            unique_filename = f"{original_name}_{get_random_uuid()}{file_extension}"
            
            # Save font file
            fonts_dir = self.get_fonts_directory()
            font_path = os.path.join(fonts_dir, unique_filename)
            
            with open(font_path, "wb") as f:
                content = await font_file.read()
                f.write(content)
            
            # Extract font metadata
            metadata = self.get_font_metadata(font_path)
            
            # Generate font URL for serving
            font_url = f"/app_data/fonts/{unique_filename}"
            
            result = {
                "success": True,
                "font_name": metadata["family_name"],
                "font_url": font_url,
                "font_path": font_path,
                "message": f"Font '{metadata['family_name']}' uploaded successfully"
            }
            
            self.log_request_success("upload_font", 
                                   filename=font_file.filename,
                                   font_name=metadata["family_name"],
                                   font_path=font_path)
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("upload_font", e, filename=font_file.filename)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload font: {str(e)}"
            )
    
    async def list_fonts(self) -> Dict[str, Any]:
        """
        List all uploaded fonts.
        
        Returns:
            Dictionary with list of fonts and their metadata
        """
        self.log_request_start("list_fonts")
        
        try:
            fonts_dir = self.get_fonts_directory()
            fonts = []
            
            if not os.path.exists(fonts_dir):
                self.logger.info("Fonts directory does not exist", fonts_dir=fonts_dir)
                return {
                    "success": True,
                    "fonts": [],
                    "message": "No fonts uploaded yet"
                }
            
            # Get all font files in directory
            for filename in os.listdir(fonts_dir):
                file_path = os.path.join(fonts_dir, filename)
                
                # Skip directories and non-font files
                if os.path.isdir(file_path):
                    continue
                
                file_extension = Path(filename).suffix.lower()
                if file_extension not in self.SUPPORTED_FONT_EXTENSIONS:
                    continue
                
                # Get font metadata
                metadata = self.get_font_metadata(file_path)
                
                # Get file stats
                stat_info = os.stat(file_path)
                
                font_info = {
                    "filename": filename,
                    "font_name": metadata["family_name"],
                    "full_name": metadata["full_name"],
                    "style": metadata["style_name"],
                    "version": metadata["version"],
                    "size": stat_info.st_size,
                    "upload_time": stat_info.st_mtime,
                    "font_url": f"/app_data/fonts/{filename}",
                    "mime_type": self.SUPPORTED_FONT_EXTENSIONS.get(file_extension, "application/octet-stream")
                }
                
                fonts.append(font_info)
            
            # Sort fonts by family name
            fonts.sort(key=lambda x: x["font_name"].lower())
            
            result = {
                "success": True,
                "fonts": fonts,
                "message": f"Found {len(fonts)} font(s)"
            }
            
            self.log_request_success("list_fonts", font_count=len(fonts))
            return result
            
        except Exception as e:
            self.log_request_error("list_fonts", e)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list fonts: {str(e)}"
            )
    
    async def delete_font(self, filename: str) -> Dict[str, Any]:
        """
        Delete a font file.
        
        Args:
            filename: Name of the font file to delete
            
        Returns:
            Dictionary with deletion result
        """
        self.log_request_start("delete_font", filename=filename)
        
        try:
            # Validate filename
            self.validate_string_length(filename, "filename", min_length=1, max_length=255)
            
            fonts_dir = self.get_fonts_directory()
            font_path = os.path.join(fonts_dir, filename)
            
            # Check if font file exists
            if not os.path.exists(font_path):
                self.log_validation_error("font_file", "not_found", f"Font file not found: {filename}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Font file '{filename}' not found"
                )
            
            # Check if it's actually a font file
            file_extension = Path(filename).suffix.lower()
            if file_extension not in self.SUPPORTED_FONT_EXTENSIONS:
                self.log_validation_error("font_file", "invalid_type", f"Not a font file: {filename}")
                raise HTTPException(
                    status_code=400,
                    detail=f"'{filename}' is not a valid font file"
                )
            
            # Get font name before deletion for logging
            metadata = self.get_font_metadata(font_path)
            font_name = metadata["family_name"]
            
            # Delete the font file
            os.remove(font_path)
            
            result = {
                "success": True,
                "message": f"Font '{font_name}' deleted successfully"
            }
            
            self.log_request_success("delete_font", 
                                   filename=filename,
                                   font_name=font_name)
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("delete_font", e, filename=filename)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete font: {str(e)}"
            )