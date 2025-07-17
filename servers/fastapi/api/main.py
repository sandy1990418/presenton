import asyncio
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from contextlib import asynccontextmanager

from api.models import SelectedLLMProvider
from api.routers.presentation.router import presentation_router
from api.services.database import sql_engine
from api.utils.supported_ollama_models import SUPPORTED_OLLAMA_MODELS
from api.utils.utils import update_env_with_user_config
from api.utils.model_utils import (
    get_selected_llm_provider,
    is_custom_llm_selected,
    is_ollama_selected,
    list_available_custom_models,
    pull_ollama_model,
)

can_change_keys = os.getenv("CAN_CHANGE_KEYS") != "false"


async def check_llm_model_availability():
    if not can_change_keys:
        if get_selected_llm_provider() == SelectedLLMProvider.OPENAI:
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                raise Exception("OPENAI_API_KEY must be provided")

        elif get_selected_llm_provider() == SelectedLLMProvider.GOOGLE:
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if not google_api_key:
                raise Exception("GOOGLE_API_KEY must be provided")

        elif is_ollama_selected():
            ollama_model = os.getenv("OLLAMA_MODEL")
            if not ollama_model:
                raise Exception("OLLAMA_MODEL must be provided")

            if ollama_model not in SUPPORTED_OLLAMA_MODELS:
                raise Exception(f"Model {ollama_model} is not supported")

            print("-" * 50)
            print("Pulling model: ", ollama_model)
            async for event in pull_ollama_model(ollama_model):
                print(event)
            print("Pulled model: ", ollama_model)
            print("-" * 50)

        elif is_custom_llm_selected():
            custom_model = os.getenv("CUSTOM_MODEL")
            custom_llm_url = os.getenv("CUSTOM_LLM_URL")
            custom_llm_api_key = os.getenv("CUSTOM_LLM_API_KEY")
            if not custom_model:
                raise Exception("CUSTOM_MODEL must be provided")
            if not custom_llm_url:
                raise Exception("CUSTOM_LLM_URL must be provided")
            if not custom_llm_api_key:
                raise Exception("CUSTOM_LLM_API_KEY must be provided")
            print("-" * 50)
            print("Selecting model: ", custom_model)
            models = await list_available_custom_models(
                custom_llm_url, custom_llm_api_key
            )
            print("Available models: ", models)
            print("-" * 50)
            if custom_model not in models:
                raise Exception(f"Model {custom_model} is not available")


@asynccontextmanager
async def lifespan(_: FastAPI):
    os.makedirs(os.getenv("APP_DATA_DIRECTORY"), exist_ok=True)
    SQLModel.metadata.create_all(sql_engine)
    await check_llm_model_availability()
    yield


app = FastAPI(
    lifespan=lifespan,
    timeout=300,  # 5分鐘請求超時
    debug=False
)
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,  # 預檢請求緩存時間
)


@app.middleware("http")
async def update_env_middleware(request: Request, call_next):
    if can_change_keys:
        update_env_with_user_config()
    return await call_next(request)


@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    try:
        # 為長時間運行的端點設置更長的超時時間
        if "/create" in str(request.url) or "/generate" in str(request.url):
            timeout = 300  # 5分鐘
        else:
            timeout = 60   # 1分鐘
        
        response = await asyncio.wait_for(call_next(request), timeout=timeout)
        return response
    except asyncio.TimeoutError:
        from fastapi import HTTPException
        raise HTTPException(status_code=504, detail="Request timeout")
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


app.include_router(presentation_router)
