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
        description="Compelling slide title that captures attention and conveys key message",
        min_length=10,
        max_length=100,
    )
    body: str = Field(
        description="Comprehensive slide content in markdown format with substantial insights, examples, and actionable points",
        min_length=50,
        max_length=2000,
    )
    
    class Config:
        json_schema_extra = {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Compelling slide title that captures attention and conveys key message",
                    "minLength": 10,
                    "maxLength": 100
                },
                "body": {
                    "type": "string",
                    "description": "Comprehensive slide content in markdown format with substantial insights, examples, and actionable points",
                    "minLength": 50,
                    "maxLength": 2000
                },
                "speaker_notes": {
                    "type": "string",
                    "description": "Detailed speaker notes with talking points, transitions, and additional context"
                },
                "visual_suggestions": {
                    "type": "string",
                    "description": "Specific suggestions for charts, images, and visual elements placement"
                },
                "estimated_time": {
                    "type": "integer",
                    "description": "Estimated presentation time for this slide in minutes"
                }
            },
            "required": ["title", "body"]
        }


def get_presentation_markdown_model_with_n_slides(n_slides: int):
    class PresentationMarkdownModelWithNSlides(PresentationMarkdownModel):
        title: str = Field(
            description="Compelling presentation title that captures the core message and value proposition",
            min_length=10,
            max_length=100,
        )
        executive_summary: Optional[str] = Field(
            description="Brief executive summary highlighting key insights and outcomes",
            default=""
        )
        notes: Optional[List[str]] = Field(
            description="Strategic notes for the presentation including key messages and call-to-actions",
            min_length=0,
            max_length=10,
        )
        total_estimated_time: Optional[int] = Field(
            description="Total estimated presentation time in minutes",
            default=10
        )
        target_audience: Optional[str] = Field(
            description="Primary target audience for this presentation",
            default="Business professionals"
        )
        key_takeaways: Optional[List[str]] = Field(
            description="Main takeaways and action items from the presentation",
            default_factory=list
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
