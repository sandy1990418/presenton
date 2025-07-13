import json
import os
import glob
from typing import List, Optional

from api.utils.utils import get_resource
from ppt_generator.models.query_and_prompt_models import (
    IconCategoryEnum,
    IconQueryCollectionWithData,
)


def get_fallback_icons(query: str, limit: int) -> List[str]:
    """
    Fallback icon search when vector store is not available.
    Returns a basic set of icons including numbered icons.
    """
    try:
        # Try to read icons.json for fallback search
        icons_file = get_resource("assets/icons.json")
        if os.path.exists(icons_file):
            with open(icons_file, "r") as f:
                icons_data = json.load(f)
                
            # Filter icons that contain the query term or get numbered icons
            matching_icons = []
            query_lower = query.lower() if query else ""
            
            # First, try to find icons matching the query
            for icon in icons_data.get("icons", []):
                if icon["name"].split("-")[-1] == "bold":
                    icon_name = icon["name"].replace("-bold", "")
                    icon_tags = " ".join(icon.get("tags", []))
                    
                    # Check if query matches name or tags
                    if (query_lower in icon_name.lower() or 
                        query_lower in icon_tags.lower() or
                        any(query_lower in tag.lower() for tag in icon.get("tags", []))):
                        matching_icons.append(icon_name)
                        
            # If we have matches, return them
            if matching_icons:
                return [get_resource(f"assets/icons/bold/{name}-bold.png") 
                       for name in matching_icons[:limit]]
        
        # Fallback: return some common numbered and basic icons
        common_icons = [
            "1-bold", "2-bold", "3-bold", "4-bold", "5-bold",
            "star-bold", "heart-bold", "circle-bold", "square-bold", 
            "triangle-bold", "arrow-right-bold", "checkmark-bold",
            "home-bold", "user-bold", "settings-bold", "mail-bold"
        ]
        
        # Check which icons actually exist
        existing_icons = []
        for icon_name in common_icons:
            icon_path = get_resource(f"assets/icons/bold/{icon_name}.png")
            if os.path.exists(icon_path):
                existing_icons.append(icon_path)
            if len(existing_icons) >= limit:
                break
                
        return existing_icons[:limit]
        
    except Exception as e:
        print(f"Error in fallback icon search: {e}")
        # Ultimate fallback - try to find any icons in the directory
        try:
            icons_dir = get_resource("assets/icons/bold/")
            if os.path.exists(icons_dir):
                icon_files = glob.glob(os.path.join(icons_dir, "*-bold.png"))
                return icon_files[:limit]
        except:
            pass
        
        return []


async def get_icon(
    vector_store,  # FastembedVectorstore,
    input: IconQueryCollectionWithData,
) -> str:
    try:
        # Use fallback when vector store is disabled
        if vector_store is None:
            query = input.icon_query
            fallback_icons = get_fallback_icons(query, 1)
            if fallback_icons:
                return fallback_icons[0]
            return get_resource("assets/icons/placeholder.png")
            
        query = input.icon_query
        results = vector_store.search(query, 1)
        icon_name = results[0][0].split("||")[0]
        return get_resource(f"assets/icons/bold/{icon_name}.png")
    except Exception as e:
        print("Error finding icon: ", e)
        return get_resource("assets/icons/placeholder.png")


async def get_icons(
    vector_store,  # FastembedVectorstore,
    query: str,
    page: int,
    limit: int,
    category: Optional[IconCategoryEnum],
    temp_dir: str,
) -> List[str]:
    # Use fallback when vector store is disabled
    if vector_store is None:
        return get_fallback_icons(query, limit)

    try:
        results = vector_store.search(query, limit)
        icon_names = [result[0].split("||")[0] for result in results]
        return [get_resource(f"assets/icons/bold/{each}.png") for each in icon_names]
    except Exception as e:
        print(f"Error in vector store search: {e}")
        # Fallback to basic search even if vector store fails
        return get_fallback_icons(query, limit)
