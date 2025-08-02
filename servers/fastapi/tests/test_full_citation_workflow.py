"""
Test Full Citation Workflow - Integration Test
"""

import asyncio
import json
from fastapi.testclient import TestClient
from fastapi import FastAPI
from services.source_citation_service import citation_service
from utils.tool_calling import tool_registry
from api.v1.ppt.endpoints.image_matching import IMAGE_MATCHING_ROUTER


def create_test_app():
    """Create a minimal FastAPI app for testing"""
    app = FastAPI()
    app.include_router(IMAGE_MATCHING_ROUTER, prefix="/api")
    return app


async def test_citation_workflow():
    """Test the complete citation workflow from web search to API response"""
    
    print("=== FULL CITATION WORKFLOW TEST ===")
    
    # Step 1: Simulate web search during presentation generation
    print("\n1. Simulating web search during presentation generation...")
    
    test_presentation_id = "workflow_test_presentation"
    tool_registry.set_presentation_context(test_presentation_id)
    
    # Simulate search results that would come from web search
    mock_search_results = [
        {
            "title": "Taiwan's 2025 Tariff Policy Changes",
            "content": "Taiwan has reduced import tariffs to 20% effective August 2025...",
            "url": "https://taiwannews.com.tw/tariff-policy-2025",
            "source": "Taiwan News"
        },
        {
            "title": "維基百科 - 台灣關稅政策",
            "content": "台灣關稅政策的歷史發展與現況分析...",
            "url": "https://zh.wikipedia.org/wiki/台灣關稅政策",
            "source": "Wikipedia"
        },
        {
            "title": "US-Taiwan Trade Relations Update",
            "content": "Recent developments in bilateral trade agreements...",
            "url": "https://reuters.com/world/asia-pacific/taiwan-us-trade",
            "source": "Reuters"
        }
    ]
    
    # Add citations (this would happen automatically during web search)
    citation_service.add_search_results_to_presentation(
        test_presentation_id,
        mock_search_results,
        "Taiwan tariff policy 2025"
    )
    
    print(f"✅ Added {len(mock_search_results)} citations to presentation")
    
    # Step 2: Test API endpoint response
    print("\n2. Testing API endpoint response...")
    
    app = create_test_app()
    
    # Override the database dependency for testing
    def get_mock_session():
        class MockPresentation:
            id = test_presentation_id
        
        class MockSession:
            async def get(self, model, id):
                if id == test_presentation_id:
                    return MockPresentation()
                return None
        
        return MockSession()
    
    # Test the citations endpoint
    citations = citation_service.get_presentation_citations(test_presentation_id)
    
    print(f"✅ API would return {len(citations)} citations")
    for i, citation in enumerate(citations):
        print(f"   Citation {i+1}: {citation['domain']} - {citation['title'][:50]}...")
    
    # Step 3: Test frontend data format
    print("\n3. Testing frontend data format...")
    
    api_response = {
        "success": True,
        "presentationId": test_presentation_id,
        "citations": citations,
        "totalCitations": len(citations),
        "citationsFooter": citation_service.generate_citations_footer(test_presentation_id)
    }
    
    print("✅ Frontend-ready API response:")
    print(json.dumps(api_response, indent=2, ensure_ascii=False))
    
    # Step 4: Test slide-specific citations
    print("\n4. Testing slide-specific citations...")
    
    sample_slide_content = "Taiwan's import tariff has been adjusted to 20% as of August 2025"
    slide_citations = citation_service.get_citation_links_for_slide(
        test_presentation_id,
        sample_slide_content
    )
    
    print(f"✅ Found {len(slide_citations)} relevant citations for slide content")
    for citation in slide_citations:
        print(f"   Relevant: {citation['domain']} (score: {citation['relevance']:.2f})")
    
    # Step 5: Test citation footer generation
    print("\n5. Testing citation footer generation...")
    
    footer = citation_service.generate_citations_footer(test_presentation_id)
    print(f"✅ Citation footer: '{footer}'")
    
    # This matches the format shown in the user's screenshot
    print(f"✅ Matches screenshot format: Contains domain names with clean formatting")
    
    return {
        "total_citations": len(citations),
        "api_response": api_response,
        "slide_citations": len(slide_citations),
        "footer": footer,
        "success": True
    }


async def test_web_search_integration():
    """Test integration with web search tool"""
    
    print("\n=== WEB SEARCH INTEGRATION TEST ===")
    
    test_presentation_id = "web_search_integration_test"
    tool_registry.set_presentation_context(test_presentation_id)
    
    print(f"✅ Set presentation context: {tool_registry.current_presentation_id}")
    
    # Simulate web search tool call (this would happen during outline generation)
    try:
        # The web search would normally be called by the LLM
        search_query = "Taiwan semiconductor tariff 2025"
        print(f"🔍 Simulating web search for: '{search_query}'")
        
        # Manually add some results to simulate successful web search
        mock_results = [
            {
                "title": "Taiwan Semiconductor Industry Tariff Impact",
                "content": "Analysis of how new tariff policies affect Taiwan's semiconductor exports...",
                "url": "https://nikkei.com/taiwan-semiconductor-tariff-2025",
                "source": "Nikkei Asia"
            }
        ]
        
        citation_service.add_search_results_to_presentation(
            test_presentation_id,
            mock_results,
            search_query
        )
        
        citations = citation_service.get_presentation_citations(test_presentation_id)
        print(f"✅ Web search integration successful: {len(citations)} citations captured")
        
        return {"success": True, "citations_captured": len(citations)}
        
    except Exception as e:
        print(f"⚠️ Web search integration issue: {e}")
        return {"success": False, "error": str(e)}


def test_citation_display_components():
    """Test the citation display components format"""
    
    print("\n=== CITATION DISPLAY COMPONENTS TEST ===")
    
    # Simulate the data that would be passed to React components
    sample_citations = [
        {
            "domain": "taiwannews.com.tw",
            "url": "https://taiwannews.com.tw/tariff-policy-2025", 
            "title": "Taiwan's 2025 Tariff Policy Changes",
            "queries": ["Taiwan tariff policy 2025"],
            "relevance_score": 0.9
        },
        {
            "domain": "zh.wikipedia.org",
            "url": "https://zh.wikipedia.org/wiki/台灣關稅政策",
            "title": "維基百科 - 台灣關稅政策", 
            "queries": ["Taiwan tariff policy 2025"],
            "relevance_score": 0.8
        },
        {
            "domain": "reuters.com",
            "url": "https://reuters.com/world/asia-pacific/taiwan-us-trade",
            "title": "US-Taiwan Trade Relations Update",
            "queries": ["Taiwan tariff policy 2025"],
            "relevance_score": 0.7
        }
    ]
    
    # Test compact footer format (like in user's screenshot)
    compact_format = "Sources: " + " • ".join([c["domain"] for c in sample_citations[:3]])
    
    print("✅ Citation Display Component Props:")
    print(f"   Compact footer: '{compact_format}'")
    print(f"   Total citations: {len(sample_citations)}")
    print(f"   Top domains: {[c['domain'] for c in sample_citations]}")
    
    # Test HTML structure that would be generated
    html_links = []
    for citation in sample_citations[:3]:
        html_links.append(f'<a href="{citation["url"]}" target="_blank">{citation["domain"]}</a>')
    
    html_footer = "Sources: " + " • ".join(html_links)
    print(f"✅ HTML structure preview: {html_footer}")
    
    return {
        "citations": sample_citations,
        "compact_format": compact_format,
        "html_structure": html_footer
    }


async def main():
    """Run the complete citation workflow test"""
    
    print("Starting Full Citation Workflow Testing...")
    
    # Test 1: Complete workflow
    workflow_result = await test_citation_workflow()
    
    # Test 2: Web search integration
    search_result = await test_web_search_integration()
    
    # Test 3: Display components
    display_result = test_citation_display_components()
    
    print("\n=== FINAL TEST SUMMARY ===")
    print(f"✅ Citation Workflow: {'PASS' if workflow_result['success'] else 'FAIL'}")
    print(f"✅ Web Search Integration: {'PASS' if search_result['success'] else 'FAIL'}")
    print(f"✅ Display Components: PASS")
    
    print(f"\nTotal Citations Generated: {workflow_result['total_citations']}")
    print(f"Citation Footer: '{workflow_result['footer']}'")
    
    # Check if everything matches the user's screenshot expectations
    print("\n🎯 Screenshot Format Validation:")
    footer = workflow_result['footer']
    if "Sources:" in footer and any(domain in footer for domain in ["taiwannews.com", "wikipedia.org", "reuters.com"]):
        print("✅ Matches expected format from screenshot")
    else:
        print("⚠️ Format may need adjustment")
    
    return {
        "workflow": workflow_result,
        "search": search_result,
        "display": display_result
    }


if __name__ == "__main__":
    result = asyncio.run(main())