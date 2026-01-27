import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.responses import StreamingResponse

from api.v2.ppt.stateless_streaming import (
    build_sse_response,
    stream_generate_from_outline,
    stream_generate_presentation,
)
from enums.tone import Tone
from enums.verbosity import Verbosity
from models.presentation_outline_model import PresentationOutlineModel, SlideOutlineModel
from models.stateless_models import StatelessGenerateFromOutlineRequest


class TestStatelessStreaming(unittest.IsolatedAsyncioTestCase):
    def test_build_sse_response_headers(self):
        async def fake_gen():
            yield "data: ok\n\n"

        response = build_sse_response(fake_gen())
        self.assertIsInstance(response, StreamingResponse)
        self.assertEqual(response.media_type, "text/event-stream")
        self.assertEqual(response.headers.get("Cache-Control"), "no-cache")
        self.assertEqual(response.headers.get("Connection"), "keep-alive")
        self.assertEqual(response.headers.get("X-Accel-Buffering"), "no")

    async def test_stream_generate_presentation_emits_complete(self):
        async def fake_updates(*_args, **_kwargs):
            yield "data: progress\n\n"

        request = MagicMock()

        with patch(
            "api.v2.ppt.stateless_streaming._stream_progress_updates",
            new=fake_updates,
        ), patch(
            "api.v2.ppt.stateless_streaming.StatelessPptxService",
        ) as service_cls, patch(
            "api.v2.ppt.stateless_streaming.STATELESS_TASK_STORE.create_task_id",
            return_value="task-123",
        ), patch(
            "api.v2.ppt.stateless_streaming.STATELESS_TASK_STORE.store_file",
            new=AsyncMock(),
        ) as store_mock, patch(
            "api.v2.ppt.stateless_streaming.resolve_file_metadata",
            return_value=("file.pptx", "application/octet-stream"),
        ):
            service = service_cls.return_value
            service.generate_full_presentation = AsyncMock(return_value="/tmp/file.pptx")

            events = []
            async for item in stream_generate_presentation(
                request,
                content="topic",
                n_slides=2,
                language="English",
                template="general",
                tone=Tone.DEFAULT,
                verbosity=Verbosity.STANDARD,
                instructions=None,
                include_table_of_contents=False,
                include_title_slide=True,
                web_search=False,
                export_as="pptx",
            ):
                events.append(item)

        self.assertTrue(events)
        self.assertIn('"complete"', events[-1])
        self.assertIn("/api/v2/ppt/stateless/download/task-123", events[-1])
        store_mock.assert_awaited_once()

    async def test_stream_generate_from_outline_emits_complete(self):
        async def fake_updates(*_args, **_kwargs):
            yield "data: progress\n\n"

        outlines = PresentationOutlineModel(slides=[SlideOutlineModel(content="Slide 1")])
        request = StatelessGenerateFromOutlineRequest(outlines=outlines, template="general")
        http_request = MagicMock()

        with patch(
            "api.v2.ppt.stateless_streaming._stream_progress_updates",
            new=fake_updates,
        ), patch(
            "api.v2.ppt.stateless_streaming.StatelessPptxService",
        ) as service_cls, patch(
            "api.v2.ppt.stateless_streaming.STATELESS_TASK_STORE.create_task_id",
            return_value="task-456",
        ), patch(
            "api.v2.ppt.stateless_streaming.STATELESS_TASK_STORE.store_file",
            new=AsyncMock(),
        ) as store_mock, patch(
            "api.v2.ppt.stateless_streaming.resolve_file_metadata",
            return_value=("file.pptx", "application/octet-stream"),
        ):
            service = service_cls.return_value
            service.generate_pptx_from_outlines = AsyncMock(return_value="/tmp/file.pptx")

            events = []
            async for item in stream_generate_from_outline(
                http_request,
                request=request,
                template="general",
            ):
                events.append(item)

        self.assertTrue(events)
        self.assertIn('"complete"', events[-1])
        self.assertIn("/api/v2/ppt/stateless/download/task-456", events[-1])
        store_mock.assert_awaited_once()
