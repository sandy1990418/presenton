"""
Test cases for Source Citation Service
"""

import pytest
from services.source_citation_service import SourceCitationService, SourceCitation


class TestSourceCitationService:
    """Test the source citation service functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.service = SourceCitationService()
        self.test_presentation_id = "test_presentation_123"
        self.sample_search_results = [
            {
                "title": "Taiwan Tariff Information 2025",
                "content": "Information about Taiwan's import tariffs for 2025...",
                "url": "https://www.example.com/taiwan-tariff-2025",
                "source": "ExampleNews"
            },
            {
                "title": "Economic Analysis - Taiwan Trade",
                "content": "Analysis of Taiwan's trade policies and economic impact...",
                "url": "https://wikipedia.org/wiki/taiwan_trade",
                "source": "Wikipedia"
            },
            {
                "title": "US-Taiwan Trade Relations",
                "content": "Current state of trade relations between US and Taiwan...",
                "url": "https://reuters.com/business/taiwan-us-trade",
                "source": "Reuters"
            }
        ]
    
    def test_extract_domain_from_url(self):
        """Test domain extraction from URLs"""
        test_cases = [
            ("https://www.example.com/path", "example.com"),
            ("https://wikipedia.org/wiki/page", "wikipedia.org"),
            ("http://www.reuters.com/news", "reuters.com"),
            ("https://subdomain.domain.com/path?query=1", "subdomain.domain.com"),
            ("invalid-url", "Unknown Domain")
        ]
        
        for url, expected_domain in test_cases:
            result = self.service.extract_domain_from_url(url)
            assert result == expected_domain, f"Expected {expected_domain}, got {result} for URL {url}"
    
    def test_add_search_results_to_presentation(self):
        """Test adding search results as citations"""
        search_query = "Taiwan tariff 2025"
        
        # Add search results
        self.service.add_search_results_to_presentation(
            self.test_presentation_id, 
            self.sample_search_results, 
            search_query
        )
        
        # Verify citations were added
        citations = self.service.presentation_sources.get(self.test_presentation_id, [])
        assert len(citations) == 3, f"Expected 3 citations, got {len(citations)}"
        
        # Check first citation details
        first_citation = citations[0]
        assert first_citation.url == "https://www.example.com/taiwan-tariff-2025"
        assert first_citation.domain == "example.com"
        assert first_citation.search_query == search_query
        assert "Taiwan Tariff Information 2025" in first_citation.title
    
    def test_get_presentation_citations(self):
        """Test retrieving formatted citations for presentation"""
        # Add test data
        self.service.add_search_results_to_presentation(
            self.test_presentation_id, 
            self.sample_search_results, 
            "Taiwan tariff 2025"
        )
        
        # Get formatted citations
        formatted_citations = self.service.get_presentation_citations(self.test_presentation_id)
        
        assert len(formatted_citations) == 3, f"Expected 3 formatted citations, got {len(formatted_citations)}"
        
        # Check structure of first citation
        first_citation = formatted_citations[0]
        required_keys = ["domain", "url", "title", "queries", "relevance_score"]
        for key in required_keys:
            assert key in first_citation, f"Missing key {key} in citation"
        
        # Check domains are properly extracted
        domains = {c["domain"] for c in formatted_citations}
        expected_domains = {"example.com", "wikipedia.org", "reuters.com"}
        assert domains == expected_domains, f"Expected domains {expected_domains}, got {domains}"
    
    def test_generate_citations_footer(self):
        """Test generating citation footer text"""
        # Test with no citations
        footer = self.service.generate_citations_footer("nonexistent_presentation")
        assert footer == "", "Expected empty footer for nonexistent presentation"
        
        # Add test data
        self.service.add_search_results_to_presentation(
            self.test_presentation_id, 
            self.sample_search_results, 
            "Taiwan tariff 2025"
        )
        
        # Test with citations
        footer = self.service.generate_citations_footer(self.test_presentation_id)
        assert "Sources:" in footer, f"Expected 'Sources:' in footer, got: {footer}"
        assert "example.com" in footer or "wikipedia.org" in footer or "reuters.com" in footer, \
            f"Expected at least one domain in footer: {footer}"
    
    def test_get_citation_links_for_slide(self):
        """Test getting relevant citations for slide content"""
        # Add test data
        self.service.add_search_results_to_presentation(
            self.test_presentation_id, 
            self.sample_search_results, 
            "Taiwan tariff 2025"
        )
        
        # Test slide content with relevant keywords
        slide_content = "Taiwan's import tariff has been adjusted to 20% in 2025"
        relevant_citations = self.service.get_citation_links_for_slide(
            self.test_presentation_id, 
            slide_content
        )
        
        # Should find relevant citations
        assert len(relevant_citations) > 0, "Expected to find relevant citations"
        
        # Check relevance structure
        if relevant_citations:
            first_citation = relevant_citations[0]
            required_keys = ["domain", "url", "title", "relevance"]
            for key in required_keys:
                assert key in first_citation, f"Missing key {key} in relevant citation"
    
    def test_avoid_duplicate_citations(self):
        """Test that duplicate URLs are not added"""
        # Add same results twice
        self.service.add_search_results_to_presentation(
            self.test_presentation_id, 
            self.sample_search_results, 
            "first query"
        )
        self.service.add_search_results_to_presentation(
            self.test_presentation_id, 
            self.sample_search_results, 
            "second query"
        )
        
        # Should still only have 3 unique citations
        citations = self.service.presentation_sources.get(self.test_presentation_id, [])
        assert len(citations) == 3, f"Expected 3 unique citations, got {len(citations)}"
    
    def test_clear_presentation_citations(self):
        """Test clearing citations for a presentation"""
        # Add test data
        self.service.add_search_results_to_presentation(
            self.test_presentation_id, 
            self.sample_search_results, 
            "Taiwan tariff 2025"
        )
        
        # Verify citations exist
        citations = self.service.get_presentation_citations(self.test_presentation_id)
        assert len(citations) > 0, "Expected citations to exist before clearing"
        
        # Clear citations
        self.service.clear_presentation_citations(self.test_presentation_id)
        
        # Verify citations are cleared
        citations = self.service.get_presentation_citations(self.test_presentation_id)
        assert len(citations) == 0, "Expected no citations after clearing"


if __name__ == "__main__":
    # Run a simple test
    service = SourceCitationService()
    
    # Test basic functionality
    print("Testing SourceCitationService...")
    
    # Test domain extraction
    domain = service.extract_domain_from_url("https://www.example.com/path")
    print(f"Domain extraction test: {domain} (expected: example.com)")
    
    # Test adding citations
    sample_results = [
        {
            "title": "Test Article",
            "content": "Test content",
            "url": "https://example.com/test",
            "source": "Test Source"
        }
    ]
    
    service.add_search_results_to_presentation("test_id", sample_results, "test query")
    citations = service.get_presentation_citations("test_id")
    
    print(f"Citations test: {len(citations)} citations added")
    print(f"First citation: {citations[0] if citations else 'None'}")
    
    print("Basic tests completed!")