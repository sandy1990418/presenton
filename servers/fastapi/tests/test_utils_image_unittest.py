import unittest
from unittest.mock import patch

from PIL import Image

from enums.image_provider import ImageProvider
from models.pptx_models import PptxObjectFitEnum, PptxObjectFitModel
from utils.image_provider import (
    get_selected_image_provider,
    is_pixabay_selected,
    is_pixels_selected,
)
from utils.image_utils import (
    clip_image,
    fit_image,
    round_image_corners,
    set_image_opacity,
)


class TestImageProvider(unittest.TestCase):
    def test_get_selected_image_provider(self):
        with patch("utils.image_provider.get_image_provider_env", return_value="pixabay"):
            provider = get_selected_image_provider()
        self.assertEqual(provider, ImageProvider.PIXABAY)

    def test_is_provider_checks(self):
        with patch("utils.image_provider.get_image_provider_env", return_value="pixabay"):
            self.assertTrue(is_pixabay_selected())
        with patch("utils.image_provider.get_image_provider_env", return_value="pexels"):
            self.assertTrue(is_pixels_selected())


class TestImageUtils(unittest.TestCase):
    def test_clip_and_fit_image(self):
        img = Image.new("RGBA", (400, 200), (255, 0, 0, 255))
        clipped = clip_image(img, 100, 100)
        self.assertEqual(clipped.size, (100, 100))

        fit = fit_image(img, 120, 60, PptxObjectFitModel(fit=PptxObjectFitEnum.CONTAIN))
        self.assertEqual(fit.size, (120, 60))

    def test_round_image_corners_invalid(self):
        img = Image.new("RGBA", (100, 100))
        with self.assertRaises(ValueError):
            round_image_corners(img, [5, 5, 5])

    def test_set_image_opacity(self):
        img = Image.new("RGBA", (50, 50), (255, 0, 0, 255))
        result = set_image_opacity(img, 0.5)
        self.assertEqual(result.mode, "RGBA")
