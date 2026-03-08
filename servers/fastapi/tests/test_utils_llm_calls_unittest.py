import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from models.presentation_layout import PresentationLayoutModel, SlideLayoutModel
from models.presentation_outline_model import PresentationOutlineModel, SlideOutlineModel
from utils.llm_calls import edit_slide
from utils.llm_calls import edit_slide_html
from utils.llm_calls import generate_presentation_outlines as outlines
from utils.llm_calls import generate_presentation_structure as structure
from utils.llm_calls import generate_slide_content as slide_content
from utils.llm_calls import select_slide_type_on_edit as select_slide


class DummyResponseModel:
    def model_json_schema(self):
        return {"type": "object"}


def _build_layout():
    slide_schema = {
        "title": "TestSlide",
        "type": "object",
        "properties": {"title": {"type": "string"}},
    }
    slide = SlideLayoutModel(id="layout-1", name="Title", json_schema=slide_schema)
    return PresentationLayoutModel(name="TestLayout", slides=[slide])


class TestGeneratePresentationOutlines(unittest.IsolatedAsyncioTestCase):
    def test_format_chunks_for_prompt(self):
        self.assertEqual(outlines.format_chunks_for_prompt([]), "")
        chunk_text = outlines.format_chunks_for_prompt(
            [{"id": 1, "title": "Doc", "summary": "Sum", "content": "abc"}]
        )
        self.assertIn("CHUNK 1", chunk_text)
        self.assertIn("Summary: Sum", chunk_text)

    def test_get_system_prompt_includes_chunks(self):
        prompt = outlines.get_system_prompt(
            tone="t",
            verbosity="v",
            instructions="i",
            include_title_slide=True,
            has_chunks=True,
        )
        self.assertIn("chunk_refs", prompt)

    def test_get_user_prompt_includes_content(self):
        prompt = outlines.get_user_prompt(
            content="Topic",
            n_slides=3,
            language="English",
            additional_context="Extra",
            chunks=[{"id": 0, "content": "data"}],
        )
        self.assertIn("Topic", prompt)
        self.assertIn("Number of Slides", prompt)
        self.assertIn("Source Document Chunks", prompt)

    async def test_generate_ppt_outline_streams(self):
        mock_client = MagicMock()

        async def fake_stream(*_args, **_kwargs):
            yield {"ok": True}

        mock_client.stream_structured = fake_stream
        mock_client.enable_web_grounding.return_value = True

        with patch(
            "utils.llm_calls.generate_presentation_outlines.LLMClient",
            return_value=mock_client,
        ), patch(
            "utils.llm_calls.generate_presentation_outlines.get_model",
            return_value="model",
        ), patch(
            "utils.llm_calls.generate_presentation_outlines.get_presentation_outline_model_with_n_slides",
            return_value=DummyResponseModel(),
        ):
            results = []
            async for chunk in outlines.generate_ppt_outline(
                content="Topic",
                n_slides=1,
                language="English",
                web_search=True,
            ):
                results.append(chunk)

        self.assertEqual(results, [{"ok": True}])

    async def test_generate_ppt_outline_handles_error(self):
        mock_client = MagicMock()

        async def broken_stream(*_args, **_kwargs):
            raise RuntimeError("boom")
            yield  # pragma: no cover

        mock_client.stream_structured = broken_stream
        mock_client.enable_web_grounding.return_value = False

        with patch(
            "utils.llm_calls.generate_presentation_outlines.LLMClient",
            return_value=mock_client,
        ), patch(
            "utils.llm_calls.generate_presentation_outlines.get_model",
            return_value="model",
        ), patch(
            "utils.llm_calls.generate_presentation_outlines.get_presentation_outline_model_with_n_slides",
            return_value=DummyResponseModel(),
        ):
            results = []
            async for chunk in outlines.generate_ppt_outline(
                content="Topic",
                n_slides=1,
                language="English",
            ):
                results.append(chunk)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], HTTPException)


class TestGeneratePresentationStructure(unittest.IsolatedAsyncioTestCase):
    async def test_generate_presentation_structure(self):
        layout = _build_layout()
        outline = PresentationOutlineModel(slides=[SlideOutlineModel(content="Slide 1")])
        mock_client = MagicMock()
        mock_client.generate_structured = AsyncMock(return_value={"slides": [0]})

        with patch(
            "utils.llm_calls.generate_presentation_structure.LLMClient",
            return_value=mock_client,
        ), patch(
            "utils.llm_calls.generate_presentation_structure.get_model",
            return_value="model",
        ), patch(
            "utils.llm_calls.generate_presentation_structure.get_presentation_structure_model_with_n_slides",
            return_value=DummyResponseModel(),
        ):
            result = await structure.generate_presentation_structure(outline, layout)

        self.assertEqual(result.slides, [0])
        mock_client.generate_structured.assert_awaited_once()


class TestGenerateSlideContent(unittest.IsolatedAsyncioTestCase):
    def test_get_system_prompt_with_source_context(self):
        prompt = slide_content.get_system_prompt(source_context="Facts")
        self.assertIn("Source Context", prompt)

    def test_get_user_prompt_includes_outline(self):
        prompt = slide_content.get_user_prompt("Outline", "English", "Context")
        self.assertIn("Outline", prompt)
        self.assertIn("English", prompt)

    async def test_get_slide_content_from_type_and_outline(self):
        layout = _build_layout().slides[0]
        outline = SlideOutlineModel(content="Outline")
        mock_client = MagicMock()
        mock_client.generate_structured = AsyncMock(return_value={"title": "ok"})

        with patch(
            "utils.llm_calls.generate_slide_content.LLMClient",
            return_value=mock_client,
        ), patch(
            "utils.llm_calls.generate_slide_content.get_model",
            return_value="model",
        ):
            result = await slide_content.get_slide_content_from_type_and_outline(
                slide_layout=layout,
                outline=outline,
                language="English",
            )

        self.assertEqual(result["title"], "ok")
        mock_client.generate_structured.assert_awaited_once()


class TestEditSlide(unittest.IsolatedAsyncioTestCase):
    async def test_get_edited_slide_content(self):
        layout = _build_layout().slides[0]
        mock_client = MagicMock()
        mock_client.generate_structured = AsyncMock(return_value={"title": "edited"})

        with patch(
            "utils.llm_calls.edit_slide.LLMClient",
            return_value=mock_client,
        ), patch(
            "utils.llm_calls.edit_slide.get_model",
            return_value="model",
        ):
            result = await edit_slide.get_edited_slide_content(
                prompt="Fix title",
                slide_content={"title": "old"},
                language="English",
                slide_layout=layout,
            )

        self.assertEqual(result["title"], "edited")
        mock_client.generate_structured.assert_awaited_once()

    async def test_get_edited_slide_content_error(self):
        layout = _build_layout().slides[0]
        mock_client = MagicMock()
        mock_client.generate_structured = AsyncMock(side_effect=RuntimeError("boom"))

        with patch(
            "utils.llm_calls.edit_slide.LLMClient",
            return_value=mock_client,
        ), patch(
            "utils.llm_calls.edit_slide.get_model",
            return_value="model",
        ):
            with self.assertRaises(HTTPException):
                await edit_slide.get_edited_slide_content(
                    prompt="Fix title",
                    slide_content={"title": "old"},
                    language="English",
                    slide_layout=layout,
                )


class TestEditSlideHtml(unittest.IsolatedAsyncioTestCase):
    def test_extract_html_from_response(self):
        html = edit_slide_html.extract_html_from_response(
            "prefix <div>ok</div> suffix"
        )
        self.assertEqual(html, "<div>ok</div>")
        self.assertIsNone(edit_slide_html.extract_html_from_response("no html"))

    async def test_get_edited_slide_html_returns_html(self):
        mock_client = MagicMock()
        mock_client.generate = AsyncMock(
            return_value="prefix <section>ok</section> suffix"
        )

        with patch(
            "utils.llm_calls.edit_slide_html.LLMClient",
            return_value=mock_client,
        ), patch(
            "utils.llm_calls.edit_slide_html.get_model",
            return_value="model",
        ):
            result = await edit_slide_html.get_edited_slide_html(
                "update", "<div>orig</div>"
            )

        self.assertEqual(result, "<section>ok</section>")

    async def test_get_edited_slide_html_falls_back(self):
        mock_client = MagicMock()
        mock_client.generate = AsyncMock(return_value="no html")

        with patch(
            "utils.llm_calls.edit_slide_html.LLMClient",
            return_value=mock_client,
        ), patch(
            "utils.llm_calls.edit_slide_html.get_model",
            return_value="model",
        ):
            result = await edit_slide_html.get_edited_slide_html(
                "update", "<div>orig</div>"
            )

        self.assertEqual(result, "<div>orig</div>")


class TestSelectSlideTypeOnEdit(unittest.IsolatedAsyncioTestCase):
    async def test_get_slide_layout_from_prompt(self):
        layout = _build_layout()
        mock_client = MagicMock()
        mock_client.generate_structured = AsyncMock(return_value={"index": 0})

        with patch(
            "utils.llm_calls.select_slide_type_on_edit.LLMClient",
            return_value=mock_client,
        ), patch(
            "utils.llm_calls.select_slide_type_on_edit.get_model",
            return_value="model",
        ):
            result = await select_slide.get_slide_layout_from_prompt(
                prompt="keep layout",
                layout=layout,
                slide_content={"title": "Slide"},
                slide_layout="layout-1",
            )

        self.assertEqual(result.id, "layout-1")
