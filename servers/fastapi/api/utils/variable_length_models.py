from typing import List, Optional
from pydantic import Field
from ppt_config_generator.models import (
    PresentationMarkdownModel,
    PresentationStructureModel,
    SlideMarkdownModel,
    SlideStructureModel,
)


class SlideMarkdownModelWithValidation(SlideMarkdownModel):
    title: str = Field(
        description="Title of the slide in about 3 to 5 words",
        min_length=10,
        max_length=50,
    )
    
    class Config:
        json_schema_extra = {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the slide in about 3 to 5 words",
                    "minLength": 10,
                    "maxLength": 50
                },
                "body": {
                    "type": "string",
                    "description": "Content of the slide in markdown format"
                }
            },
            "required": ["title", "body"]
        }


def get_presentation_markdown_model_with_n_slides(n_slides: int):
    class PresentationMarkdownModelWithNSlides(PresentationMarkdownModel):
        title: str = Field(
            description="Title of the presentation in about 3 to 8 words",
            min_length=10,
            max_length=50,
        )
        notes: Optional[List[str]] = Field(
            description="Important notes for the presentation styling and formatting",
            min_length=0,
            max_length=10,
        )
        slides: List[SlideMarkdownModelWithValidation] = Field(
            description="List of slides", min_items=n_slides, max_items=n_slides
        )
        
        class Config:
            json_schema_extra = {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the presentation in about 3 to 8 words",
                        "minLength": 10,
                        "maxLength": 50
                    },
                    "notes": {
                        "type": "array",
                        "description": "Important notes for the presentation styling and formatting",
                        "minItems": 0,
                        "maxItems": 10,
                        "items": {
                            "type": "string"
                        }
                    },
                    "slides": {
                        "type": "array",
                        "description": "List of slides",
                        "minItems": n_slides,
                        "maxItems": n_slides,
                        "items": {
                            "type": "object"
                        }
                    }
                },
                "required": ["title", "slides"]
            }

    return PresentationMarkdownModelWithNSlides


def get_presentation_structure_model_with_n_slides(n_slides: int):
    class PresentationStructureModelWithNSlides(PresentationStructureModel):
        slides: List[SlideStructureModel] = Field(
            description="List of slide structure",
            min_items=n_slides,
            max_items=n_slides,
        )
        
        class Config:
            json_schema_extra = {
                "type": "object",
                "properties": {
                    "slides": {
                        "type": "array",
                        "description": "List of slide structure",
                        "minItems": n_slides,
                        "maxItems": n_slides,
                        "items": {
                            "type": "object"
                        }
                    }
                },
                "required": ["slides"]
            }

    return PresentationStructureModelWithNSlides
