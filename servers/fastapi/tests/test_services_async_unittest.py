import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from enums.llm_provider import LLMProvider
from models.llm_tool_call import OpenAIToolCall, OpenAIToolCallFunction
from models.presentation_outline_model import PresentationOutlineModel, SlideOutlineModel
from services.document_chunker import DocumentChunker
from services.image_embedding_service import ImageEmbeddingService
from services.image_generation_service import ImageGenerationService
from services.llm_tool_calls_handler import LLMToolCallsHandler
from services.reference_image_extractor import ReferenceImageExtractor
from services.web_search_service import WebSearchService
from services.webhook_service import WebhookService
from services.llm_client import LLMClient
from utils.ppt_utils import get_presentation_title_from_outlines


class TestDocumentChunker(unittest.IsolatedAsyncioTestCase):
    async def test_chunk_documents_by_headers(self):
        chunker = DocumentChunker(min_chunk_size=1, max_chunk_size=50)
        text = "# Intro\nA\n## Section\nB"
        chunks = await chunker.chunk_documents(text, generate_summaries=False)
        self.assertTrue(chunks)
        self.assertEqual(chunks[0].title, "Intro")


class TestImageGenerationService(unittest.IsolatedAsyncioTestCase):
    async def test_generate_image_disabled_returns_placeholder(self):
        with patch(
            "services.image_generation_service.is_image_generation_disabled",
            return_value=True,
        ):
            service = ImageGenerationService("/tmp")
            prompt = MagicMock()
            prompt.prompt = "test"
            result = await service.generate_image(prompt)
        self.assertEqual(result, "/static/images/placeholder.jpg")


class TestImageEmbeddingService(unittest.IsolatedAsyncioTestCase):
    async def test_process_images_fallback(self):
        service = ImageEmbeddingService()
        images = [{"contextText": "Solar energy", "position": {"width": 100, "height": 100}}]
        processed = await service._process_images_fallback(images)
        self.assertEqual(len(processed), 1)
        self.assertTrue(processed[0].context_keywords)

    async def test_match_images_fallback(self):
        service = ImageEmbeddingService()
        processed = await service._process_images_fallback(
            [{"contextText": "climate change", "position": {"width": 900, "height": 700}}]
        )
        slide_outlines = [{"title": "Climate", "body": "change impacts"}]
        matches = await service._match_images_fallback(processed, slide_outlines)
        self.assertTrue(matches)
        self.assertEqual(matches[0].slide_index, 0)


class TestLLMToolCallsHandler(unittest.IsolatedAsyncioTestCase):
    async def test_handle_tool_calls_openai(self):
        client = MagicMock()
        client.llm_provider = LLMProvider.OPENAI
        handler = LLMToolCallsHandler(client)
        handler.tools_map["SearchWebTool"] = AsyncMock(return_value="ok")

        tool_call = OpenAIToolCall(
            id="1",
            function=OpenAIToolCallFunction(name="SearchWebTool", arguments='{"query": "x"}'),
        )
        results = await handler.handle_tool_calls_openai([tool_call])
        self.assertEqual(results[0].content, "ok")


class TestReferenceImageExtractor(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_analysis(self):
        extractor = ReferenceImageExtractor()
        result = extractor._fallback_image_analysis("Figure 1 shows data")
        self.assertIn("identified_images", result)

    async def test_analyze_document_uses_fallback_on_error(self):
        extractor = ReferenceImageExtractor()
        with patch("services.reference_image_extractor.LLMClient") as client_cls, \
            patch("services.reference_image_extractor.get_llm_provider", return_value=LLMProvider.OPENAI), \
            patch("services.reference_image_extractor.is_google_selected", return_value=False):
            client = client_cls.return_value
            client.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
            result = await extractor.analyze_document_for_images("content")
        self.assertIn("identified_images", result)


class TestWebSearchService(unittest.IsolatedAsyncioTestCase):
    async def test_comprehensive_search_google_selected_returns_empty(self):
        service = WebSearchService()
        with patch("services.web_search_service.is_google_selected", return_value=True):
            result = await service.comprehensive_search("query")
        self.assertEqual(result, [])

    async def test_search_duckduckgo_returns_results(self):
        service = WebSearchService()
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(
            return_value={"Abstract": "A", "Heading": "H", "AbstractURL": "U", "RelatedTopics": []}
        )
        response.__aenter__.return_value = response
        response.__aexit__.return_value = None

        session = MagicMock()
        session.get.return_value = response
        with patch.object(service, "_get_session", new=AsyncMock(return_value=session)):
            results = await service.search_duckduckgo("q", max_results=1)
        self.assertEqual(len(results), 1)


class TestWebhookService(unittest.IsolatedAsyncioTestCase):
    async def test_send_webhook_no_subscriptions(self):
        session = AsyncMock()
        session.scalars.return_value = []
        async def session_gen():
            yield session
        with patch("services.webhook_service.get_async_session", session_gen):
            await WebhookService.send_webhook(event=MagicMock(value="evt"), data={})

    async def test_send_request_to_webhook(self):
        subscription = MagicMock(url="http://example.com", secret=None, id="1")
        response = AsyncMock()
        response.__aenter__.return_value = response
        response.__aexit__.return_value = None
        session = AsyncMock()
        session.post.return_value = response
        session.__aenter__.return_value = session
        session.__aexit__.return_value = None
        with patch("services.webhook_service.aiohttp.ClientSession", return_value=session):
            await WebhookService.send_request_to_webhook(subscription, {})


class TestLLMClient(unittest.TestCase):
    def test_get_client_openai_path(self):
        with patch("services.llm_client.get_llm_provider", return_value=LLMProvider.OPENAI), \
            patch.object(LLMClient, "_get_client", return_value=MagicMock()):
            client = LLMClient()
        self.assertEqual(client.llm_provider, LLMProvider.OPENAI)


class TestPptUtils(unittest.TestCase):
    def test_get_presentation_title_from_outlines(self):
        outlines = PresentationOutlineModel(slides=[SlideOutlineModel(content="# Page 1 My Title")])
        title = get_presentation_title_from_outlines(outlines)
        self.assertIn("My Title", title)
