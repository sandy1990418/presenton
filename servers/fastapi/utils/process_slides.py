import asyncio
import os
from typing import List, Tuple
from models.image_prompt import ImagePrompt
from models.sql.image_asset import ImageAsset
from models.sql.slide import SlideModel
from services.icon_finder_service import IconFinderService
from services.image_generation_service import ImageGenerationService
from utils.asset_directory_utils import get_images_directory
from utils.dict_utils import get_dict_at_path, get_dict_paths_with_key, set_dict_at_path
from utils.get_env import get_app_data_directory_env


def convert_file_path_to_web_url(file_path: str) -> str:
    """Convert a local file path to a web-accessible URL."""
    if file_path.startswith("http"):
        return file_path
    
    # Check if already a web path
    if file_path.startswith("/app_data/") or file_path.startswith("/static/"):
        return file_path
    
    # Get the app_data directory
    try:
        app_data_dir = get_app_data_directory_env()
        
        # If the path contains app_data, extract the relative path
        if app_data_dir and app_data_dir in file_path:
            relative_path = os.path.relpath(file_path, app_data_dir)
            # Convert to forward slashes for URL
            relative_path = relative_path.replace(os.sep, '/')
            return f"/app_data/{relative_path}"
        
        # If the path is in the images directory structure, make it web accessible
        if "images/" in file_path:
            # Extract everything after "images/"
            parts = file_path.split("images/")
            if len(parts) > 1:
                image_path = parts[-1]
                return f"/app_data/images/{image_path}"
                
    except Exception as e:
        print(f"Warning: Could not convert file path: {e}")
    
    # Fallback: return placeholder for broken images
    return "/static/images/placeholder.jpg"


async def process_slide_and_fetch_assets(
    image_generation_service: ImageGenerationService,
    icon_finder_service: IconFinderService,
    slide: SlideModel,
) -> List[ImageAsset]:

    async_tasks = []

    image_paths = get_dict_paths_with_key(slide.content, "__image_prompt__")
    icon_paths = get_dict_paths_with_key(slide.content, "__icon_query__")

    for image_path in image_paths:
        image_prompt_parent = get_dict_at_path(slide.content, image_path)
        async_tasks.append(
            image_generation_service.generate_image(
                ImagePrompt(
                    prompt=image_prompt_parent["__image_prompt__"],
                )
            )
        )

    for icon_path in icon_paths:
        icon_query_parent = get_dict_at_path(slide.content, icon_path)
        async_tasks.append(
            icon_finder_service.search_icons(icon_query_parent["__icon_query__"])
        )

    results = await asyncio.gather(*async_tasks)
    results.reverse()

    return_assets = []
    for image_path in image_paths:
        image_dict = get_dict_at_path(slide.content, image_path)
        result = results.pop()
        if isinstance(result, ImageAsset):
            return_assets.append(result)
            image_dict["__image_url__"] = convert_file_path_to_web_url(result.path)
        else:
            image_dict["__image_url__"] = convert_file_path_to_web_url(result)
        set_dict_at_path(slide.content, image_path, image_dict)

    for icon_path in icon_paths:
        icon_dict = get_dict_at_path(slide.content, icon_path)
        icon_dict["__icon_url__"] = results.pop()[0]
        set_dict_at_path(slide.content, icon_path, icon_dict)

    return return_assets


async def process_old_and_new_slides_and_fetch_assets(
    image_generation_service: ImageGenerationService,
    icon_finder_service: IconFinderService,
    old_slide_content: dict,
    new_slide_content: dict,
) -> List[ImageAsset]:
    # Finds all old images
    old_image_dict_paths = get_dict_paths_with_key(
        old_slide_content, "__image_prompt__"
    )
    old_image_dicts = [
        get_dict_at_path(old_slide_content, path) for path in old_image_dict_paths
    ]
    old_image_prompts = [
        old_image_dict["__image_prompt__"] for old_image_dict in old_image_dicts
    ]

    # Finds all old icons
    old_icon_dict_paths = get_dict_paths_with_key(old_slide_content, "__icon_query__")
    old_icon_dicts = [
        get_dict_at_path(old_slide_content, path) for path in old_icon_dict_paths
    ]
    old_icon_queries = [
        old_icon_dict["__icon_query__"] for old_icon_dict in old_icon_dicts
    ]

    # Finds all new images
    new_image_dict_paths = get_dict_paths_with_key(
        new_slide_content, "__image_prompt__"
    )
    new_image_dicts = [
        get_dict_at_path(new_slide_content, path) for path in new_image_dict_paths
    ]

    # Finds all new icons
    new_icon_dict_paths = get_dict_paths_with_key(new_slide_content, "__icon_query__")
    new_icon_dicts = [
        get_dict_at_path(new_slide_content, path) for path in new_icon_dict_paths
    ]

    # Creates async tasks for fetching new images
    async_image_fetch_tasks = []
    new_images_fetch_status = []

    # Creates async tasks for fetching new icons
    async_icon_fetch_tasks = []
    new_icons_fetch_status = []

    # Creates async tasks for fetching new images
    # Use old image url if prompt is same
    for new_image in new_image_dicts:
        if new_image["__image_prompt__"] in old_image_prompts:
            old_image_url = old_image_dicts[
                old_image_prompts.index(new_image["__image_prompt__"])
            ]["__image_url__"]
            new_image["__image_url__"] = old_image_url
            new_images_fetch_status.append(False)
            continue

        async_image_fetch_tasks.append(
            image_generation_service.generate_image(
                ImagePrompt(
                    prompt=new_image["__image_prompt__"],
                )
            )
        )
        new_images_fetch_status.append(True)

    # Creates async tasks for fetching new icons
    # Use old icon url if query is same
    for new_icon in new_icon_dicts:
        if new_icon["__icon_query__"] in old_icon_queries:
            old_icon_url = old_icon_dicts[
                old_icon_queries.index(new_icon["__icon_query__"])
            ]["__icon_url__"]
            new_icon["__icon_url__"] = old_icon_url
            new_icons_fetch_status.append(False)
            continue

        async_icon_fetch_tasks.append(
            icon_finder_service.search_icons(new_icon["__icon_query__"])
        )
        new_icons_fetch_status.append(True)

    new_images = await asyncio.gather(*async_image_fetch_tasks)
    new_icons = await asyncio.gather(*async_icon_fetch_tasks)

    # list of new assets
    new_assets = []

    # Sets new image and icon urls for assets that were fetched
    for i, new_image in enumerate(new_images):
        if new_images_fetch_status[i]:
            fetched_image = new_images[i]
            if isinstance(fetched_image, ImageAsset):
                new_assets.append(fetched_image)
                image_url = convert_file_path_to_web_url(fetched_image.path)
            else:
                image_url = convert_file_path_to_web_url(fetched_image)
            new_image_dicts[i]["__image_url__"] = image_url

    for i, new_icon in enumerate(new_icons):
        if new_icons_fetch_status[i]:
            new_icon_dicts[i]["__icon_url__"] = new_icons[i][0]

    for i, new_image_dict in enumerate(new_image_dicts):
        set_dict_at_path(new_slide_content, new_image_dict_paths[i], new_image_dict)

    for i, new_icon_dict in enumerate(new_icon_dicts):
        set_dict_at_path(new_slide_content, new_icon_dict_paths[i], new_icon_dict)

    return new_assets
