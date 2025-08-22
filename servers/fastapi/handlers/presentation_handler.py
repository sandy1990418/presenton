"""
PresentationHandler contains all business logic for presentation operations.
Uses mixins for common functionality like database operations, logging, and streaming.
"""

import asyncio
import json
import os
import random
from typing import List, Optional, AsyncGenerator, Set

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

# Models
from models.presentation_outline_model import PresentationOutlineModel, SlideOutlineModel
from models.pptx_models import PptxPresentationModel
from models.presentation_layout import PresentationLayoutModel
from models.presentation_structure_model import PresentationStructureModel
from models.presentation_with_slides import PresentationWithSlides
from models.sql.presentation import PresentationModel
from models.sql.slide import SlideModel

# Services and utilities
from utils.llm_calls.generate_presentation_structure import generate_presentation_structure
from utils.llm_calls.generate_slide_content import get_slide_content_from_type_and_outline
from utils.process_slides import process_slide_and_fetch_assets, convert_file_path_to_web_url
from utils.randomizers import get_random_uuid
from utils.asset_directory_utils import get_exports_directory
from services.llm_client import LLMClient
from services.pptx_presentation_creator import PptxPresentationCreator
from services import TEMP_FILE_SERVICE

# External dependencies
try:
    from pathvalidate import sanitize_filename
except ImportError:
    # Fallback if pathvalidate is not available
    def sanitize_filename(filename: str) -> str:
        return filename.replace('/', '_').replace('\\', '_')

# Mixins
from mixins import DatabaseMixin, AssetServicesMixin, StreamingMixin, ValidationMixin


class PresentationHandler(DatabaseMixin, AssetServicesMixin, StreamingMixin, ValidationMixin):
    """Handler for all presentation-related business logic."""
    
    # Track active streaming requests to prevent duplicates
    _active_streams: Set[str] = set()
    
    def __init__(self, sql_session: AsyncSession):
        super().__init__(sql_session)
        self.log_request_start("handler_initialization", handler="PresentationHandler")
    
    def convert_slide_image_urls(self, slides: List[SlideModel]) -> List[SlideModel]:
        """Convert all image URLs in slide content to web-accessible paths."""
        self.logger.debug("Converting slide image URLs", slide_count=len(slides))
        
        for slide in slides:
            if slide.content:
                slide.content = self._convert_urls_in_dict(slide.content)
        return slides
    
    def _convert_urls_in_dict(self, data) -> any:
        """Recursively convert image URLs in a dictionary structure."""
        if isinstance(data, dict):
            converted = {}
            for key, value in data.items():
                if key in ("__image_url__", "__icon_url__") and isinstance(value, str):
                    converted[key] = convert_file_path_to_web_url(value)
                else:
                    converted[key] = self._convert_urls_in_dict(value)
            return converted
        elif isinstance(data, list):
            return [self._convert_urls_in_dict(item) for item in data]
        else:
            return data
    
    async def get_presentation(self, presentation_id: str) -> PresentationWithSlides:
        """
        Get a presentation with all its slides.
        
        Args:
            presentation_id: ID of the presentation to retrieve
            
        Returns:
            PresentationWithSlides object
        """
        self.log_request_start("get_presentation", presentation_id=presentation_id)
        
        try:
            # Get presentation
            presentation = await self.get_or_404(PresentationModel, presentation_id, "Presentation not found")
            
            # Get slides
            slides = await self.sql_session.scalars(
                select(SlideModel)
                .where(SlideModel.presentation == presentation_id)
                .order_by(SlideModel.index)
            )
            slides_list = list(slides)
            
            # Convert image URLs for offline environments
            converted_slides = self.convert_slide_image_urls(slides_list)
            
            result = PresentationWithSlides(
                **presentation.model_dump(),
                slides=converted_slides,
            )
            
            self.log_request_success("get_presentation", presentation_id=presentation_id, slide_count=len(converted_slides))
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("get_presentation", e, presentation_id=presentation_id)
            raise HTTPException(status_code=500, detail="Failed to retrieve presentation")
    
    async def delete_presentation(self, presentation_id: str) -> None:
        """
        Delete a presentation and all its slides.
        
        Args:
            presentation_id: ID of the presentation to delete
        """
        self.log_request_start("delete_presentation", presentation_id=presentation_id)
        
        try:
            # Verify presentation exists
            presentation = await self.get_or_404(PresentationModel, presentation_id, "Presentation not found")
            
            # Delete slides first
            await self.sql_session.execute(delete(SlideModel).where(SlideModel.presentation == presentation_id))
            self.log_database_operation("delete_slides", "SlideModel", presentation_id=presentation_id)
            
            # Delete presentation
            await self.sql_session.delete(presentation)
            await self.safe_commit()
            
            self.log_request_success("delete_presentation", presentation_id=presentation_id)
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("delete_presentation", e, presentation_id=presentation_id)
            raise HTTPException(status_code=500, detail="Failed to delete presentation")
    
    async def get_all_presentations(self) -> List[PresentationWithSlides]:
        """
        Get all presentations with their first slide.
        
        Returns:
            List of PresentationWithSlides objects
        """
        self.log_request_start("get_all_presentations")
        
        try:
            presentations = await self.sql_session.scalars(select(PresentationModel))
            
            async def get_presentation_with_first_slide(presentation: PresentationModel) -> Optional[PresentationWithSlides]:
                first_slide = await self.sql_session.scalar(
                    select(SlideModel)
                    .where(SlideModel.presentation == presentation.id)
                    .where(SlideModel.index == 0)
                )
                if not first_slide:
                    return None
                    
                return PresentationWithSlides(
                    **presentation.model_dump(),
                    slides=[first_slide],
                )
            
            tasks = [get_presentation_with_first_slide(p) for p in presentations]
            results = await asyncio.gather(*tasks)
            presentations_with_slides = [r for r in results if r is not None]
            
            self.log_request_success("get_all_presentations", count=len(presentations_with_slides))
            return presentations_with_slides
            
        except Exception as e:
            self.log_request_error("get_all_presentations", e)
            raise HTTPException(status_code=500, detail="Failed to retrieve presentations")
    
    async def create_presentation(
        self, 
        prompt: str, 
        n_slides: int, 
        language: str, 
        file_paths: Optional[List[str]] = None
    ) -> PresentationModel:
        """
        Create a new presentation.
        
        Args:
            prompt: Presentation prompt
            n_slides: Number of slides
            language: Language code
            file_paths: Optional list of file paths
            
        Returns:
            Created PresentationModel
        """
        self.log_request_start("create_presentation", n_slides=n_slides, language=language)
        
        # Log feature status
        llm_client = LLMClient()
        thinking_disabled = llm_client.disable_thinking()
        web_grounding_enabled = llm_client.enable_web_grounding()
        self.logger.info("LLM Feature Status", 
                        web_grounding_enabled=web_grounding_enabled,
                        thinking_status="DISABLED" if thinking_disabled else "ENABLED",
                        llm_provider=str(llm_client.llm_provider.value))
        
        try:
            # Validate inputs
            self.validate_string_length(prompt, "prompt", min_length=1, max_length=5000, allow_empty=True)
            n_slides = self.validate_positive_integer(n_slides, "n_slides", min_value=1)
            language = self.validate_language_code(language)
            file_paths = self.validate_file_paths(file_paths)
            
            presentation_id = get_random_uuid()
            
            presentation = PresentationModel(
                id=presentation_id,
                prompt=prompt,
                n_slides=n_slides,
                language=language,
                file_paths=file_paths,
            )
            
            await self.safe_add(presentation)
            await self.safe_commit()
            
            self.log_request_success("create_presentation", presentation_id=presentation_id)
            return presentation
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("create_presentation", e)
            raise HTTPException(status_code=500, detail="Failed to create presentation")
    
    async def prepare_presentation(
        self,
        presentation_id: str,
        outlines: List[SlideOutlineModel],
        layout: PresentationLayoutModel,
        title: Optional[str] = None
    ) -> PresentationModel:
        """
        Prepare a presentation with outlines and layout.
        
        Args:
            presentation_id: ID of the presentation to prepare
            outlines: List of slide outlines
            layout: Presentation layout
            title: Optional presentation title
            
        Returns:
            Updated PresentationModel
        """
        self.log_request_start("prepare_presentation", presentation_id=presentation_id, outline_count=len(outlines))
        
        try:
            # Validate inputs
            outlines = self.validate_list_not_empty(outlines, "outlines")
            
            presentation = await self.get_or_404(PresentationModel, presentation_id)
            presentation_outline_model = PresentationOutlineModel(slides=outlines)
            
            total_slide_layouts = len(layout.slides)
            total_outlines = len(outlines)
            
            # Generate or use ordered structure
            if layout.ordered:
                presentation_structure = layout.to_presentation_structure()
                self.logger.info("Using ordered layout structure")
            else:
                self.log_external_service_call("LLM", "generate_presentation_structure")
                presentation_structure: PresentationStructureModel = (
                    await generate_presentation_structure(
                        presentation_outline=presentation_outline_model,
                        presentation_layout=layout,
                    )
                )
                self.logger.info("Generated dynamic layout structure")
            
            # Ensure structure matches outline count
            presentation_structure.slides = presentation_structure.slides[:total_outlines]
            for index in range(total_outlines):
                if index >= len(presentation_structure.slides):
                    random_slide_index = random.randint(0, total_slide_layouts - 1)
                    presentation_structure.slides.append(random_slide_index)
                elif presentation_structure.slides[index] >= total_slide_layouts:
                    presentation_structure.slides[index] = random.randint(0, total_slide_layouts - 1)
            
            # Update presentation
            presentation.outlines = presentation_outline_model.model_dump(mode="json")
            presentation.title = title or presentation.title
            presentation.set_layout(layout)
            presentation.set_structure(presentation_structure)
            
            await self.safe_add(presentation)
            await self.safe_commit()
            
            self.log_request_success("prepare_presentation", presentation_id=presentation_id)
            return presentation
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("prepare_presentation", e, presentation_id=presentation_id)
            raise HTTPException(status_code=500, detail="Failed to prepare presentation")
    
    async def stream_presentation_generator(self, presentation_id: str) -> AsyncGenerator[str, None]:
        """
        Generate presentation content with streaming updates.
        
        Args:
            presentation_id: ID of the presentation to generate
            
        Yields:
            SSE formatted strings with progress updates
        """
        self.log_request_start("stream_presentation", presentation_id=presentation_id)
        
        try:
            # Check for duplicate streams
            if not self.track_active_stream(presentation_id, self._active_streams):
                raise HTTPException(
                    status_code=409,
                    detail=f"Stream already active for presentation {presentation_id}"
                )
            
            try:
                presentation = await self.get_or_404(PresentationModel, presentation_id)
                
                # Validate presentation state
                if not presentation.structure:
                    raise HTTPException(status_code=400, detail="Presentation not prepared for stream")
                if not presentation.outlines:
                    raise HTTPException(status_code=400, detail="Outlines cannot be empty")
                
                structure = presentation.get_structure()
                layout = presentation.get_layout()
                outline = presentation.get_presentation_outline()
                
                total_slides = len(structure.slides)
                
                # Initial status update
                yield await self.yield_status_update(f"Generating content for {total_slides} slides...")
                
                # Start JSON array
                yield await self.yield_chunk_update('{ "slides": [ ')
                
                slides: List[SlideModel] = []
                async_assets_generation_tasks = []
                
                # Generate slides sequentially
                for i, slide_layout_index in enumerate(structure.slides):
                    slide_layout = layout.slides[slide_layout_index]
                    
                    # Progress update
                    yield await self.yield_progress_update(
                        f"Generating slide {i+1}/{total_slides}",
                        current=i+1,
                        total=total_slides,
                        slide_layout=slide_layout.id
                    )
                    
                    # Generate slide content
                    self.log_external_service_call("LLM", "generate_slide_content", slide_index=i)
                    slide_content = await get_slide_content_from_type_and_outline(
                        slide_layout, outline.slides[i], presentation.language
                    )
                    
                    slide = SlideModel(
                        presentation=presentation_id,
                        layout_group=layout.name,
                        layout=slide_layout.id,
                        index=i,
                        speaker_note=slide_content.get("__speaker_note__", ""),
                        content=slide_content,
                    )
                    slides.append(slide)
                    
                    # Queue asset generation
                    async_assets_generation_tasks.append(
                        process_slide_and_fetch_assets(
                            self.image_service, self.icon_service, slide
                        )
                    )
                    
                    # Send slide data
                    yield await self.yield_chunk_update(slide.model_dump_json())
                    
                    if i < total_slides - 1:
                        yield await self.yield_chunk_update(", ")
                
                # Close JSON array
                yield await self.yield_chunk_update(" ] }")
                
                # Process assets
                yield await self.yield_status_update("Processing assets...")
                self.log_asset_generation("images_and_icons", len(async_assets_generation_tasks))
                
                generated_assets_lists = await asyncio.gather(*async_assets_generation_tasks)
                generated_assets = []
                for assets_list in generated_assets_lists:
                    generated_assets.extend(assets_list)
                
                # Save to database
                await self.safe_add(presentation)
                await self.safe_add_all(slides)
                await self.safe_add_all(generated_assets)
                await self.safe_commit()
                
                # Convert URLs and send final response
                converted_slides = self.convert_slide_image_urls(slides)
                response = PresentationWithSlides(
                    **presentation.model_dump(),
                    slides=converted_slides,
                )
                
                yield await self.yield_completion("presentation", response.model_dump(mode="json"))
                
                self.log_request_success("stream_presentation", presentation_id=presentation_id, slides_generated=len(slides))
                
            except HTTPException:
                yield await self.yield_error(f"Stream error: Presentation processing failed")
                raise
            except Exception as e:
                self.log_request_error("stream_presentation", e, presentation_id=presentation_id)
                yield await self.yield_error(f"Stream error: {str(e)}")
                raise HTTPException(status_code=500, detail="Stream processing failed")
                
        finally:
            # Always clean up active stream
            self.cleanup_active_stream(presentation_id, self._active_streams)
    
    async def update_presentation(self, presentation_with_slides: PresentationWithSlides) -> PresentationWithSlides:
        """
        Update a presentation and its slides.
        
        Args:
            presentation_with_slides: Updated presentation data
            
        Returns:
            Updated PresentationWithSlides
        """
        self.log_request_start("update_presentation", presentation_id=presentation_with_slides.id)
        
        try:
            updated_presentation = presentation_with_slides.to_presentation_model()
            updated_slides = presentation_with_slides.slides
            
            presentation = await self.get_or_404(PresentationModel, updated_presentation.id)
            presentation.sqlmodel_update(updated_presentation)
            
            # Delete existing slides and add new ones
            await self.sql_session.execute(
                delete(SlideModel).where(SlideModel.presentation == updated_presentation.id)
            )
            await self.safe_add_all(updated_slides)
            await self.safe_commit()
            
            # Convert URLs for response
            converted_slides = self.convert_slide_image_urls(updated_slides)
            
            result = PresentationWithSlides(
                **presentation.model_dump(),
                slides=converted_slides,
            )
            
            self.log_request_success("update_presentation", presentation_id=updated_presentation.id, slides_updated=len(updated_slides))
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("update_presentation", e, presentation_id=getattr(presentation_with_slides, 'id', 'unknown'))
            raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    
    async def create_pptx_export(self, pptx_model: PptxPresentationModel) -> str:
        """
        Create a PPTX export of a presentation.
        
        Args:
            pptx_model: PPTX presentation model
            
        Returns:
            Download URL for the exported file
        """
        self.log_request_start("create_pptx_export", presentation_name=pptx_model.name)
        
        try:
            temp_dir = TEMP_FILE_SERVICE.create_temp_dir()
            
            pptx_creator = PptxPresentationCreator(pptx_model, temp_dir)
            await pptx_creator.create_ppt()
            
            export_directory = get_exports_directory()
            sanitized_name = sanitize_filename(pptx_model.name or get_random_uuid()).replace(' ', '_')
            pptx_path = os.path.join(export_directory, f"{sanitized_name}.pptx")
            pptx_creator.save(pptx_path)
            
            # Return download URL
            filename = os.path.basename(pptx_path)
            download_url = f"/api/download/{filename}"
            
            self.log_request_success("create_pptx_export", filename=filename, path=pptx_path)
            return download_url
            
        except Exception as e:
            self.log_request_error("create_pptx_export", e)
            raise HTTPException(status_code=500, detail="Failed to create PPTX export")
    
    async def generate_complete_presentation(self, request) -> dict:
        """
        Generate a complete presentation from request (legacy generate endpoint).
        
        Args:
            request: GeneratePresentationRequest
            
        Returns:
            Dict with presentation path and edit path
        """
        from utils.get_layout_by_name import get_layout_by_name
        from utils.llm_calls.generate_presentation_outlines import generate_ppt_outline
        from utils.export_utils import export_presentation
        
        self.log_request_start("generate_complete_presentation", 
                              n_slides=request.n_slides,
                              language=request.language,
                              template=request.template)
        
        try:
            presentation_id = get_random_uuid()

            # Generate Outlines
            presentation_outlines_text = ""
            additional_context = ""
            
            self.logger.info("Starting outline generation", presentation_id=presentation_id)
            
            async for chunk in generate_ppt_outline(
                request.prompt,
                request.n_slides,
                request.language,
                additional_context,
            ):
                presentation_outlines_text += chunk

            try:
                presentation_outlines_json = json.loads(presentation_outlines_text)
            except Exception as e:
                self.log_request_error("parse_generated_outlines", e, presentation_id=presentation_id)
                raise HTTPException(
                    status_code=400,
                    detail="Failed to generate presentation outlines. Please try again.",
                )
            
            from models.presentation_outline_model import PresentationOutlineModel
            presentation_outlines = PresentationOutlineModel(**presentation_outlines_json)
            outlines = presentation_outlines.slides[:request.n_slides]
            total_outlines = len(outlines)

            self.logger.info("Successfully generated presentation outlines", 
                           presentation_id=presentation_id,
                           total_outlines=total_outlines)

            # Parse Layouts
            layout_model = await get_layout_by_name(request.template)
            total_slide_layouts = len(layout_model.slides)

            # Generate Structure
            if layout_model.ordered:
                presentation_structure = layout_model.to_presentation_structure()
                self.logger.info("Using ordered layout structure", presentation_id=presentation_id)
            else:
                self.logger.info("Generating dynamic presentation structure", presentation_id=presentation_id)
                presentation_structure = await generate_presentation_structure(
                    presentation_outlines,
                    layout_model,
                )

            presentation_structure.slides = presentation_structure.slides[:total_outlines]
            for index in range(total_outlines):
                random_slide_index = random.randint(0, total_slide_layouts - 1)
                if index >= total_outlines:
                    presentation_structure.slides.append(random_slide_index)
                    continue
                if presentation_structure.slides[index] >= total_slide_layouts:
                    presentation_structure.slides[index] = random_slide_index

            # Create PresentationModel
            presentation = PresentationModel(
                id=presentation_id,
                prompt=request.prompt,
                n_slides=request.n_slides,
                language=request.language,
                outlines=presentation_outlines.model_dump(),
                layout=layout_model.model_dump(),
                structure=presentation_structure.model_dump(),
            )

            async_asset_generation_tasks = []
            slides: List[SlideModel] = []
            
            # Generate slide content
            for i, slide_layout_index in enumerate(presentation_structure.slides):
                slide_layout = layout_model.slides[slide_layout_index]
                
                self.logger.debug("Generating slide content", 
                                presentation_id=presentation_id,
                                slide_index=i, 
                                layout_id=slide_layout.id)
                
                slide_content = await get_slide_content_from_type_and_outline(
                    slide_layout, outlines[i], request.language
                )
                slide = SlideModel(
                    presentation=presentation_id,
                    layout_group=layout_model.name,
                    layout=slide_layout.id,
                    index=i,
                    speaker_note=slide_content.get("__speaker_note__", ""),
                    content=slide_content,
                )
                async_asset_generation_tasks.append(
                    process_slide_and_fetch_assets(
                        self.image_service, self.icon_service, slide
                    )
                )
                slides.append(slide)

            self.logger.info("Processing slide assets", 
                           presentation_id=presentation_id,
                           slide_count=len(slides),
                           asset_tasks=len(async_asset_generation_tasks))

            # Process all assets in parallel
            generated_assets_lists = await asyncio.gather(*async_asset_generation_tasks)
            generated_assets = []
            for assets_list in generated_assets_lists:
                generated_assets.extend(assets_list)

            # Save PresentationModel and Slides
            await self.safe_add(presentation)
            await self.safe_add_all(slides)
            await self.safe_add_all(generated_assets)
            await self.safe_commit()

            self.logger.info("Saved presentation to database", 
                           presentation_id=presentation_id,
                           slide_count=len(slides),
                           asset_count=len(generated_assets))

            # Export
            presentation_and_path = await export_presentation(
                presentation_id, presentation.title or get_random_uuid(), request.export_as
            )

            self.log_request_success("generate_complete_presentation", 
                                   presentation_id=presentation_id,
                                   export_format=request.export_as)

            return {
                **presentation_and_path.model_dump(),
                "edit_path": f"/presentation?id={presentation_id}",
            }
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("generate_complete_presentation", e)
            raise HTTPException(status_code=500, detail="Failed to generate complete presentation")
    
    async def create_from_template(self, data) -> dict:
        """
        Create presentation from template.
        
        Args:
            data: GetPresentationUsingTemplateRequest
            
        Returns:
            Dict with presentation path and edit path
        """
        from utils.dict_utils import deep_update
        from utils.export_utils import export_presentation
        
        self.log_request_start("create_from_template", 
                              source_presentation_id=data.presentation_id,
                              export_format=data.export_as)
        
        try:
            presentation = await self.get_or_404(PresentationModel, data.presentation_id)
            
            slides = await self.sql_session.scalars(
                select(SlideModel).where(SlideModel.presentation == data.presentation_id)
            )

            new_presentation = presentation.get_new_presentation()
            new_slides = []
            updated_slides_count = 0
            
            for each_slide in slides:
                updated_content = None
                new_slide_data = list(filter(lambda x: x.index == each_slide.index, data.data))
                if new_slide_data:
                    updated_content = deep_update(each_slide.content, new_slide_data[0].content)
                    updated_slides_count += 1
                    
                new_slides.append(
                    each_slide.get_new_slide(new_presentation.id, updated_content)
                )

            await self.safe_add(new_presentation)
            await self.safe_add_all(new_slides)
            await self.safe_commit()

            self.logger.info("Created presentation from template", 
                           new_presentation_id=new_presentation.id,
                           total_slides=len(new_slides),
                           updated_slides=updated_slides_count)

            presentation_and_path = await export_presentation(
                new_presentation.id, new_presentation.title or get_random_uuid(), data.export_as
            )

            self.log_request_success("create_from_template", 
                                   new_presentation_id=new_presentation.id)

            return {
                **presentation_and_path.model_dump(),
                "edit_path": f"/presentation?id={new_presentation.id}",
            }
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("create_from_template", e)
            raise HTTPException(status_code=500, detail="Failed to create presentation from template")