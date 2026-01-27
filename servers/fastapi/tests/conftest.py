import os
import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def set_fastapi_cwd():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    current = os.getcwd()
    os.chdir(base_dir)
    try:
        yield
    finally:
        os.chdir(current)
