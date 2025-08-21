"""
FilesHandler contains all business logic for file upload, decompose, and update operations.
Uses mixins for common functionality like database operations, logging, and validation.
"""

import asyncio
import os
from typing import List, Optional, Dict, Any

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from constants.documents import UPLOAD_ACCEPTED_FILE_TYPES
from models.decomposed_file_info import DecomposedFileInfo
from services import TEMP_FILE_SERVICE
from services.documents_loader import DocumentsLoader
from utils.randomizers import get_random_uuid
from utils.validators import validate_files

# Mixins
from mixins import DatabaseMixin, ValidationMixin


class FilesHandler(DatabaseMixin, ValidationMixin):
    """Handler for all file management operations."""
    
    def __init__(self, sql_session: AsyncSession):
        super().__init__(sql_session)
        self.log_request_start("handler_initialization", handler="FilesHandler")
    
    async def upload_files(self, files: Optional[List[UploadFile]]) -> List[str]:
        """
        Upload files and save them to temporary directory.
        
        Args:
            files: List of uploaded files
            
        Returns:
            List of temporary file paths
        """
        self.log_request_start("upload_files", file_count=len(files) if files else 0)
        
        try:
            if not files:
                self.log_validation_error("files", "required", "Documents are required")
                raise HTTPException(status_code=400, detail="Documents are required")

            temp_dir = TEMP_FILE_SERVICE.create_temp_dir(get_random_uuid())
            self.logger.debug("Created temporary directory", temp_dir=temp_dir)

            # Validate files
            validate_files(files, True, True, 100, UPLOAD_ACCEPTED_FILE_TYPES)
            self.logger.info("Files validation passed", file_count=len(files))

            temp_files: List[str] = []
            for each_file in files:
                if not each_file.filename:
                    self.logger.warning("File without filename skipped")
                    continue
                    
                temp_path = TEMP_FILE_SERVICE.create_temp_file_path(
                    each_file.filename, temp_dir
                )
                
                try:
                    with open(temp_path, "wb") as f:
                        content = await each_file.read()
                        f.write(content)
                    
                    temp_files.append(temp_path)
                    self.logger.debug("File uploaded", 
                                    filename=each_file.filename,
                                    temp_path=temp_path,
                                    size=len(content))
                                    
                except Exception as e:
                    self.logger.exception("Failed to save uploaded file", 
                                        filename=each_file.filename)
                    # Continue with other files rather than failing completely
                    continue

            self.log_request_success("upload_files", 
                                   uploaded_count=len(temp_files),
                                   temp_dir=temp_dir)
            
            return temp_files
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("upload_files", e, file_count=len(files) if files else 0)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload files: {str(e)}"
            )
    
    async def decompose_files(self, file_paths: List[str]) -> List[DecomposedFileInfo]:
        """
        Decompose files into text format for processing.
        
        Args:
            file_paths: List of file paths to decompose
            
        Returns:
            List of decomposed file information
        """
        self.log_request_start("decompose_files", file_count=len(file_paths))
        
        try:
            self.validate_string_length(str(file_paths), "file_paths", min_length=1)
            
            temp_dir = TEMP_FILE_SERVICE.create_temp_dir(get_random_uuid())
            self.logger.debug("Created temporary directory for decomposition", temp_dir=temp_dir)

            # Separate txt files from other files
            txt_files = []
            other_files = []
            for file_path in file_paths:
                if file_path.endswith(".txt"):
                    txt_files.append(file_path)
                else:
                    other_files.append(file_path)
            
            self.logger.info("Categorized files", 
                           txt_files=len(txt_files),
                           other_files=len(other_files))

            response = []

            # Process non-txt files through DocumentsLoader
            if other_files:
                documents_loader = DocumentsLoader(file_paths=other_files)
                await documents_loader.load_documents(temp_dir)
                parsed_documents = documents_loader.documents
                
                self.logger.info("Parsed documents", parsed_count=len(parsed_documents))

                for index, parsed_doc in enumerate(parsed_documents):
                    try:
                        file_path = TEMP_FILE_SERVICE.create_temp_file_path(
                            f"{get_random_uuid()}.txt", temp_dir
                        )
                        
                        # Clean up HTML breaks
                        parsed_doc = parsed_doc.replace("<br>", "\n")
                        
                        def _write_file():
                            with open(file_path, "w", encoding="utf-8") as text_file:
                                text_file.write(parsed_doc)
                        
                        await asyncio.to_thread(_write_file)
                        
                        response.append(
                            DecomposedFileInfo(
                                name=os.path.basename(other_files[index]), 
                                file_path=file_path
                            )
                        )
                        
                        self.logger.debug("Decomposed file", 
                                        original=other_files[index],
                                        decomposed=file_path,
                                        content_length=len(parsed_doc))
                                        
                    except Exception as e:
                        self.logger.exception("Failed to decompose file", 
                                            file_path=other_files[index] if index < len(other_files) else "unknown")
                        # Continue with other files
                        continue

            # Add txt files as-is
            for each_file in txt_files:
                response.append(
                    DecomposedFileInfo(
                        name=os.path.basename(each_file), 
                        file_path=each_file
                    )
                )
                self.logger.debug("Added txt file as-is", file_path=each_file)

            self.log_request_success("decompose_files", 
                                   total_files=len(file_paths),
                                   decomposed_count=len(response))
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("decompose_files", e, file_count=len(file_paths))
            raise HTTPException(
                status_code=500,
                detail=f"Failed to decompose files: {str(e)}"
            )
    
    async def update_file(self, file_path: str, file: UploadFile) -> Dict[str, Any]:
        """
        Update an existing file with new content.
        
        Args:
            file_path: Path to the file to update
            file: New file content
            
        Returns:
            Dictionary with success message
        """
        self.log_request_start("update_file", file_path=file_path, filename=file.filename)
        
        try:
            # Validate inputs
            self.validate_string_length(file_path, "file_path", min_length=1, max_length=1000)
            
            if not file.filename:
                self.log_validation_error("file", "no_filename", "File must have a filename")
                raise HTTPException(status_code=400, detail="File must have a filename")
            
            # Check if target file path exists
            if not os.path.exists(os.path.dirname(file_path)):
                self.log_validation_error("file_path", "directory_not_found", 
                                        f"Directory does not exist: {os.path.dirname(file_path)}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Directory does not exist: {os.path.dirname(file_path)}"
                )
            
            # Read file content
            content = await file.read()
            
            # Write to target file
            with open(file_path, "wb") as f:
                f.write(content)
            
            self.log_request_success("update_file", 
                                   file_path=file_path,
                                   filename=file.filename,
                                   content_size=len(content))
            
            return {"message": "File updated successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("update_file", e, file_path=file_path)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update file: {str(e)}"
            )