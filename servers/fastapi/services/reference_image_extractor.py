"""
Reference Image Extraction Service

Extracts images from reference documents and determines optimal placement
in presentation slides using LLM-based analysis.
"""

import asyncio
import logging
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from utils.llm_provider import get_llm_client, get_large_model, is_google_selected
from services.image_embedding_service import ImageEmbeddingService

logger = logging.getLogger(__name__)

@dataclass
class ExtractedReferenceImage:
    """Represents an image extracted from reference material"""
    image_data: bytes
    image_url: Optional[str]
    context_text: str
    caption: Optional[str]
    alt_text: Optional[str]
    position_in_document: int
    relevance_score: float
    suggested_placement: str

class ReferenceImageExtractor:
    """Service for extracting and analyzing images from reference documents"""
    
    def __init__(self):
        self.embedding_service = ImageEmbeddingService()
        
    async def analyze_document_for_images(self, document_content: str, document_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze document content to identify image locations and relevance using LLM
        
        Args:
            document_content: The text content of the document
            document_url: Optional URL of the document for image extraction
            
        Returns:
            Analysis results with image locations and relevance scores
        """
        system_prompt = """
        You are an expert document analyst. Analyze the provided document content to identify:
        
        1. **Image Locations**: Where images are likely positioned based on text references
        2. **Image Relevance**: How relevant each image reference is to key concepts
        3. **Contextual Information**: What each image likely depicts based on surrounding text
        4. **Placement Priority**: How important each image would be for a presentation
        
        Look for:
        - Direct image references: "Figure 1", "Image shows", "See diagram", etc.
        - Descriptive text that indicates visual content: "chart", "graph", "screenshot", "diagram"
        - Contextual clues about what images contain
        - Educational or explanatory value of images
        
        Return a JSON structure with image analysis.
        """
        
        user_prompt = f"""
        Document Content:
        {document_content[:8000]}  # Limit content to avoid token limits
        
        Document URL: {document_url or "Not provided"}
        
        Please analyze this document and identify potential images with their context and relevance.
        """
        
        model = get_large_model()
        
        if not is_google_selected():
            client = get_llm_client()
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "ImageAnalysis",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "identified_images": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "position": {"type": "integer"},
                                                "context_text": {"type": "string"},
                                                "likely_content": {"type": "string"},
                                                "relevance_score": {"type": "number", "minimum": 0, "maximum": 1},
                                                "image_type": {"type": "string", "enum": ["chart", "diagram", "screenshot", "photo", "illustration", "graph", "table"]},
                                                "placement_priority": {"type": "number", "minimum": 0, "maximum": 1},
                                                "suggested_slide_placement": {"type": "string", "enum": ["header", "content", "sidebar", "background", "full-slide"]}
                                            },
                                            "required": ["position", "context_text", "likely_content", "relevance_score", "image_type", "placement_priority", "suggested_slide_placement"]
                                        }
                                    },
                                    "document_summary": {"type": "string"},
                                    "key_concepts": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    }
                                },
                                "required": ["identified_images", "document_summary", "key_concepts"]
                            }
                        }
                    }
                )
                return json.loads(response.choices[0].message.content)
            except Exception as e:
                logger.exception("Failed to analyze document with OpenAI")
                return self._fallback_image_analysis(document_content)
        else:
            # Google Gemini fallback
            try:
                from utils.llm_provider import get_google_llm_client
                from google.genai.types import GenerateContentConfig
                
                client = get_google_llm_client()
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=[user_prompt],
                    config=GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json"
                    )
                )
                return json.loads(response.text)
            except Exception as e:
                logger.exception("Failed to analyze document with Gemini")
                return self._fallback_image_analysis(document_content)
    
    def _fallback_image_analysis(self, content: str) -> Dict[str, Any]:
        """Fallback analysis using simple text patterns"""
        import re
        
        # Simple pattern-based image detection
        image_patterns = [
            r'figure\s+\d+',
            r'image\s+\d+',
            r'diagram\s+\d+',
            r'chart\s+\d+',
            r'graph\s+\d+',
            r'screenshot',
            r'see\s+(image|figure|diagram|chart)',
        ]
        
        identified_images = []
        for i, pattern in enumerate(image_patterns):
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Extract context around the match
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 100)
                context = content[start:end]
                
                identified_images.append({
                    "position": match.start(),
                    "context_text": context,
                    "likely_content": f"Visual content referenced by: {match.group()}",
                    "relevance_score": 0.6,  # Default moderate relevance
                    "image_type": "illustration",
                    "placement_priority": 0.5,
                    "suggested_slide_placement": "content"
                })
        
        return {
            "identified_images": identified_images[:10],  # Limit to 10 images
            "document_summary": content[:200] + "..." if len(content) > 200 else content,
            "key_concepts": ["visual content", "reference material"]
        }
    
    async def match_reference_images_to_slides(
        self, 
        reference_analysis: Dict[str, Any], 
        slide_outlines: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Match identified reference images to specific slides based on content similarity
        
        Args:
            reference_analysis: Results from analyze_document_for_images
            slide_outlines: List of slide outline dictionaries
            
        Returns:
            List of image-to-slide matches with placement suggestions
        """
        if not reference_analysis.get("identified_images"):
            return []
        
        matches = []
        
        for image_info in reference_analysis["identified_images"]:
            best_slide_index = 0
            best_score = 0
            
            # Simple keyword matching for slide relevance
            image_keywords = self._extract_keywords(image_info["context_text"] + " " + image_info["likely_content"])
            
            for slide_index, slide_outline in enumerate(slide_outlines):
                slide_text = f"{slide_outline.get('title', '')} {slide_outline.get('body', '')}"
                slide_keywords = self._extract_keywords(slide_text)
                
                # Calculate keyword overlap score
                overlap = len(set(image_keywords) & set(slide_keywords))
                score = overlap / max(len(image_keywords), 1)
                
                if score > best_score:
                    best_score = score
                    best_slide_index = slide_index
            
            if best_score > 0.1:  # Minimum relevance threshold
                matches.append({
                    "slide_index": best_slide_index,
                    "slide_title": slide_outlines[best_slide_index].get("title", f"Slide {best_slide_index + 1}"),
                    "image_info": image_info,
                    "relevance_score": best_score,
                    "placement_suggestion": image_info["suggested_slide_placement"],
                    "confidence": min(best_score * image_info["relevance_score"], 1.0)
                })
        
        # Sort by confidence score
        matches.sort(key=lambda x: x["confidence"], reverse=True)
        
        return matches
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text"""
        import re
        
        # Simple keyword extraction
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter out common words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'
        }
        
        keywords = [word for word in words if len(word) > 3 and word not in stop_words]
        
        # Return unique keywords, limited to top 20
        return list(set(keywords))[:20]
    
    async def process_reference_document(
        self, 
        document_content: str, 
        slide_outlines: List[Dict[str, Any]],
        document_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete pipeline for processing a reference document and matching images to slides
        
        Args:
            document_content: The content of the reference document
            slide_outlines: List of slide outlines to match images to
            document_url: Optional URL for the document
            
        Returns:
            Complete processing results with matched images
        """
        try:
            # Step 1: Analyze document for images
            logger.info("Analyzing reference document for images...")
            analysis = await self.analyze_document_for_images(document_content, document_url)
            
            # Step 2: Match images to slides
            logger.info(f"Matching {len(analysis.get('identified_images', []))} identified images to slides...")
            matches = await self.match_reference_images_to_slides(analysis, slide_outlines)
            
            return {
                "success": True,
                "document_analysis": analysis,
                "image_matches": matches,
                "total_images_identified": len(analysis.get("identified_images", [])),
                "total_matches": len(matches),
                "processing_summary": f"Identified {len(analysis.get('identified_images', []))} potential images, matched {len(matches)} to slides"
            }
            
        except Exception as e:
            logger.exception("Failed to process reference document")
            return {
                "success": False,
                "error": str(e),
                "document_analysis": None,
                "image_matches": [],
                "total_images_identified": 0,
                "total_matches": 0,
                "processing_summary": f"Processing failed: {str(e)}"
            }