from typing import List, Optional
from pydantic import BaseModel, Field


class SlideStructureModel(BaseModel):
    type: int = Field(description="Type of the slide", gte=1, lte=9)
    
    class Config:
        json_schema_extra = {
            "type": "object",
            "properties": {
                "type": {
                    "type": "integer",
                    "description": "Type of the slide",
                    "minimum": 1,
                    "maximum": 9
                }
            },
            "required": ["type"]
        }


class PresentationStructureModel(BaseModel):
    slides: List[SlideStructureModel] = Field(description="List of slide structure")
    
    class Config:
        json_schema_extra = {
            "type": "object",
            "properties": {
                "slides": {
                    "type": "array",
                    "description": "List of slide structure",
                    "items": {
                        "type": "object"
                    }
                }
            },
            "required": ["slides"]
        }


class SlideMarkdownModel(BaseModel):
    title: str = Field(
        description="Title of the slide in about 3 to 5 words",
    )
    body: str = Field(
        description="Content of the slide in markdown format",
    )
    
    class Config:
        json_schema_extra = {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the slide in about 3 to 5 words"
                },
                "body": {
                    "type": "string",
                    "description": "Content of the slide in markdown format"
                }
            },
            "required": ["title", "body"]
        }


class PresentationMarkdownModel(BaseModel):
    title: str = Field(
        description="Title of the presentation in about 3 to 8 words",
    )
    notes: Optional[List[str]] = Field(description="Notes for the presentation")
    slides: List[SlideMarkdownModel] = Field(description="List of slides")
    
    class Config:
        json_schema_extra = {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the presentation in about 3 to 8 words"
                },
                "notes": {
                    "type": "array",
                    "description": "Notes for the presentation",
                    "items": {
                        "type": "string"
                    }
                },
                "slides": {
                    "type": "array",
                    "description": "List of slides",
                    "items": {
                        "type": "object"
                    }
                }
            },
            "required": ["title", "slides"]
        }

    def to_string(self):
        message = f"# Presentation Title: {self.title} \n\n"
        for i, slide in enumerate(self.slides):
            message += f"## Slide {i+1}:\n"
            message += f"  - Title: {slide.title} \n"
            message += f"  - Body: {slide.body} \n"

        if self.notes:
            message += f"# Notes: \n"
            for note in self.notes:
                message += f"  - {note} \n"
        return message
