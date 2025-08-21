"""
SlideHandler contains all business logic for slide operations.
Uses mixins for common functionality like database operations, logging, and asset services.
"""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Models
from models.sql.presentation import PresentationModel
from models.sql.slide import SlideModel

# Services and utilities
from utils.llm_calls.edit_slide import get_edited_slide_content
from utils.llm_calls.edit_slide_html import get_edited_slide_html
from utils.llm_calls.select_slide_type_on_edit import get_slide_layout_from_prompt
from utils.process_slides import process_old_and_new_slides_and_fetch_assets
from utils.randomizers import get_random_uuid

# Mixins
from mixins import DatabaseMixin, AssetServicesMixin, ValidationMixin


class SlideHandler(DatabaseMixin, AssetServicesMixin, ValidationMixin):
    """Handler for all slide-related business logic."""
    
    def __init__(self, sql_session: AsyncSession):
        super().__init__(sql_session)
        self.log_request_start("handler_initialization", handler="SlideHandler")
    
    async def edit_slide(self, slide_id: str, prompt: str) -> SlideModel:
        """
        Edit a slide with AI-generated content.
        
        Args:
            slide_id: ID of the slide to edit
            prompt: Edit instruction prompt
            
        Returns:
            Updated SlideModel
        """
        self.log_request_start("edit_slide", slide_id=slide_id)
        
        try:
            # Validate inputs
            self.validate_string_length(slide_id, "slide_id", min_length=1)
            self.validate_string_length(prompt, "prompt", min_length=1, max_length=2000)
            
            # Get slide and presentation
            slide = await self.get_or_404(SlideModel, slide_id, "Slide not found")
            presentation = await self.get_or_404(PresentationModel, slide.presentation, "Presentation not found")
            
            self.logger.info("Retrieved slide and presentation", 
                           slide_id=slide_id, 
                           presentation_id=slide.presentation)
            
            # Get slide layout for editing
            presentation_layout = presentation.get_layout()
            self.log_external_service_call("LLM", "select_slide_layout", slide_id=slide_id)
            
            slide_layout = await get_slide_layout_from_prompt(
                prompt, presentation_layout, slide
            )
            
            # Generate edited content
            self.log_external_service_call("LLM", "edit_slide_content", slide_id=slide_id)
            edited_slide_content = await get_edited_slide_content(
                prompt, slide, presentation.language, slide_layout
            )
            
            # Process assets
            self.logger.info("Processing slide assets", slide_id=slide_id)
            new_assets = await process_old_and_new_slides_and_fetch_assets(
                self.image_service,
                self.icon_service,
                slide.content,
                edited_slide_content,
            )
            
            # Update slide with new content
            slide.id = get_random_uuid()  # Always assign new UUID for tracking
            slide.content = edited_slide_content
            slide.layout = slide_layout.id
            slide.speaker_note = edited_slide_content.get("__speaker_note__", "")
            
            # Save changes
            await self.safe_add(slide)
            await self.safe_add_all(new_assets)
            await self.safe_commit()
            
            self.log_request_success("edit_slide", 
                                   slide_id=slide_id, 
                                   new_slide_id=slide.id,
                                   assets_generated=len(new_assets))
            
            return slide
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("edit_slide", e, slide_id=slide_id)
            raise HTTPException(status_code=500, detail="Failed to edit slide")
    
    async def edit_slide_html(
        self, 
        slide_id: str, 
        prompt: str, 
        html: Optional[str] = None
    ) -> SlideModel:
        """
        Edit slide HTML content directly.
        
        Args:
            slide_id: ID of the slide to edit
            prompt: Edit instruction prompt
            html: Optional HTML content to edit (uses slide's HTML if not provided)
            
        Returns:
            Updated SlideModel
        """
        self.log_request_start("edit_slide_html", slide_id=slide_id)
        
        try:
            # Validate inputs
            self.validate_string_length(slide_id, "slide_id", min_length=1)
            self.validate_string_length(prompt, "prompt", min_length=1, max_length=2000)
            
            # Get slide
            slide = await self.get_or_404(SlideModel, slide_id, "Slide not found")
            
            # Determine HTML to edit
            html_to_edit = html or slide.html_content
            if not html_to_edit:
                self.log_validation_error("html_content", "empty", "No HTML content available for editing")
                raise HTTPException(status_code=400, detail="No HTML to edit")
            
            self.logger.info("Editing slide HTML", 
                           slide_id=slide_id, 
                           html_length=len(html_to_edit))
            
            # Generate edited HTML
            self.log_external_service_call("LLM", "edit_slide_html", slide_id=slide_id)
            edited_slide_html = await get_edited_slide_html(prompt, html_to_edit)
            
            # Update slide
            slide.id = get_random_uuid()  # New UUID for tracking updates
            slide.html_content = edited_slide_html
            
            # Save changes
            await self.safe_add(slide)
            await self.safe_commit()
            
            self.log_request_success("edit_slide_html", 
                                   slide_id=slide_id, 
                                   new_slide_id=slide.id,
                                   edited_html_length=len(edited_slide_html))
            
            return slide
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("edit_slide_html", e, slide_id=slide_id)
            raise HTTPException(status_code=500, detail="Failed to edit slide HTML")