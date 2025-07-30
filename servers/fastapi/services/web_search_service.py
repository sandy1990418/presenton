import asyncio
import aiohttp
import json
from typing import List, Dict, Any, Optional
from urllib.parse import quote
import logging

logger = logging.getLogger(__name__)

class WebSearchService:
    """
    Web search service that provides search functionality for LLM tool calling
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self.session
    
    async def search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search using DuckDuckGo API (free alternative)
        """
        try:
            session = await self._get_session()
            
            # DuckDuckGo instant answer API
            url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1&skip_disambig=1"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    results = []
                    
                    # Extract main result
                    if data.get('Abstract'):
                        results.append({
                            'title': data.get('Heading', 'DuckDuckGo Result'),
                            'content': data.get('Abstract', ''),
                            'url': data.get('AbstractURL', ''),
                            'source': 'DuckDuckGo'
                        })
                    
                    # Extract related topics
                    for topic in data.get('RelatedTopics', [])[:max_results-1]:
                        if isinstance(topic, dict) and topic.get('Text'):
                            results.append({
                                'title': topic.get('FirstURL', '').split('/')[-1].replace('_', ' ') or 'Related Topic',
                                'content': topic.get('Text', ''),
                                'url': topic.get('FirstURL', ''),
                                'source': 'DuckDuckGo'
                            })
                    
                    return results[:max_results]
                else:
                    logger.warning(f"DuckDuckGo search failed with status {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []
    
    async def search_wikipedia(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Search Wikipedia for factual information
        """
        try:
            session = await self._get_session()
            
            # Wikipedia API search
            search_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(query.replace(' ', '_'))}"
            
            async with session.get(search_url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    return [{
                        'title': data.get('title', query),
                        'content': data.get('extract', ''),
                        'url': data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                        'source': 'Wikipedia'
                    }]
                else:
                    # Try search API if direct page lookup fails
                    search_api_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote(query)}&format=json&srlimit={max_results}"
                    
                    async with session.get(search_api_url) as search_response:
                        if search_response.status == 200:
                            search_data = await search_response.json()
                            results = []
                            
                            for item in search_data.get('query', {}).get('search', []):
                                results.append({
                                    'title': item.get('title', ''),
                                    'content': item.get('snippet', '').replace('<span class="searchmatch">', '').replace('</span>', ''),
                                    'url': f"https://en.wikipedia.org/wiki/{quote(item.get('title', '').replace(' ', '_'))}",
                                    'source': 'Wikipedia'
                                })
                            
                            return results
                        else:
                            return []
                            
        except Exception as e:
            logger.error(f"Wikipedia search error: {e}")
            return []
    
    async def comprehensive_search(self, query: str, max_results: int = 8) -> List[Dict[str, Any]]:
        """
        Perform comprehensive search using multiple sources
        """
        try:
            # Run searches in parallel
            tasks = [
                self.search_duckduckgo(query, max_results // 2),
                self.search_wikipedia(query, max_results // 2)
            ]
            
            results_lists = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine results
            all_results = []
            for result_list in results_lists:
                if isinstance(result_list, list):
                    all_results.extend(result_list)
                else:
                    logger.warning(f"Search task failed: {result_list}")
            
            # Remove duplicates and limit results
            seen_urls = set()
            unique_results = []
            
            for result in all_results:
                if result['url'] not in seen_urls and len(unique_results) < max_results:
                    seen_urls.add(result['url'])
                    unique_results.append(result)
            
            logger.info(f"Found {len(unique_results)} search results for query: {query}")
            return unique_results
            
        except Exception as e:
            logger.error(f"Comprehensive search error: {e}")
            return []
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()

# Global instance
web_search_service = WebSearchService()