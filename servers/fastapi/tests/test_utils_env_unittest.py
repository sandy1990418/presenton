import json
import os
import tempfile
import unittest
from unittest.mock import patch

from utils import get_env, set_env
from utils.asset_directory_utils import get_exports_directory, get_images_directory, get_uploads_directory
from utils.user_config import get_user_config, update_env_with_user_config


class TestGetSetEnv(unittest.TestCase):
    def test_get_env_reads_values(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "k", "APP_DATA_DIRECTORY": "/tmp/app"}):
            self.assertEqual(get_env.get_openai_api_key_env(), "k")
            self.assertEqual(get_env.get_app_data_directory_env(), "/tmp/app")

    def test_set_env_updates(self):
        set_env.set_openai_api_key_env("k2")
        self.assertEqual(os.environ.get("OPENAI_API_KEY"), "k2")


class TestAssetDirectoryUtils(unittest.TestCase):
    def test_directories_created(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("utils.asset_directory_utils.get_app_data_directory_env", return_value=temp_dir):
                images = get_images_directory()
                exports = get_exports_directory()
                uploads = get_uploads_directory()
        self.assertTrue(os.path.basename(images) == "images")
        self.assertTrue(os.path.basename(exports) == "exports")
        self.assertTrue(os.path.basename(uploads) == "uploads")


class TestUserConfig(unittest.TestCase):
    def test_get_user_config_from_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "config.json")
            with open(path, "w") as handle:
                json.dump({"LLM": "openai", "OPENAI_API_KEY": "abc"}, handle)
            with patch.dict(os.environ, {"USER_CONFIG_PATH": path}):
                config = get_user_config()
        self.assertEqual(config.LLM, "openai")
        self.assertEqual(config.OPENAI_API_KEY, "abc")

    def test_update_env_with_user_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "config.json")
            with open(path, "w") as handle:
                json.dump({"LLM": "openai", "OPENAI_API_KEY": "abc"}, handle)
            with patch.dict(os.environ, {"USER_CONFIG_PATH": path}):
                update_env_with_user_config()
        self.assertEqual(os.environ.get("LLM"), "openai")
        self.assertEqual(os.environ.get("OPENAI_API_KEY"), "abc")
