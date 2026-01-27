import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from models.pptx_models import PptxPresentationModel, PptxSlideModel, PptxTextBoxModel, PptxPictureBoxModel
from services.pptx_presentation_creator import (
    ImageLayoutEnum,
    PptxPresentationCreator,
)


class DummyPresentation:
    def __init__(self, *args, **kwargs):
        self.slide_width = MagicMock(pt=1280)
        self.slide_height = MagicMock(pt=720)
        self.slide_layouts = [MagicMock() for _ in range(10)]
        self.slides = MagicMock()
        self.slides.add_slide = MagicMock(return_value=MagicMock())

    def save(self, path):
        self.saved_path = path


class TestPptxPresentationCreatorFromSimpleJson(unittest.TestCase):
    def test_from_simple_json_builds_models_and_layouts(self):
        slides_data = [
            {
                "mainTitle": "Slide Title",
                "layout_index": "template_3",
                "bulletPoints": [
                    {"text": "Point A", "subPoints": ["A1"]},
                    {"text": "Point B", "subPoints": []},
                ],
                "image": {"__image_url__": "http://example.com/img.png"},
                "imageLayout": "right_half",
                "__speaker_note__": "Notes here",
            }
        ]

        with patch(
            "services.pptx_presentation_creator.Presentation",
            DummyPresentation,
        ), patch(
            "services.pptx_presentation_creator.os.path.exists",
            return_value=False,
        ):
            creator = PptxPresentationCreator.from_simple_json(
                slides_data=slides_data,
                temp_dir="/tmp",
                template_path="",
                default_layout_index=2,
            )

        self.assertEqual(len(creator._ppt_model.slides), 1)
        slide = creator._ppt_model.slides[0]
        self.assertEqual(slide.layout_index, 2)
        self.assertEqual(slide.note, "Notes here")
        self.assertEqual(creator._slide_image_layouts[0], ImageLayoutEnum.RIGHT_HALF)

        title_shapes = [
            shape
            for shape in slide.shapes
            if isinstance(shape, PptxTextBoxModel)
            and shape.structure
            and shape.structure.placeholder_idx == 0
        ]
        self.assertTrue(title_shapes)
        self.assertEqual(title_shapes[0].paragraphs[0].text, "Slide Title")

        picture_shapes = [
            shape for shape in slide.shapes if isinstance(shape, PptxPictureBoxModel)
        ]
        self.assertTrue(picture_shapes)
        self.assertEqual(picture_shapes[0].picture.path, "http://example.com/img.png")
        self.assertTrue(picture_shapes[0].picture.is_network)

        column_shapes = [
            shape
            for shape in slide.shapes
            if isinstance(shape, PptxTextBoxModel)
            and shape.structure
            and shape.structure.num_columns == 2
        ]
        self.assertTrue(column_shapes)

    def test_distribute_bullets_to_columns_sets_columns(self):
        bullets = [
            {"text": "A", "subPoints": ["A1"]},
            {"text": "B", "subPoints": ["B1"]},
            {"text": "C", "subPoints": []},
        ]
        shapes = PptxPresentationCreator._distribute_bullets_to_columns(bullets, 2)
        columns = {shape.structure.column for shape in shapes if shape.structure}
        self.assertEqual(columns, {0, 1})
        self.assertTrue(all(shape.structure.num_columns == 2 for shape in shapes))


class TestPptxPresentationCreatorCreatePpt(unittest.IsolatedAsyncioTestCase):
    async def test_create_ppt_calls_fetch_and_add_slide(self):
        ppt_model = PptxPresentationModel(
            slides=[
                PptxSlideModel(layout_index=0, shapes=[]),
                PptxSlideModel(layout_index=0, shapes=[]),
            ]
        )

        with patch(
            "services.pptx_presentation_creator.Presentation",
            DummyPresentation,
        ), patch(
            "services.pptx_presentation_creator.os.path.exists",
            return_value=False,
        ):
            creator = PptxPresentationCreator(
                ppt_model=ppt_model,
                temp_dir="/tmp",
                template_path="",
            )
            creator.fetch_network_assets = AsyncMock()
            creator._add_slide = MagicMock()

            await creator.create_ppt()

        creator.fetch_network_assets.assert_awaited_once()
        self.assertEqual(creator._add_slide.call_count, 2)
        creator._add_slide.assert_any_call(ppt_model.slides[0], 0)
        creator._add_slide.assert_any_call(ppt_model.slides[1], 1)


class TestPptxPresentationCreatorSave(unittest.TestCase):
    def test_save_calls_ppt_save(self):
        ppt_model = PptxPresentationModel(slides=[])

        with patch(
            "services.pptx_presentation_creator.Presentation",
            DummyPresentation,
        ), patch(
            "services.pptx_presentation_creator.os.path.exists",
            return_value=False,
        ):
            creator = PptxPresentationCreator(
                ppt_model=ppt_model,
                temp_dir="/tmp",
                template_path="",
            )

        creator._ppt = MagicMock()
        creator.save("/tmp/out.pptx")
        creator._ppt.save.assert_called_once_with("/tmp/out.pptx")
