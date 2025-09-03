import asyncio
import aiohttp
from typing import Optional


class ExternalApiImageService:
    """
    Service for calling external APIs with proper aiohttp session management.
    Solves the "last image hanging" issue with semaphore-based concurrency control.
    """

    def __init__(self, max_concurrent_requests: int = 5):
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.max_concurrent_requests = max_concurrent_requests

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create a shared aiohttp session with proper connector settings."""
        if self._session is None or self._session.closed:
            # Optimized connector - prevent connection pool exhaustion
            self._connector = aiohttp.TCPConnector(
                limit=self.max_concurrent_requests + 2,  # Small buffer above semaphore
                limit_per_host=self.max_concurrent_requests,  # Match semaphore limit
                ttl_dns_cache=300,
                use_dns_cache=True,
                enable_cleanup_closed=True,
                keepalive_timeout=30,
            )
            
            # Shorter timeouts to prevent hanging on last requests
            timeout = aiohttp.ClientTimeout(
                total=30,  # Reduced total timeout
                connect=5,   # Quick connect timeout
                sock_read=20,  # Socket read timeout
            )
            
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout,
                trust_env=True
            )
        
        return self._session

    async def close_session(self):
        """Close the aiohttp session and connector properly."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._connector:
            await self._connector.close()
        # Add small delay to ensure cleanup
        await asyncio.sleep(0.1)

    async def fetch_image_from_external_api(self, prompt: str, api_endpoint: str, headers: dict = None) -> str:
        """
        Fetch image from external API with semaphore-controlled concurrency.
        This prevents the "last image hanging" issue by limiting concurrent requests.
        
        Args:
            prompt: The image prompt/query
            api_endpoint: The API endpoint URL
            headers: Optional headers for the request
            
        Returns:
            Image URL or path
        """
        # Use semaphore to limit concurrent requests - key fix for hanging issue
        async with self._semaphore:
            session = await self.get_session()
            
            try:
                params = {
                    "query": prompt,
                    "per_page": 1,
                    "format": "json"
                }
                
                async with session.get(
                    api_endpoint,
                    params=params,
                    headers=headers or {}
                ) as response:
                    data = await response.json()
                    
                    # Handle response based on API structure
                    if "images" in data and data["images"]:
                        return data["images"][0]["url"]
                    elif "results" in data and data["results"]:
                        return data["results"][0]["image_url"]
                    else:
                        raise Exception("No images found in API response")
                        
            except asyncio.TimeoutError:
                print(f"Timeout error when fetching image for prompt: {prompt}")
                raise Exception("API request timed out")
            except aiohttp.ClientError as e:
                print(f"Client error when fetching image: {e}")
                raise Exception(f"API client error: {e}")
            except Exception as e:
                print(f"Unexpected error when fetching image: {e}")
                raise

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensure session is closed."""
        await self.close_session()


# Singleton instance with limited concurrency to prevent hanging
EXTERNAL_API_IMAGE_SERVICE = ExternalApiImageService(max_concurrent_requests=5)