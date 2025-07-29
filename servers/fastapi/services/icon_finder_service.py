import json
from typing import List


class IconFinderService:
    def __init__(self):
        self.icons_data = self._load_icons()

    def _load_icons(self) -> List[dict]:
        """Load and filter icons to only include bold variants."""
        with open("assets/icons.json", "r") as f:
            icons = json.load(f)
        
        # Filter to only bold icons and prepare searchable data
        bold_icons = []
        for icon in icons["icons"]:
            if icon["name"].split("-")[-1] == "bold":
                bold_icons.append({
                    "name": icon["name"],
                    "tags": icon["tags"].lower(),
                    "searchable_text": f"{icon['name'].replace('-', ' ')} {icon['tags']}".lower()
                })
        
        return bold_icons

    async def search_icons(self, query: str, k: int = 1) -> List[str]:
        """Search for icons using simple text matching."""
        query_lower = query.lower()
        scored_icons = []
        
        for icon in self.icons_data:
            score = 0
            searchable = icon["searchable_text"]
            
            # Exact match gets highest score
            if query_lower in searchable:
                score += 100
            
            # Word matches
            query_words = query_lower.split()
            for word in query_words:
                if word in searchable:
                    score += 10
            
            # Partial matches for icon name
            name_words = icon["name"].replace("-bold", "").replace("-", " ").split()
            for name_word in name_words:
                for query_word in query_words:
                    if query_word in name_word or name_word in query_word:
                        score += 5
            
            if score > 0:
                scored_icons.append((score, icon["name"]))
        
        # Sort by score (descending) and return top k results
        scored_icons.sort(reverse=True, key=lambda x: x[0])
        
        # If no matches found, return a default icon
        if not scored_icons:
            scored_icons = [(0, "placeholder-bold")]
        
        # Return paths for the top k icons
        result_icons = [icon_name for _, icon_name in scored_icons[:k]]
        return [f"/static/icons/bold/{icon_name.replace('-bold', '-bold')}.png" for icon_name in result_icons]
