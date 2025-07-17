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
        description="Compelling slide title that captures attention and conveys key message",
    )
    body: str = Field(
        description="Comprehensive slide content in markdown format with substantial insights, examples, and actionable points",
    )
    speaker_notes: Optional[str] = Field(
        description="Detailed speaker notes with talking points, transitions, and additional context",
        default=""
    )
    visual_suggestions: Optional[str] = Field(
        description="Specific suggestions for charts, images, and visual elements placement",
        default=""
    )
    estimated_time: Optional[int] = Field(
        description="Estimated presentation time for this slide in minutes",
        default=2
    )
    
    class Config:
        json_schema_extra = {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Compelling slide title that captures attention and conveys key message"
                },
                "body": {
                    "type": "string",
                    "description": "Comprehensive slide content in markdown format with substantial insights, examples, and actionable points"
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


class PresentationMarkdownModel(BaseModel):
    title: str = Field(
        description="Compelling presentation title that captures the core message and value proposition",
    )
    executive_summary: Optional[str] = Field(
        description="Brief executive summary highlighting key insights and outcomes",
        default=""
    )
    notes: Optional[List[str]] = Field(description="Strategic notes for the presentation including key messages and call-to-actions")
    slides: List[SlideMarkdownModel] = Field(description="List of professionally crafted slides with comprehensive content")
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
    
    class Config:
        json_schema_extra = {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Compelling presentation title that captures the core message and value proposition"
                },
                "executive_summary": {
                    "type": "string",
                    "description": "Brief executive summary highlighting key insights and outcomes"
                },
                "notes": {
                    "type": "array",
                    "description": "Strategic notes for the presentation including key messages and call-to-actions",
                    "items": {
                        "type": "string"
                    }
                },
                "slides": {
                    "type": "array",
                    "description": "List of professionally crafted slides with comprehensive content",
                    "items": {
                        "type": "object"
                    }
                },
                "total_estimated_time": {
                    "type": "integer",
                    "description": "Total estimated presentation time in minutes"
                },
                "target_audience": {
                    "type": "string",
                    "description": "Primary target audience for this presentation"
                },
                "key_takeaways": {
                    "type": "array",
                    "description": "Main takeaways and action items from the presentation",
                    "items": {
                        "type": "string"
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
