import unittest
import uuid
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from utils.export_utils import export_presentation


class MockResponse:
    def __init__(self, status=200, json_data=None, text_data=""):
        self.status = status
        self._json_data = json_data or {}
        self._text_data = text_data

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class MockSession:
    def __init__(self, get_response=None, post_response=None):
        self._get_response = get_response
        self._post_response = post_response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, *_args, **_kwargs):
        return self._get_response

    def post(self, *_args, **_kwargs):
        return self._post_response


class TestExportUtils(unittest.IsolatedAsyncioTestCase):
    async def test_export_presentation_pptx(self):
        presentation_id = uuid.uuid4()
        response = MockResponse(
            status=200,
            json_data={"slides": [{"shapes": []}]},
        )
        session = MockSession(get_response=response)

        mock_creator = unittest.mock.MagicMock()
        mock_creator.create_ppt = AsyncMock()

        with patch(
            "utils.export_utils.aiohttp.ClientSession",
            return_value=session,
        ), patch(
            "utils.export_utils.TEMP_FILE_SERVICE.create_temp_dir",
            return_value="/tmp/export",
        ), patch(
            "utils.export_utils.PptxPresentationCreator",
            return_value=mock_creator,
        ), patch(
            "utils.export_utils.get_exports_directory",
            return_value="/tmp/exports",
        ), patch(
            "utils.export_utils.sanitize_filename",
            return_value="My_Title",
        ):
            result = await export_presentation(
                presentation_id=presentation_id,
                title="My Title",
                export_as="pptx",
            )

        self.assertEqual(result.presentation_id, presentation_id)
        self.assertEqual(result.path, "/database/exports/My_Title.pptx")
        mock_creator.create_ppt.assert_awaited_once()
        mock_creator.save.assert_called_once_with("/tmp/exports/My_Title.pptx")

    async def test_export_presentation_pdf(self):
        presentation_id = uuid.uuid4()
        response = MockResponse(
            status=200,
            json_data={"path": "/database/exports/file.pdf"},
        )
        session = MockSession(post_response=response)

        with patch(
            "utils.export_utils.aiohttp.ClientSession",
            return_value=session,
        ), patch(
            "utils.export_utils.get_exports_directory",
            return_value="/tmp/exports",
        ), patch(
            "utils.export_utils.sanitize_filename",
            return_value="My_Title",
        ):
            result = await export_presentation(
                presentation_id=presentation_id,
                title="My Title",
                export_as="pdf",
            )

        self.assertEqual(result.presentation_id, presentation_id)
        self.assertEqual(result.path, "/database/exports/file.pdf")

    async def test_export_presentation_pptx_error(self):
        presentation_id = uuid.uuid4()
        response = MockResponse(status=500, text_data="fail")
        session = MockSession(get_response=response)

        with patch(
            "utils.export_utils.aiohttp.ClientSession",
            return_value=session,
        ):
            with self.assertRaises(HTTPException):
                await export_presentation(
                    presentation_id=presentation_id,
                    title="My Title",
                    export_as="pptx",
                )
