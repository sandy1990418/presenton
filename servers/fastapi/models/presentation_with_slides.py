from typing import List, Optional
from datetime import datetime
import uuid

from pydantic import BaseModel

from models.sql.slide import SlideModel


class PresentationWithSlides(BaseModel):
    id: str
    content: Optional[str] = None
    n_slides: int
    language: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tone: Optional[str] = None
    verbosity: Optional[str] = None
    slides: List[SlideModel]
