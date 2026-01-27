import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from models.presentation_outline_model import PresentationOutlineModel, SlideOutlineModel
from models.stateless_models import (
    StatelessGenerateFromOutlineRequest,
    StatelessGenerateRequest,
    StatelessGenerationContext,
    StatelessOutlineRequest,
    StatelessOutlineResponse,
)
from services.stateless_flow_service import StatelessFlowService
from services.stateless_pptx_service import StatelessPptxService
from services.stateless_task_store import StatelessTaskStore, TaskInfo


class TestStatelessTaskStore(unittest.IsolatedAsyncioTestCase):
    async def test_create_task_id_uses_uuid(self):
        fixed_uuid = uuid.UUID("00000000-0000-0000-0000-000000000001")
        with patch("services.stateless_task_store.uuid.uuid4", return_value=fixed_uuid):
            store = StatelessTaskStore()
            self.assertEqual(
                store.create_task_id(),
                "00000000-0000-0000-0000-000000000001",
            )

    async def test_get_task_expired_removes_file(self):
        store = StatelessTaskStore(ttl_minutes=1)
        task_info = TaskInfo(
            task_id="expired-task",
            file_path="/tmp/expired.pptx",
            filename="expired.pptx",
            media_type="application/octet-stream",
            created_at=datetime.now() - timedelta(minutes=10),
            expires_at=datetime.now() - timedelta(minutes=1),
        )
        store._tasks["expired-task"] = task_info

        with patch("services.stateless_task_store.os.path.exists", return_value=True) as exists_mock, \
            patch("services.stateless_task_store.os.remove") as remove_mock:
            result = await store.get_task("expired-task")

        self.assertIsNone(result)
        exists_mock.assert_called_once_with("/tmp/expired.pptx")
        remove_mock.assert_called_once_with("/tmp/expired.pptx")

    async def test_cleanup_expired_removes_only_expired(self):
        store = StatelessTaskStore(ttl_minutes=1)
        expired = TaskInfo(
            task_id="expired",
            file_path="/tmp/expired.pptx",
            filename="expired.pptx",
            media_type="application/octet-stream",
            created_at=datetime.now() - timedelta(minutes=10),
            expires_at=datetime.now() - timedelta(minutes=1),
        )
        active = TaskInfo(
            task_id="active",
            file_path="/tmp/active.pptx",
            filename="active.pptx",
            media_type="application/octet-stream",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=5),
        )
        store._tasks["expired"] = expired
        store._tasks["active"] = active

        with patch("services.stateless_task_store.os.path.exists", return_value=True), \
            patch("services.stateless_task_store.os.remove") as remove_mock:
            await store._cleanup_expired()

        self.assertNotIn("expired", store._tasks)
        self.assertIn("active", store._tasks)
        remove_mock.assert_called_once_with("/tmp/expired.pptx")


class TestStatelessFlowService(unittest.IsolatedAsyncioTestCase):
    async def test_generate_full_presentation_calls_service(self):
        request = StatelessGenerateRequest(content="topic")
        with patch("services.stateless_flow_service.StatelessPptxService") as service_cls:
            service = service_cls.return_value
            service.generate_full_presentation = AsyncMock(return_value="/tmp/out.pptx")

            result = await StatelessFlowService.generate_full_presentation(request)

        self.assertEqual(result, "/tmp/out.pptx")
        service.generate_full_presentation.assert_awaited_once()

    async def test_generate_outlines_calls_service(self):
        request = StatelessOutlineRequest(content="topic")
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
        response = StatelessOutlineResponse(
            title="Title",
            outlines=outlines,
            generation_context=context,
        )

        with patch("services.stateless_flow_service.StatelessPptxService") as service_cls:
            service = service_cls.return_value
            service.generate_outlines = AsyncMock(return_value=response)

            result = await StatelessFlowService.generate_outlines(request)

        self.assertEqual(result.title, "Title")
        service.generate_outlines.assert_awaited_once()

    async def test_generate_from_outline_calls_service(self):
        outlines = PresentationOutlineModel(slides=[SlideOutlineModel(content="Slide 1")])
        request = StatelessGenerateFromOutlineRequest(outlines=outlines, template="general")

        with patch("services.stateless_flow_service.StatelessPptxService") as service_cls:
            service = service_cls.return_value
            service.generate_pptx_from_outlines = AsyncMock(return_value="/tmp/from-outline.pptx")

            result = await StatelessFlowService.generate_from_outline(request)

        self.assertEqual(result, "/tmp/from-outline.pptx")
        service.generate_pptx_from_outlines.assert_awaited_once()

    def test_normalize_template_invalid_raises(self):
        with self.assertRaises(HTTPException):
            StatelessFlowService.normalize_template("invalid-template")


class TestStatelessPptxService(unittest.IsolatedAsyncioTestCase):
    async def test_generate_full_presentation_with_markdown_skips_outlines(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
            patch("services.stateless_pptx_service.ImageGenerationService", return_value=MagicMock()):
            service = StatelessPptxService(temp_dir=temp_dir)
            service.generate_outlines = AsyncMock()
            service.generate_pptx_from_outlines = AsyncMock(return_value="/tmp/generated.pptx")

            result = await service.generate_full_presentation(
                content="topic",
                n_slides=2,
                language="English",
                template="general",
                slides_markdown=["# Slide 1", "# Slide 2"],
            )

        self.assertEqual(result, "/tmp/generated.pptx")
        service.generate_outlines.assert_not_awaited()
        service.generate_pptx_from_outlines.assert_awaited_once()
        outlines = service.generate_pptx_from_outlines.call_args.kwargs["outlines"]
        self.assertEqual(len(outlines.slides), 2)

    async def test_generate_full_presentation_uses_outlines(self):
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
            source_summary="summary",
        )
        outline_response = StatelessOutlineResponse(
            title="Title",
            outlines=outlines,
            generation_context=context,
        )

        with tempfile.TemporaryDirectory() as temp_dir, \
            patch("services.stateless_pptx_service.ImageGenerationService", return_value=MagicMock()):
            service = StatelessPptxService(temp_dir=temp_dir)
            service.generate_outlines = AsyncMock(return_value=outline_response)
            service.generate_pptx_from_outlines = AsyncMock(return_value="/tmp/generated.pptx")

            result = await service.generate_full_presentation(
                content="topic",
                n_slides=1,
                language="English",
                template="general",
            )

        self.assertEqual(result, "/tmp/generated.pptx")
        service.generate_outlines.assert_awaited_once()
        service.generate_pptx_from_outlines.assert_awaited_once()
        self.assertEqual(
            service.generate_pptx_from_outlines.call_args.kwargs["title"],
            "Title",
        )
        self.assertEqual(
            service.generate_pptx_from_outlines.call_args.kwargs["source_summary"],
            "summary",
        )
