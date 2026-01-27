import importlib
import os
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI


class TestAppLifespan(unittest.IsolatedAsyncioTestCase):
    async def test_app_lifespan_calls_start_stop(self):
        with patch("api.lifespan.create_db_and_tables", new=AsyncMock()) as create_db, \
            patch("api.lifespan.check_llm_and_image_provider_api_or_model_availability", new=AsyncMock()) as check_models, \
            patch("api.lifespan.STATELESS_TASK_STORE.start_cleanup_task", new=AsyncMock()) as start_task, \
            patch("api.lifespan.STATELESS_TASK_STORE.stop_cleanup_task", new=AsyncMock()) as stop_task, \
            patch("api.lifespan.get_app_data_directory_env", return_value="/tmp"):
            from api.lifespan import app_lifespan
            async with app_lifespan(FastAPI()):
                pass

        create_db.assert_awaited_once()
        check_models.assert_awaited_once()
        start_task.assert_awaited_once()
        stop_task.assert_awaited_once()


class TestUserConfigMiddleware(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_updates_env(self):
        from api.middlewares import UserConfigEnvUpdateMiddleware
        middleware = UserConfigEnvUpdateMiddleware(app=MagicMock())
        request = MagicMock()
        call_next = AsyncMock(return_value="ok")
        with patch("api.middlewares.get_can_change_keys_env", return_value="true"), \
            patch("api.middlewares.update_env_with_user_config") as update_env:
            result = await middleware.dispatch(request, call_next)
        update_env.assert_called_once()
        self.assertEqual(result, "ok")


class TestApiMain(unittest.TestCase):
    def test_app_imports(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with tempfile.TemporaryDirectory() as temp_dir, \
            patch.dict(os.environ, {"APP_DATA_DIRECTORY": temp_dir}), \
            _chdir(base_dir), \
            patch("api.main.os.path.exists", return_value=False):
            module = importlib.import_module("api.main")
            importlib.reload(module)
        self.assertIsInstance(module.app, FastAPI)


class TestRouters(unittest.TestCase):
    def test_v2_router_prefix(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with _chdir(base_dir):
            from api.v2.ppt.router import API_V2_PPT_ROUTER
            self.assertEqual(API_V2_PPT_ROUTER.prefix, "/api/v2/ppt")


@contextmanager
def _chdir(path):
    current = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(current)
