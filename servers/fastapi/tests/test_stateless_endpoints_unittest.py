import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from api.v2.ppt.router import API_V2_PPT_ROUTER
from models.presentation_outline_model import PresentationOutlineModel, SlideOutlineModel
from models.stateless_models import StatelessGenerationContext, StatelessOutlineResponse
from services.stateless_task_store import TaskInfo


class StatelessEndpointTestCase(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(API_V2_PPT_ROUTER)
        self.client = TestClient(app)

    def _outline_payload(self):
        return {"slides": [{"content": "Slide 1"}]}

    def test_generate_presentation_stateless(self):
        with patch(
            "api.v2.ppt.stateless.StatelessFlowService.generate_full_presentation",
            new=AsyncMock(return_value="/tmp/generated.pptx"),
        ) as generate_mock, patch(
            "api.v2.ppt.stateless.build_file_response",
            return_value=PlainTextResponse("ok"),
        ) as build_mock:
            response = self.client.post(
                "/api/v2/ppt/stateless/generate",
                json={"content": "topic"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "ok")
        generate_mock.assert_awaited_once()
        build_mock.assert_called_once_with("/tmp/generated.pptx")

    def test_generate_outline_stateless(self):
        outlines = PresentationOutlineModel(slides=[SlideOutlineModel(content="Slide 1")])
        context = StatelessGenerationContext(
            language="English",
            tone="default",
            verbosity="standard",
            instructions=None,
            include_table_of_contents=False,
            include_title_slide=True,
            n_slides=1,
            template="general",
        )
        outline_response = StatelessOutlineResponse(
            title="Title",
            outlines=outlines,
            generation_context=context,
        )

        with patch(
            "api.v2.ppt.stateless.StatelessFlowService.generate_outlines",
            new=AsyncMock(return_value=outline_response),
        ) as generate_mock:
            response = self.client.post(
                "/api/v2/ppt/stateless/outline",
                json={"content": "topic"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Title")
        generate_mock.assert_awaited_once()

    def test_generate_from_outline_stateless(self):
        with patch(
            "api.v2.ppt.stateless.StatelessFlowService.generate_from_outline",
            new=AsyncMock(return_value="/tmp/from-outline.pptx"),
        ) as generate_mock, patch(
            "api.v2.ppt.stateless.build_file_response",
            return_value=PlainTextResponse("ok"),
        ) as build_mock:
            response = self.client.post(
                "/api/v2/ppt/stateless/generate-from-outline",
                json={
                    "outlines": self._outline_payload(),
                    "title": "Title",
                    "template": "general",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "ok")
        generate_mock.assert_awaited_once()
        build_mock.assert_called_once_with("/tmp/from-outline.pptx")

    def test_generate_stream_requires_content(self):
        response = self.client.get("/api/v2/ppt/stateless/generate/stream")
        self.assertEqual(response.status_code, 400)

    def test_generate_stream_builds_response(self):
        async def fake_updates():
            yield "data: ok\n\n"

        def fake_stream(*_args, **_kwargs):
            return fake_updates()

        stream_mock = MagicMock(side_effect=fake_stream)
        with patch(
            "api.v2.ppt.stateless.stream_generate_presentation",
            new=stream_mock,
        ), patch(
            "api.v2.ppt.stateless.build_sse_response",
            return_value=PlainTextResponse("stream"),
        ) as build_mock:
            response = self.client.get(
                "/api/v2/ppt/stateless/generate/stream",
                params={"content": "topic"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "stream")
        self.assertTrue(stream_mock.called)
        self.assertTrue(build_mock.called)

    def test_generate_from_outline_stream(self):
        async def fake_updates():
            yield "data: ok\n\n"

        def fake_stream(*_args, **_kwargs):
            return fake_updates()

        stream_mock = MagicMock(side_effect=fake_stream)
        with patch(
            "api.v2.ppt.stateless.stream_generate_from_outline",
            new=stream_mock,
        ), patch(
            "api.v2.ppt.stateless.build_sse_response",
            return_value=PlainTextResponse("stream"),
        ) as build_mock:
            response = self.client.post(
                "/api/v2/ppt/stateless/generate-from-outline/stream",
                json={
                    "outlines": self._outline_payload(),
                    "title": "Title",
                    "template": "general",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "stream")
        self.assertTrue(stream_mock.called)
        self.assertTrue(build_mock.called)

    def test_download_generated_file_success(self):
        task_info = TaskInfo(
            task_id="task-1",
            file_path="/tmp/file.pptx",
            filename="file.pptx",
            media_type="application/octet-stream",
            created_at=MagicMock(),
            expires_at=MagicMock(),
        )

        with patch(
            "api.v2.ppt.stateless.STATELESS_TASK_STORE.get_task",
            new=AsyncMock(return_value=task_info),
        ), patch(
            "api.v2.ppt.stateless.os.path.exists",
            return_value=True,
        ), patch(
            "api.v2.ppt.stateless.FileResponse",
            return_value=PlainTextResponse("file"),
        ) as file_response:
            response = self.client.get("/api/v2/ppt/stateless/download/task-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "file")
        file_response.assert_called_once()

    def test_download_generated_file_missing_task(self):
        with patch(
            "api.v2.ppt.stateless.STATELESS_TASK_STORE.get_task",
            new=AsyncMock(return_value=None),
        ):
            response = self.client.get("/api/v2/ppt/stateless/download/missing")

        self.assertEqual(response.status_code, 404)

    def test_download_generated_file_missing_file(self):
        task_info = TaskInfo(
            task_id="task-2",
            file_path="/tmp/missing.pptx",
            filename="missing.pptx",
            media_type="application/octet-stream",
            created_at=MagicMock(),
            expires_at=MagicMock(),
        )

        with patch(
            "api.v2.ppt.stateless.STATELESS_TASK_STORE.get_task",
            new=AsyncMock(return_value=task_info),
        ), patch(
            "api.v2.ppt.stateless.os.path.exists",
            return_value=False,
        ):
            response = self.client.get("/api/v2/ppt/stateless/download/task-2")

        self.assertEqual(response.status_code, 404)
