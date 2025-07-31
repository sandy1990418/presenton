"""
Image Embedding Service

Matches extracted images with presentation content using semantic embeddings
to determine optimal placement locations.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import asyncio
from dataclasses import dataclass

# Try to import optional dependencies with fallbacks
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

try:
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    np = None
    cosine_similarity = None

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

logger = logging.getLogger(__name__)

@dataclass
class ImageMatch:
    """Represents a match between an image and slide content"""
    image_data: Dict[str, Any]
    slide_index: int
    slide_title: str
    slide_content: str
    similarity_score: float
    placement_suggestion: str  # "header", "content", "sidebar", "background"
    confidence: float

@dataclass  
class ProcessedImage:
    """Processed image with embeddings and metadata"""
    original_data: Dict[str, Any]
    text_embedding: Optional[Any]  # Changed from np.ndarray to Any for compatibility
    context_keywords: List[str]
    placement_priority: float

class ImageEmbeddingService:
    """Service for matching images with slide content using embeddings"""
    
    def __init__(self):
        self.text_model = None
        self.model_loaded = False
        
    async def initialize_models(self):
        """Initialize embedding models using existing OpenAI/Gemini APIs"""
        try:
            # Use existing LLM providers instead of local models
            from utils.llm_provider import get_llm_client, is_google_selected
            
            if is_google_selected():
                # Use Google Gemini for embeddings (if available)
                logger.info("Using Google Gemini API for embeddings")
                self.text_model = "gemini"
                self.model_loaded = True
            else:
                # Use OpenAI for embeddings
                self.text_model = get_llm_client()
                logger.info("Using OpenAI API for embeddings")
                self.model_loaded = True
                
        except Exception as e:
            logger.error(f"Failed to initialize embedding APIs: {e}")
            self.model_loaded = False
    
    async def process_extracted_images(self, images_data: List[Dict[str, Any]]) -> List[ProcessedImage]:
        """Process extracted images and create embeddings"""
        if not self.model_loaded:
            await self.initialize_models()
        
        if not self.model_loaded:
            logger.warning("Models not loaded, using fallback processing")
            return await self._process_images_fallback(images_data)
        
        processed_images = []
        
        for image_data in images_data:
            try:
                processed_image = await self._process_single_image(image_data)
                if processed_image:
                    processed_images.append(processed_image)
            except Exception as e:
                logger.error(f"Failed to process image: {e}")
        
        return processed_images
    
    async def _process_single_image(self, image_data: Dict[str, Any]) -> Optional[ProcessedImage]:
        """Process a single image and create embeddings"""
        try:
            # Extract text context
            context_text = image_data.get('contextText', '')
            alt_text = image_data.get('altText', '')
            caption = image_data.get('caption', '')
            
            # Combine all text context
            full_context = f"{context_text} {alt_text} {caption}".strip()
            
            if not full_context:
                logger.warning("No text context found for image, using placeholder")
                full_context = "image content visual element"
            
            # Create text embedding using API
            text_embedding = await self._create_embedding_via_api(full_context)
            
            # Extract keywords for better matching
            keywords = self._extract_keywords(full_context)
            
            # Calculate placement priority based on image characteristics
            placement_priority = self._calculate_placement_priority(image_data)
            
            return ProcessedImage(
                original_data=image_data,
                text_embedding=text_embedding,
                context_keywords=keywords,
                placement_priority=placement_priority
            )
            
        except Exception as e:
            logger.error(f"Failed to process single image: {e}")
            return None
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from image context"""
        # Simple keyword extraction - could be enhanced with NLP
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'had', 'has', 'this', 'that', 'these', 'those'
        }
        
        words = text.lower().split()
        keywords = [word.strip('.,!?;:') for word in words 
                   if len(word) > 3 and word.lower() not in stop_words]
        
        # Return unique keywords, limited to most relevant
        return list(set(keywords))[:10]
    
    def _calculate_placement_priority(self, image_data: Dict[str, Any]) -> float:
        """Calculate placement priority based on image characteristics"""
        priority = 0.5  # Base priority
        
        # Consider image size
        width = image_data.get('position', {}).get('width', 0)
        height = image_data.get('position', {}).get('height', 0)
        
        if width > 800 or height > 600:
            priority += 0.3  # Large images get higher priority
        elif width < 200 and height < 200:
            priority -= 0.2  # Small images get lower priority
        
        # Consider context length
        context_length = len(image_data.get('contextText', ''))
        if context_length > 100:
            priority += 0.2  # More context = higher priority
        
        # Consider presence of alt text or caption
        if image_data.get('altText') or image_data.get('caption'):
            priority += 0.1
        
        return min(1.0, max(0.0, priority))
    
    async def match_images_to_slides(
        self, 
        processed_images: List[ProcessedImage], 
        slide_outlines: List[Dict[str, Any]]
    ) -> List[ImageMatch]:
        """Match processed images to slide outlines using embeddings"""
        if not self.model_loaded:
            await self.initialize_models()
        
        if not self.model_loaded:
            logger.warning("Using fallback keyword matching instead of embeddings")
            return await self._match_images_fallback(processed_images, slide_outlines)
        
        if not processed_images or not slide_outlines:
            return []
        
        matches = []
        
        # Create embeddings for slide content
        slide_texts = []
        for slide in slide_outlines:
            slide_text = f"{slide.get('title', '')} {slide.get('body', '')}".strip()
            slide_texts.append(slide_text)
        
        if not slide_texts:
            return []
        
        try:
            # Create embeddings for all slide texts using API
            slide_embeddings = []
            for slide_text in slide_texts:
                embedding = await self._create_embedding_via_api(slide_text)
                slide_embeddings.append(embedding)
        except Exception as e:
            logger.error(f"Failed to create slide embeddings: {e}")
            return await self._match_images_fallback(processed_images, slide_outlines)
        
        # Match each image to the best slide
        for processed_image in processed_images:
            try:
                best_match = await self._find_best_slide_match(
                    processed_image, slide_embeddings, slide_outlines
                )
                if best_match:
                    matches.append(best_match)
            except Exception as e:
                logger.error(f"Failed to match image: {e}")
        
        # Sort matches by similarity score (best matches first)
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        
        return matches
    
    async def _find_best_slide_match(
        self, 
        processed_image: ProcessedImage, 
        slide_embeddings: Any,  # Changed from np.ndarray for compatibility
        slide_outlines: List[Dict[str, Any]]
    ) -> Optional[ImageMatch]:
        """Find the best slide match for a processed image"""
        try:
            if processed_image.text_embedding is None:
                # Fall back to keyword matching
                return await self._find_keyword_match(processed_image, slide_outlines)
            
            # Calculate similarities with each slide using API embeddings
            similarities = []
            for slide_embedding in slide_embeddings:
                similarity = self._calculate_api_similarity(
                    processed_image.text_embedding, 
                    slide_embedding
                )
                similarities.append(similarity)
            
            # Find best match
            best_idx = similarities.index(max(similarities))
            best_score = similarities[best_idx]
            
            # Apply minimum threshold
            if best_score < 0.1:  # Very low similarity threshold
                return None
            
            # Enhance score with keyword matching
            enhanced_score = self._enhance_score_with_keywords(
                processed_image, slide_outlines[best_idx], best_score
            )
            
            # Determine placement suggestion
            placement = self._suggest_placement(processed_image, slide_outlines[best_idx])
            
            # Calculate confidence
            confidence = self._calculate_confidence(enhanced_score, processed_image)
            
            return ImageMatch(
                image_data=processed_image.original_data,
                slide_index=best_idx,
                slide_title=slide_outlines[best_idx].get('title', ''),
                slide_content=slide_outlines[best_idx].get('body', ''),
                similarity_score=enhanced_score,
                placement_suggestion=placement,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Failed to find best slide match: {e}")
            return None
    
    def _enhance_score_with_keywords(
        self, 
        processed_image: ProcessedImage, 
        slide_outline: Dict[str, Any], 
        base_score: float
    ) -> float:
        """Enhance similarity score with keyword matching"""
        slide_text = f"{slide_outline.get('title', '')} {slide_outline.get('body', '')}".lower()
        
        keyword_matches = 0
        for keyword in processed_image.context_keywords:
            if keyword.lower() in slide_text:
                keyword_matches += 1
        
        # Boost score based on keyword matches
        keyword_boost = min(0.3, keyword_matches * 0.05)
        
        return min(1.0, base_score + keyword_boost)
    
    def _suggest_placement(
        self, 
        processed_image: ProcessedImage, 
        slide_outline: Dict[str, Any]
    ) -> str:
        """Suggest where to place the image on the slide"""
        width = processed_image.original_data.get('position', {}).get('width', 0)
        height = processed_image.original_data.get('position', {}).get('height', 0)
        
        # Large horizontal images
        if width > height and width > 600:
            return "header"
        
        # Large vertical images
        elif height > width and height > 400:
            return "sidebar"
        
        # Square or medium images
        elif width > 300 and height > 300:
            return "content"
        
        # Small images
        else:
            return "inline"
    
    def _calculate_confidence(self, similarity_score: float, processed_image: ProcessedImage) -> float:
        """Calculate confidence in the image-slide match"""
        confidence = similarity_score
        
        # Boost confidence for images with rich context
        if len(processed_image.context_keywords) > 5:
            confidence += 0.1
        
        # Boost confidence for high-priority images
        confidence += processed_image.placement_priority * 0.2
        
        return min(1.0, confidence)
    
    async def optimize_image_distribution(self, matches: List[ImageMatch]) -> List[ImageMatch]:
        """Optimize image distribution across slides to avoid overcrowding"""
        if not matches:
            return matches
        
        # Count images per slide
        slide_image_count = {}
        for match in matches:
            slide_idx = match.slide_index
            slide_image_count[slide_idx] = slide_image_count.get(slide_idx, 0) + 1
        
        # Redistribute if any slide has too many images
        optimized_matches = []
        max_images_per_slide = 2
        
        for match in matches:
            slide_idx = match.slide_index
            
            # If slide has too many images, only keep the best ones
            if slide_image_count[slide_idx] <= max_images_per_slide:
                optimized_matches.append(match)
            else:
                # Keep only if it's a high-confidence match
                if match.confidence > 0.7:
                    optimized_matches.append(match)
        
        return optimized_matches
    
    async def _process_images_fallback(self, images_data: List[Dict[str, Any]]) -> List[ProcessedImage]:
        """Fallback image processing when embeddings aren't available"""
        processed_images = []
        
        for image_data in images_data:
            try:
                # Extract text context
                context_text = image_data.get('contextText', '')
                alt_text = image_data.get('altText', '')
                caption = image_data.get('caption', '')
                
                # Combine all text context
                full_context = f"{context_text} {alt_text} {caption}".strip()
                
                if not full_context:
                    full_context = "image content visual element"
                
                # Extract keywords for better matching
                keywords = self._extract_keywords(full_context)
                
                # Calculate placement priority based on image characteristics
                placement_priority = self._calculate_placement_priority(image_data)
                
                processed_images.append(ProcessedImage(
                    original_data=image_data,
                    text_embedding=None,  # No embedding in fallback mode
                    context_keywords=keywords,
                    placement_priority=placement_priority
                ))
                
            except Exception as e:
                logger.error(f"Failed to process single image in fallback mode: {e}")
        
        return processed_images
    
    async def _match_images_fallback(
        self, 
        processed_images: List[ProcessedImage], 
        slide_outlines: List[Dict[str, Any]]
    ) -> List[ImageMatch]:
        """Fallback matching using keyword similarity when embeddings aren't available"""
        matches = []
        
        for processed_image in processed_images:
            try:
                best_match = await self._find_keyword_match(processed_image, slide_outlines)
                if best_match:
                    matches.append(best_match)
            except Exception as e:
                logger.error(f"Failed to match image in fallback mode: {e}")
        
        # Sort matches by confidence (best matches first)
        matches.sort(key=lambda x: x.confidence, reverse=True)
        
        return matches
    
    async def _find_keyword_match(
        self, 
        processed_image: ProcessedImage, 
        slide_outlines: List[Dict[str, Any]]
    ) -> Optional[ImageMatch]:
        """Find the best slide match using keyword matching"""
        try:
            best_score = 0.0
            best_idx = 0
            
            # Simple keyword matching
            for idx, slide_outline in enumerate(slide_outlines):
                slide_text = f"{slide_outline.get('title', '')} {slide_outline.get('body', '')}".lower()
                
                keyword_matches = 0
                for keyword in processed_image.context_keywords:
                    if keyword.lower() in slide_text:
                        keyword_matches += 1
                
                # Calculate simple similarity score
                if processed_image.context_keywords:
                    score = keyword_matches / len(processed_image.context_keywords)
                else:
                    score = 0.1  # Default low score
                
                if score > best_score:
                    best_score = score
                    best_idx = idx
            
            # Apply minimum threshold
            if best_score < 0.1:
                return None
            
            # Determine placement suggestion
            placement = self._suggest_placement(processed_image, slide_outlines[best_idx])
            
            # Calculate confidence
            confidence = min(0.8, best_score + processed_image.placement_priority * 0.2)
            
            return ImageMatch(
                image_data=processed_image.original_data,
                slide_index=best_idx,
                slide_title=slide_outlines[best_idx].get('title', ''),
                slide_content=slide_outlines[best_idx].get('body', ''),
                similarity_score=best_score,
                placement_suggestion=placement,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Failed to find keyword match: {e}")
            return None
    
    async def _create_embedding_via_api(self, text: str) -> Optional[List[float]]:
        """Create embedding using OpenAI or Gemini API"""
        try:
            if self.text_model == "gemini":
                # Use Google Gemini for embeddings (simplified approach)
                return await self._create_gemini_embedding(text)
            else:
                # Use OpenAI for embeddings
                return await self._create_openai_embedding(text)
        except Exception as e:
            logger.error(f"Failed to create API embedding: {e}")
            return None
    
    async def _create_openai_embedding(self, text: str) -> Optional[List[float]]:
        """Create embedding using OpenAI API"""
        try:
            # Use the existing OpenAI client
            response = await self.text_model.embeddings.create(
                model="text-embedding-3-small",  # Efficient and cost-effective
                input=text,
                dimensions=384  # Smaller dimension for efficiency
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            return None
    
    async def _create_gemini_embedding(self, text: str) -> Optional[List[float]]:
        """Create embedding using Gemini API (placeholder)"""
        try:
            # Note: Gemini doesn't have a dedicated embedding API like OpenAI
            # For now, fall back to keyword-based approach
            logger.warning("Gemini embeddings not implemented, using fallback")
            return None
            
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            return None
    
    def _calculate_api_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between API embeddings"""
        try:
            if not embedding1 or not embedding2:
                return 0.0
            
            # Ensure same dimensions
            if len(embedding1) != len(embedding2):
                return 0.0
            
            # Cosine similarity calculation
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            magnitude_a = sum(a * a for a in embedding1) ** 0.5
            magnitude_b = sum(b * b for b in embedding2) ** 0.5
            
            if magnitude_a == 0 or magnitude_b == 0:
                return 0.0
            
            return dot_product / (magnitude_a * magnitude_b)
            
        except Exception as e:
            logger.error(f"Error calculating API similarity: {e}")
            return 0.0