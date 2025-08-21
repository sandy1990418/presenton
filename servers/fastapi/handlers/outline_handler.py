"""
OutlineHandler contains all business logic for outline generation operations.
Uses mixins for common functionality like database operations, logging, and streaming.
"""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Models
from models.presentation_outline_model import PresentationOutlineModel
from models.sql.presentation import PresentationModel

# Services and utilities
from services import TEMP_FILE_SERVICE
from services.documents_loader import DocumentsLoader
from services.score_based_chunker import ScoreBasedChunker
from utils.llm_calls.generate_presentation_outlines import generate_ppt_outline

# Mixins
from mixins import DatabaseMixin, StreamingMixin, ValidationMixin


class OutlineHandler(DatabaseMixin, StreamingMixin, ValidationMixin):
    """Handler for all outline-related business logic."""
    
    def __init__(self, sql_session: AsyncSession):
        super().__init__(sql_session)
        self.log_request_start("handler_initialization", handler="OutlineHandler")
    
    async def stream_outlines_generator(self, presentation_id: str) -> AsyncGenerator[str, None]:
        """
        Generate presentation outlines with streaming updates.
        
        Args:
            presentation_id: ID of the presentation to generate outlines for
            
        Yields:
            SSE formatted strings with progress updates
        """
        self.log_request_start("stream_outlines", presentation_id=presentation_id)
        
        try:
            # Get presentation
            presentation = await self.get_or_404(PresentationModel, presentation_id)
            
            # Create temp directory for document processing
            temp_dir = TEMP_FILE_SERVICE.create_temp_dir()
            self.logger.debug("Created temporary directory", temp_dir=temp_dir)
            
            # Initial status update
            yield await self.yield_status_update("Generating presentation outlines...")
            
            presentation_outlines = None
            additional_context = ""
            
            # Process files if available
            if presentation.file_paths:
                self.logger.info("Processing uploaded files", 
                               file_count=len(presentation.file_paths),
                               presentation_id=presentation_id)
                
                documents_loader = DocumentsLoader(file_paths=presentation.file_paths)
                await documents_loader.load_documents(temp_dir)
                documents = documents_loader.documents
                
                if documents:
                    additional_context = documents[0]
                    chunker = ScoreBasedChunker()
                    
                    try:
                        chunks = await chunker.get_n_chunks(documents[0], presentation.n_slides)
                        presentation_outlines = PresentationOutlineModel(
                            slides=[chunk.to_slide_outline() for chunk in chunks]
                        )
                        self.logger.info("Generated outlines from document chunks", 
                                       chunk_count=len(chunks),
                                       presentation_id=presentation_id)
                    except Exception as e:
                        self.logger.exception("Failed to process document chunks", 
                                           presentation_id=presentation_id)
                        # Continue with LLM-based outline generation
            
            # Generate outlines using LLM if not already done
            if not presentation_outlines:
                self.logger.info("Generating outlines using LLM", 
                               presentation_id=presentation_id)
                
                presentation_outlines_text = ""
                
                async for chunk in generate_ppt_outline(
                    presentation.prompt,
                    presentation.n_slides,
                    presentation.language,
                    additional_context,
                ):
                    # Give control to the event loop
                    await asyncio.sleep(0)
                    
                    yield await self.yield_chunk_update(chunk)
                    presentation_outlines_text += chunk
                
                try:
                    presentation_outlines_json = json.loads(presentation_outlines_text)
                except Exception as e:
                    self.log_request_error("parse_outline_json", e, presentation_id=presentation_id)
                    raise HTTPException(
                        status_code=400,
                        detail="Failed to generate presentation outlines. Please try again.",
                    )
                
                presentation_outlines = PresentationOutlineModel(**presentation_outlines_json)
            
            # Limit slides to requested number
            presentation_outlines.slides = presentation_outlines.slides[:presentation.n_slides]
            
            # Generate title from first slide
            presentation.outlines = presentation_outlines.model_dump()
            presentation.title = (
                presentation_outlines.slides[0]
                .content[:50]
                .replace("#", "")
                .replace("/", "")
                .replace("\\", "")
                .replace("\n", "")
            )
            
            # Save to database
            await self.safe_add(presentation)
            await self.safe_commit()
            
            self.log_request_success("stream_outlines", 
                                   presentation_id=presentation_id,
                                   outline_count=len(presentation_outlines.slides))
            
            # Send final completion
            yield await self.yield_completion("presentation", presentation.model_dump(mode="json"))
            
        except HTTPException:
            yield await self.yield_error("Failed to generate presentation outlines")
            raise
        except Exception as e:
            self.log_request_error("stream_outlines", e, presentation_id=presentation_id)
            yield await self.yield_error(f"Outline generation error: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to generate outlines")