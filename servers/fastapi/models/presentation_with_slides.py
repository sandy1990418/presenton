from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from pydantic import BaseModel

from models.stateless_models import SlideData


class SlideResponse(BaseModel):
    """Slide data for API responses (no SQL dependency)."""
    content: Dict[str, Any]
    layout_group: str = ""
    layout: str = ""
    index: int = 0
    speaker_note: Optional[str] = None


class PresentationWithSlides(BaseModel):
    """Presentation with slides for API responses (no SQL dependency)."""
    id: str
    content: Optional[str] = None
    n_slides: int
    language: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tone: Optional[str] = None
    verbosity: Optional[str] = None
    slides: List[SlideResponse]
