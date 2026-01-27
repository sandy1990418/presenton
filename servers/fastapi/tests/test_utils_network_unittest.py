import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from enums.llm_provider import LLMProvider

from models.stateless_models import ImageAssetData
from utils.available_models import (
    list_available_anthropic_models,
    list_available_google_models,
    list_available_openai_compatible_models,
)
from utils.download_helpers import download_file
from utils.get_layout_by_name import get_layout_by_name
from utils.model_availability import check_llm_and_image_provider_api_or_model_availability
from utils.ollama import list_pulled_ollama_models, pull_ollama_model
from utils.process_slides import convert_file_path_to_web_url, process_slide_and_fetch_assets
from utils.tool_calling import handle_tool_calls, should_use_web_search, tool_registry


class TestAvailableModels(unittest.IsolatedAsyncioTestCase):
    async def test_list_available_openai_models(self):
        model_obj = MagicMock(id="m1")
        client = MagicMock()
        client.models.list = AsyncMock(return_value=MagicMock(data=[model_obj]))
        with patch("utils.available_models.AsyncOpenAI", return_value=client):
            models = await list_available_openai_compatible_models("url", "key")
        self.assertEqual(models, ["m1"])

    async def test_list_available_anthropic_models(self):
        model_obj = MagicMock(id="a1")
        client = MagicMock()
        client.models.list = AsyncMock(return_value=MagicMock(data=[model_obj]))
        with patch("utils.available_models.AsyncAnthropic", return_value=client):
            models = await list_available_anthropic_models("key")
        self.assertEqual(models, ["a1"])

    async def test_list_available_google_models(self):
        model_obj = MagicMock(name="g1")
        client = MagicMock()
        client.models.list.return_value = [model_obj]
        with patch("utils.available_models.genai.Client", return_value=client):
            models = await list_available_google_models("key")
        self.assertEqual(models, ["g1"])


class TestGetLayoutByName(unittest.IsolatedAsyncioTestCase):
    async def test_get_layout_by_name_success(self):
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value={"name": "general", "slides": []})
        response.__aenter__.return_value = response
        response.__aexit__.return_value = None
        session = AsyncMock()
        session.get.return_value = response
        session.__aenter__.return_value = session
        session.__aexit__.return_value = None
        with patch("utils.get_layout_by_name.aiohttp.ClientSession", return_value=session):
            layout = await get_layout_by_name("general")
        self.assertEqual(layout.name, "general")


class TestModelAvailability(unittest.IsolatedAsyncioTestCase):
    async def test_check_availability_skips_image_when_disabled(self):
        with patch("utils.model_availability.get_can_change_keys_env", return_value="false"), \
            patch("utils.model_availability.get_llm_provider", return_value=LLMProvider.OPENAI), \
            patch("utils.model_availability.get_openai_api_key_env", return_value="k"), \
            patch("utils.model_availability.get_openai_model_env", return_value="m"), \
            patch("utils.model_availability.list_available_openai_compatible_models", new=AsyncMock(return_value=["m"])), \
            patch("utils.model_availability.is_image_generation_disabled", return_value=True):
            await check_llm_and_image_provider_api_or_model_availability()


class TestToolCalling(unittest.IsolatedAsyncioTestCase):
    async def test_handle_tool_calls_invalid_json(self):
        tool_call = MagicMock()
        tool_call.id = "1"
        tool_call.function.name = "web_search"
        tool_call.function.arguments = "{bad json}"
        results = await handle_tool_calls([tool_call])
        self.assertEqual(results[0]["tool_call_id"], "1")

    def test_should_use_web_search(self):
        self.assertTrue(should_use_web_search("latest trends"))


class TestDownloadHelpers(unittest.IsolatedAsyncioTestCase):
    async def test_download_file_writes(self):
        response = AsyncMock()
        response.status = 200
        async def iter_chunked(_):
            yield b"data"
        response.content.iter_chunked = iter_chunked
        response.__aenter__.return_value = response
        response.__aexit__.return_value = None

        session = AsyncMock()
        session.head.return_value = response
        session.get.return_value = response
        session.__aenter__.return_value = session
        session.__aexit__.return_value = None

        with tempfile.TemporaryDirectory() as temp_dir, \
            patch("utils.download_helpers.aiohttp.ClientSession", return_value=session):
            path = await download_file("http://example.com/file.png", temp_dir)
            self.assertTrue(path)
            self.assertTrue(os.path.exists(path))


class TestProcessSlides(unittest.IsolatedAsyncioTestCase):
    async def test_convert_file_path_to_web_url(self):
        self.assertEqual(convert_file_path_to_web_url(""), "/static/images/placeholder.jpg")
        self.assertEqual(convert_file_path_to_web_url("/static/img.png"), "/static/img.png")
        self.assertEqual(convert_file_path_to_web_url("/database/exports/a.pptx"), "/app_data/exports/a.pptx")

    async def test_process_slide_and_fetch_assets(self):
        slide = {"image": {"__image_prompt__": "a"}, "icon": {"__icon_query__": "b"}}
        image_service = MagicMock()
        image_service.generate_image = AsyncMock(return_value=ImageAssetData(path="/tmp/a.png"))
        with patch("utils.process_slides.ICON_FINDER_SERVICE.search_icons", new=AsyncMock(return_value=["/icon.png"])):
            content, assets = await process_slide_and_fetch_assets(image_service, slide)
        self.assertTrue(assets)
        self.assertIn("__image_url__", content["image"])


class TestOllamaUtils(unittest.IsolatedAsyncioTestCase):
    async def test_list_pulled_ollama_models(self):
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value={"models": [{"model": "m", "size": 1}]})
        response.__aenter__.return_value = response
        response.__aexit__.return_value = None
        session = AsyncMock()
        session.get.return_value = response
        session.__aenter__.return_value = session
        session.__aexit__.return_value = None
        with patch("utils.ollama.aiohttp.ClientSession", return_value=session):
            models = await list_pulled_ollama_models()
        self.assertEqual(models[0].name, "m")

    async def test_pull_ollama_model_yields_events(self):
        response = AsyncMock()
        response.status = 200
        async def stream():
            yield b'{"status": "pulling"}\n'
        response.content = stream()
        response.__aenter__.return_value = response
        response.__aexit__.return_value = None
        session = AsyncMock()
        session.post.return_value = response
        session.__aenter__.return_value = session
        session.__aexit__.return_value = None
        with patch("utils.ollama.aiohttp.ClientSession", return_value=session):
            events = []
            async for event in pull_ollama_model("model"):
                events.append(event)
        self.assertEqual(events[0]["status"], "pulling")
