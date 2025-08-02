"""
Test Reference Image Extractor Service
"""

import asyncio
import json
from services.reference_image_extractor import ReferenceImageExtractor


async def test_document_image_analysis():
    """Test document analysis for image identification"""
    
    print("Testing Reference Image Extractor...")
    
    extractor = ReferenceImageExtractor()
    
    # Test document content with clear image references
    test_document = """
    Taiwan Import Tariff Analysis 2025
    
    As shown in Figure 1, Taiwan's import tariffs have been significantly adjusted. 
    The chart below illustrates the comparison between previous rates and new rates.
    
    According to the data visualization in the accompanying graph, the 20% tariff rate 
    represents a decrease from the previously announced 32% rate in April 2025.
    
    See the diagram for detailed breakdown of tariff categories.
    The screenshot from the official government website shows the exact implementation timeline.
    
    Image 2 demonstrates the impact on various product categories including semiconductors,
    electronics, and telecommunications equipment.
    """
    
    print("\n1. Testing document analysis...")
    
    try:
        # Test document analysis
        analysis = await extractor.analyze_document_for_images(
            test_document, 
            "https://example.com/taiwan-tariff-report"
        )
        
        print(f"✅ Document analysis completed")
        print(f"   Identified images: {len(analysis.get('identified_images', []))}")
        print(f"   Document summary: {analysis.get('document_summary', 'N/A')[:100]}...")
        print(f"   Key concepts: {analysis.get('key_concepts', [])}")
        
        # Show identified images
        for i, image in enumerate(analysis.get('identified_images', [])[:3]):
            print(f"   Image {i+1}:")
            print(f"     - Type: {image.get('image_type', 'N/A')}")
            print(f"     - Context: {image.get('context_text', 'N/A')[:50]}...")
            print(f"     - Relevance: {image.get('relevance_score', 0):.2f}")
            print(f"     - Suggested placement: {image.get('suggested_slide_placement', 'N/A')}")
        
        return analysis
        
    except Exception as e:
        print(f"❌ Document analysis failed: {e}")
        return None


async def test_image_slide_matching():
    """Test matching images to slides"""
    
    print("\n2. Testing image-to-slide matching...")
    
    extractor = ReferenceImageExtractor()
    
    # Mock analysis results
    mock_analysis = {
        "identified_images": [
            {
                "position": 100,
                "context_text": "Figure 1 shows Taiwan tariff comparison chart",
                "likely_content": "Bar chart comparing tariff rates",
                "relevance_score": 0.8,
                "image_type": "chart",
                "placement_priority": 0.9,
                "suggested_slide_placement": "content"
            },
            {
                "position": 250,
                "context_text": "Screenshot of government website timeline",
                "likely_content": "Timeline showing implementation dates",
                "relevance_score": 0.7,
                "image_type": "screenshot",
                "placement_priority": 0.6,
                "suggested_slide_placement": "content"
            }
        ],
        "document_summary": "Taiwan tariff analysis report",
        "key_concepts": ["tariff", "Taiwan", "trade", "policy"]
    }
    
    # Mock slide outlines
    mock_slides = [
        {
            "title": "Taiwan Tariff Overview",
            "body": "Taiwan has adjusted import tariffs to 20% in 2025"
        },
        {
            "title": "Implementation Timeline",
            "body": "The new tariff rates will be effective from August 2025"
        },
        {
            "title": "Economic Impact",
            "body": "Analysis of the economic implications of the tariff changes"
        }
    ]
    
    try:
        matches = await extractor.match_reference_images_to_slides(
            mock_analysis,
            mock_slides
        )
        
        print(f"✅ Image matching completed")
        print(f"   Found {len(matches)} matches")
        
        for i, match in enumerate(matches):
            print(f"   Match {i+1}:")
            print(f"     - Slide: {match['slide_title']}")
            print(f"     - Image type: {match['image_info']['image_type']}")
            print(f"     - Confidence: {match['confidence']:.2f}")
            print(f"     - Placement: {match['placement_suggestion']}")
        
        return matches
        
    except Exception as e:
        print(f"❌ Image matching failed: {e}")
        return []


async def test_complete_pipeline():
    """Test the complete reference document processing pipeline"""
    
    print("\n3. Testing complete pipeline...")
    
    extractor = ReferenceImageExtractor()
    
    test_document = """
    Taiwan Economic Policy Update 2025
    
    Figure 1: Tariff Rate Comparison
    The chart shows the new 20% import tariff compared to previous rates.
    
    Diagram 2: Trade Flow Analysis  
    This visualization demonstrates the impact on bilateral trade.
    
    Screenshot: Official Implementation Timeline
    The government website shows August 7, 2025 as the effective date.
    """
    
    mock_slides = [
        {
            "title": "Policy Overview",
            "body": "Taiwan's new tariff policy introduction and background"
        },
        {
            "title": "Rate Changes", 
            "body": "Detailed analysis of the 20% tariff rate implementation"
        }
    ]
    
    try:
        result = await extractor.process_reference_document(
            test_document,
            mock_slides,
            "https://example.com/taiwan-policy-report"
        )
        
        print(f"✅ Complete pipeline test: {'Success' if result['success'] else 'Failed'}")
        print(f"   Images identified: {result['total_images_identified']}")
        print(f"   Images matched: {result['total_matches']}")
        print(f"   Summary: {result['processing_summary']}")
        
        if result['image_matches']:
            print("   Top matches:")
            for match in result['image_matches'][:2]:
                print(f"     - {match['slide_title']}: {match['image_info']['image_type']} (confidence: {match['confidence']:.2f})")
        
        return result
        
    except Exception as e:
        print(f"❌ Complete pipeline failed: {e}")
        return {"success": False, "error": str(e)}


async def test_image_download_storage():
    """Test image download and storage functionality"""
    
    print("\n4. Testing image download and storage...")
    
    extractor = ReferenceImageExtractor()
    
    # Test with some placeholder image URLs
    test_urls = [
        "https://via.placeholder.com/300x200/blue/white?text=Chart",
        "https://via.placeholder.com/400x300/green/white?text=Diagram"
    ]
    
    test_presentation_id = "storage_test_123"
    
    try:
        stored_images = await extractor.download_and_store_reference_images(
            test_urls,
            test_presentation_id
        )
        
        print(f"✅ Image storage test completed")
        print(f"   Successfully stored: {len(stored_images)} images")
        
        for i, image_info in enumerate(stored_images):
            print(f"   Image {i+1}:")
            print(f"     - Original URL: {image_info['original_url']}")
            print(f"     - Stored filename: {image_info['stored_filename']}")
            print(f"     - File size: {image_info['file_size']} bytes")
        
        return stored_images
        
    except Exception as e:
        print(f"❌ Image storage failed: {e}")
        return []


def test_api_endpoint_format():
    """Test the API endpoint data format"""
    
    print("\n5. Testing API endpoint data format...")
    
    # Simulate API response format
    mock_api_response = {
        "success": True,
        "message": "Identified 3 potential images, matched 2 to slides",
        "documentAnalysis": {
            "summary": "Taiwan tariff policy document with charts and diagrams",
            "keyConcepts": ["tariff", "Taiwan", "trade", "policy", "2025"],
            "totalImagesIdentified": 3
        },
        "imageMatches": [
            {
                "slide_index": 0,
                "slide_title": "Policy Overview",
                "image_info": {
                    "image_type": "chart",
                    "likely_content": "Tariff comparison chart",
                    "relevance_score": 0.8,
                    "suggested_slide_placement": "content"
                },
                "relevance_score": 0.75,
                "placement_suggestion": "content",
                "confidence": 0.85
            }
        ],
        "totalMatches": 1,
        "recommendations": [
            "Found 1 high-confidence image match. Consider adding these images to enhance your presentation."
        ]
    }
    
    print("✅ API Response format:")
    print(json.dumps(mock_api_response, indent=2))
    
    return mock_api_response


async def main():
    """Run all reference image extractor tests"""
    
    print("=== REFERENCE IMAGE EXTRACTOR TESTING ===")
    
    # Test 1: Document Analysis
    analysis_result = await test_document_image_analysis()
    
    # Test 2: Image-Slide Matching
    matching_result = await test_image_slide_matching()
    
    # Test 3: Complete Pipeline
    pipeline_result = await test_complete_pipeline()
    
    # Test 4: Image Storage
    storage_result = await test_image_download_storage()
    
    # Test 5: API Format
    api_format = test_api_endpoint_format()
    
    print("\n=== TEST SUMMARY ===")
    print(f"Document Analysis: {'✅ Pass' if analysis_result else '❌ Fail'}")
    print(f"Image Matching: {'✅ Pass' if matching_result else '❌ Fail'}")
    print(f"Complete Pipeline: {'✅ Pass' if pipeline_result and pipeline_result.get('success') else '❌ Fail'}")
    print(f"Image Storage: {'✅ Pass' if storage_result else '❌ Fail'}")
    print(f"API Format: {'✅ Pass' if api_format else '❌ Fail'}")
    
    # Identify issues
    issues = []
    if not analysis_result:
        issues.append("Document analysis failing - check LLM integration")
    
    if not matching_result:
        issues.append("Image matching not working - check keyword extraction")
    
    if not pipeline_result or not pipeline_result.get('success'):
        issues.append("Complete pipeline has errors - check error handling")
    
    if not storage_result:
        issues.append("Image storage failing - check network/file permissions")
    
    if issues:
        print("\n⚠️ IDENTIFIED ISSUES:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("\n✅ All reference image extractor tests passed!")
    
    return {
        "analysis": bool(analysis_result),
        "matching": bool(matching_result),
        "pipeline": pipeline_result and pipeline_result.get('success', False),
        "storage": bool(storage_result),
        "issues": issues
    }


if __name__ == "__main__":
    result = asyncio.run(main())