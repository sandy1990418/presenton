"""
AssetServicesMixin provides standardized asset service management for handlers.
"""

from typing import Optional
from services.image_generation_service import ImageGenerationService
from services.icon_finder_service import IconFinderService
from utils.asset_directory_utils import get_images_directory

from .logging_mixin import LoggingMixin


class AssetServicesMixin(LoggingMixin):
    """Provides standardized asset service initialization and management."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._image_service: Optional[ImageGenerationService] = None
        self._icon_service: Optional[IconFinderService] = None
    
    @property
    def image_service(self) -> ImageGenerationService:
        """Lazy-initialized image generation service."""
        if self._image_service is None:
            self.log_external_service_call("ImageGenerationService", "initialize")
            try:
                images_directory = get_images_directory()
                self._image_service = ImageGenerationService(images_directory)
                self.logger.info(
                    "Image generation service initialized",
                    service="ImageGenerationService",
                    directory=images_directory
                )
            except Exception as e:
                self.log_request_error("image_service_init", e)
                raise
        
        return self._image_service
    
    @property 
    def icon_service(self) -> IconFinderService:
        """Lazy-initialized icon finder service."""
        if self._icon_service is None:
            self.log_external_service_call("IconFinderService", "initialize")
            try:
                self._icon_service = IconFinderService()
                self.logger.info(
                    "Icon finder service initialized",
                    service="IconFinderService"
                )
            except Exception as e:
                self.log_request_error("icon_service_init", e)
                raise
        
        return self._icon_service
    
    def cleanup_services(self) -> None:
        """Clean up service resources if needed."""
        if self._image_service is not None:
            self.logger.debug("Cleaning up image service")
            # Add any cleanup logic if needed
            
        if self._icon_service is not None:
            self.logger.debug("Cleaning up icon service")
            # Add any cleanup logic if needed