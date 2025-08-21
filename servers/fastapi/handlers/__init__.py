"""
Handlers package for Presenton FastAPI server.
Contains business logic handlers that use mixins for common functionality.
"""

# Import handlers - these depend on mixins being available
from .presentation_handler import PresentationHandler
from .slide_handler import SlideHandler
from .outline_handler import OutlineHandler
from .slide_to_html_handler import SlideToHtmlHandler
from .pptx_slides_handler import PptxSlidesHandler
from .pdf_slides_handler import PdfSlidesHandler
from .fonts_handler import FontsHandler
from .files_handler import FilesHandler

__all__ = [
    "PresentationHandler",
    "SlideHandler",
    "OutlineHandler",
    "SlideToHtmlHandler",
    "PptxSlidesHandler",
    "PdfSlidesHandler",
    "FontsHandler",
    "FilesHandler",
]