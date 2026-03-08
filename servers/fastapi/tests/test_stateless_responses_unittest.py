import unittest
from unittest.mock import patch

from api.v2.ppt import stateless_responses


class TestStatelessResponses(unittest.TestCase):
    def test_media_type_for_file(self):
        self.assertEqual(
            stateless_responses.media_type_for_file("/tmp/report.pdf"),
            "application/pdf",
        )
        self.assertEqual(
            stateless_responses.media_type_for_file("/tmp/deck.pptx"),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        self.assertEqual(
            stateless_responses.media_type_for_file("/tmp/data.bin"),
            "application/octet-stream",
        )

    def test_resolve_file_metadata(self):
        filename, media_type = stateless_responses.resolve_file_metadata(
            "/tmp/deck.pptx"
        )
        self.assertEqual(filename, "deck.pptx")
        self.assertEqual(
            media_type,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

    def test_build_file_response(self):
        with patch(
            "api.v2.ppt.stateless_responses.FileResponse",
        ) as file_response:
            stateless_responses.build_file_response("/tmp/file.pdf")

        file_response.assert_called_once_with(
            "/tmp/file.pdf",
            media_type="application/pdf",
            filename="file.pdf",
        )
