import asyncio
import os
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from services.concurrent_service import ConcurrentService
from services.docling_service import DoclingService
from services.documents_loader import DocumentsLoader
from services.external_api_image_service import ExternalApiImageService
from services.html_to_text_runs_service import parse_html_text_to_text_runs
from services.score_based_chunker import ScoreBasedChunker
from services.source_citation_service import SourceCitationService
from services.temp_file_service import TempFileService


class TestConcurrentService(unittest.IsolatedAsyncioTestCase):
    async def test_run_task_registers_task(self):
        service = ConcurrentService()
        fake_task = MagicMock()
        def fake_create_task(coro):
            coro.close()
            return fake_task
        with patch("services.concurrent_service.asyncio.create_task", side_effect=fake_create_task):
            service.run_task(None, AsyncMock())
        self.assertIn(fake_task, service._background_tasks)
        fake_task.add_done_callback.assert_called_once()
        service.on_task_done(fake_task)
        self.assertNotIn(fake_task, service._background_tasks)


class TestDoclingService(unittest.TestCase):
    def test_parse_to_markdown(self):
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "markdown"
        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result
        with patch("services.docling_service.DocumentConverter", return_value=mock_converter):
            service = DoclingService()
            result = service.parse_to_markdown("/tmp/file.pdf")
        self.assertEqual(result, "markdown")


class TestDocumentsLoader(unittest.IsolatedAsyncioTestCase):
    async def test_load_documents_text_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "sample.txt")
            with open(file_path, "w") as handle:
                handle.write("hello world")

            loader = DocumentsLoader([file_path])
            await loader.load_documents()
            self.assertEqual(loader.documents, ["hello world"])

    async def test_load_documents_missing_file_raises(self):
        loader = DocumentsLoader(["/missing.txt"])
        with self.assertRaises(HTTPException):
            await loader.load_documents()


class TestExternalApiImageService(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_image_from_external_api_returns_url(self):
        service = ExternalApiImageService(max_concurrent_requests=1)
        response = AsyncMock()
        response.json = AsyncMock(return_value={"images": [{"url": "http://img"}]})
        response.__aenter__.return_value = response
        response.__aexit__.return_value = None

        session = MagicMock()
        session.get.return_value = response

        with patch.object(service, "get_session", new=AsyncMock(return_value=session)):
            result = await service.fetch_image_from_external_api("q", "http://api")
        self.assertEqual(result, "http://img")

    async def test_close_session_closes(self):
        service = ExternalApiImageService()
        session = AsyncMock()
        session.closed = False
        connector = AsyncMock()
        service._session = session
        service._connector = connector
        await service.close_session()
        session.close.assert_awaited_once()
        connector.close.assert_awaited_once()


class TestHtmlToTextRunsService(unittest.TestCase):
    def test_parse_html_text_to_text_runs_handles_tags(self):
        runs = parse_html_text_to_text_runs("Hello <strong>World</strong><br>Next")
        self.assertTrue(any(run.text == "World" for run in runs))
        self.assertTrue(any(run.text == "\n" for run in runs))


class TestIconFinderService(unittest.IsolatedAsyncioTestCase):
    async def test_search_icons_returns_match(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with _chdir(base_dir):
            from services.icon_finder_service import IconFinderService
            service = IconFinderService()
            service.icons_data = [
                {"name": "chart-bold", "tags": "chart", "searchable_text": "chart chart"}
            ]
            results = await service.search_icons("chart", k=1)
            self.assertEqual(results, ["/static/icons/bold/chart-bold.png"])

    async def test_search_icons_returns_placeholder(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with _chdir(base_dir):
            from services.icon_finder_service import IconFinderService
            service = IconFinderService()
            service.icons_data = []
            results = await service.search_icons("unknown", k=1)
            self.assertEqual(results, ["/static/icons/bold/placeholder-bold.png"])


class TestScoreBasedChunker(unittest.TestCase):
    def test_extract_headings_and_chunks(self):
        text = "# Title\nContent\n## Section\nMore"
        chunker = ScoreBasedChunker()
        headings = chunker.extract_headings(text)
        self.assertEqual(headings, ["# Title", "## Section"])
        scores = chunker.score_headings(headings)
        chunks = chunker.get_chunks_from_headings(text, headings, scores, top_k=1)
        self.assertEqual(len(chunks), 1)

    def test_get_n_chunks_raises_when_insufficient(self):
        chunker = ScoreBasedChunker()
        with self.assertRaises(ValueError):
            asyncio.run(chunker.get_n_chunks("# Title\nBody", 5))


class TestSourceCitationService(unittest.TestCase):
    def test_add_and_get_citations(self):
        service = SourceCitationService()
        service.add_search_results_to_presentation(
            "p1",
            [{"url": "https://www.example.com/a", "title": "T", "content": "C", "relevance_score": 0.3}],
            "query",
        )
        citations = service.get_presentation_citations("p1")
        self.assertEqual(citations[0]["domain"], "example.com")

    def test_generate_footer_and_slide_links(self):
        service = SourceCitationService()
        service.add_search_results_to_presentation(
            "p1",
            [{"url": "https://example.com/a", "title": "T", "content": "C", "relevance_score": 0.9}],
            "market trends",
        )
        footer = service.generate_citations_footer("p1")
        self.assertTrue(footer.startswith("Sources:"))
        links = service.get_citation_links_for_slide("p1", "market trends overview")
        self.assertTrue(links)


class TestTempFileService(unittest.TestCase):
    def test_create_and_cleanup_temp_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("services.temp_file_service.get_temp_directory_env", return_value=temp_dir):
                service = TempFileService()
            file_path = service.create_temp_file("test.txt", "content")
            self.assertTrue(os.path.exists(file_path))
            service.cleanup_temp_file(file_path)
            self.assertFalse(os.path.exists(file_path))


@contextmanager
def _chdir(path):
    current = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(current)
