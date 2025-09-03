from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.lifespan import app_lifespan
from api.middlewares import UserConfigEnvUpdateMiddleware
from api.v1.ppt.router import API_V1_PPT_ROUTER
from utils.asset_directory_utils import get_exports_directory, get_images_directory
import os


app = FastAPI(lifespan=app_lifespan)


# Routers
app.include_router(API_V1_PPT_ROUTER)

# Static file services
app_data_dir = os.getenv("APP_DATA_DIRECTORY", "./database")
if os.path.exists(app_data_dir):
    # Mount exports directory
    exports_dir = get_exports_directory()
    if os.path.exists(exports_dir):
        app.mount("/exports", StaticFiles(directory=exports_dir), name="exports")
    
    # Mount images directory  
    images_dir = get_images_directory()
    if os.path.exists(images_dir):
        app.mount("/app_data/images", StaticFiles(directory=images_dir), name="images")
    
    # Mount screenshots directory if it exists
    screenshots_dir = os.path.join(app_data_dir, "screenshots")
    if os.path.exists(screenshots_dir):
        app.mount("/app_data/screenshots", StaticFiles(directory=screenshots_dir), name="screenshots")

# Middlewares
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(UserConfigEnvUpdateMiddleware)
