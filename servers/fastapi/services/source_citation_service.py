"""
Source Citation Service

Manages web search source citations and provides clickable domain links
for presentations that use web search results.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SourceCitation:
    """Represents a source citation with URL and domain information"""
    url: str
    domain: str
    title: str
    content_snippet: str
    search_query: str
    relevance_score: float = 0.0

class SourceCitationService:
    """Service for managing web search source citations in presentations"""
    
    def __init__(self):
        self.presentation_sources: Dict[str, List[SourceCitation]] = {}
        
    def extract_domain_from_url(self, url: str) -> str:
        """Extract domain name from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            # Remove 'www.' prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception:
            return "Unknown Domain"
    
    def add_search_results_to_presentation(
        self, 
        presentation_id: str, 
        search_results: List[Dict[str, Any]], 
        search_query: str
    ) -> None:
        """
        Add search results as citations for a presentation
        
        Args:
            presentation_id: ID of the presentation
            search_results: List of search result dictionaries
            search_query: The search query that generated these results
        """
        if presentation_id not in self.presentation_sources:
            self.presentation_sources[presentation_id] = []
        
        for result in search_results:
            url = result.get('url', '')
            if url:
                citation = SourceCitation(
                    url=url,
                    domain=self.extract_domain_from_url(url),
                    title=result.get('title', 'Unknown Title'),
                    content_snippet=result.get('content', '')[:200] + "..." if result.get('content') else "",
                    search_query=search_query,
                    relevance_score=result.get('relevance_score', 0.0)
                )
                
                # Avoid duplicate citations
                existing_urls = {c.url for c in self.presentation_sources[presentation_id]}
                if url not in existing_urls:
                    self.presentation_sources[presentation_id].append(citation)
                    logger.info(f"Added citation from {citation.domain} for presentation {presentation_id}")
    
    def get_presentation_citations(self, presentation_id: str) -> List[Dict[str, Any]]:
        """
        Get all citations for a presentation in a format suitable for frontend display
        
        Args:
            presentation_id: ID of the presentation
            
        Returns:
            List of citation dictionaries with display formatting
        """
        citations = self.presentation_sources.get(presentation_id, [])
        
        # Group citations by domain to avoid redundancy
        domain_citations = {}
        for citation in citations:
            if citation.domain not in domain_citations:
                domain_citations[citation.domain] = {
                    "domain": citation.domain,
                    "url": citation.url,
                    "title": citation.title,
                    "queries": [citation.search_query],
                    "relevance_score": citation.relevance_score
                }
            else:
                # Add query if not already present
                if citation.search_query not in domain_citations[citation.domain]["queries"]:
                    domain_citations[citation.domain]["queries"].append(citation.search_query)
                # Update relevance score if higher
                if citation.relevance_score > domain_citations[citation.domain]["relevance_score"]:
                    domain_citations[citation.domain]["relevance_score"] = citation.relevance_score
        
        # Convert to list and sort by relevance
        result = list(domain_citations.values())
        result.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return result
    
    def generate_citations_footer(self, presentation_id: str) -> str:
        """
        Generate a formatted citations footer for presentation slides
        
        Args:
            presentation_id: ID of the presentation
            
        Returns:
            Formatted citation text for display
        """
        citations = self.get_presentation_citations(presentation_id)
        
        if not citations:
            return ""
        
        # Create a compact footer with main domains
        domain_names = [c["domain"] for c in citations[:3]]  # Limit to top 3 sources
        
        if len(citations) > 3:
            footer = f"Sources: {', '.join(domain_names)} and {len(citations) - 3} more"
        else:
            footer = f"Sources: {', '.join(domain_names)}"
        
        return footer
    
    def get_citation_links_for_slide(self, presentation_id: str, slide_content: str) -> List[Dict[str, Any]]:
        """
        Get relevant citation links for a specific slide based on content similarity
        
        Args:
            presentation_id: ID of the presentation
            slide_content: Content of the slide to match citations against
            
        Returns:
            List of relevant citation links
        """
        citations = self.presentation_sources.get(presentation_id, [])
        
        if not citations:
            return []
        
        # Simple keyword matching for relevance
        slide_keywords = set(slide_content.lower().split())
        relevant_citations = []
        
        for citation in citations:
            # Check if search query keywords appear in slide content
            query_keywords = set(citation.search_query.lower().split())
            overlap = len(slide_keywords & query_keywords)
            
            if overlap > 0:
                relevant_citations.append({
                    "domain": citation.domain,
                    "url": citation.url,
                    "title": citation.title,
                    "relevance": overlap / len(query_keywords) if query_keywords else 0
                })
        
        # Sort by relevance and return top results
        relevant_citations.sort(key=lambda x: x["relevance"], reverse=True)
        return relevant_citations[:2]  # Limit to 2 most relevant citations per slide
    
    def clear_presentation_citations(self, presentation_id: str) -> None:
        """Clear all citations for a presentation"""
        if presentation_id in self.presentation_sources:
            del self.presentation_sources[presentation_id]
            logger.info(f"Cleared citations for presentation {presentation_id}")

# Global instance
citation_service = SourceCitationService()