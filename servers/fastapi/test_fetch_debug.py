"""
Debug test for async image fetching
Run with: cd servers/fastapi && uv run python test_fetch_debug.py
"""

import asyncio
import aiohttp
import time


class ImageFetcherDebug:
    def __init__(self, max_concurrent: int = 2, timeout: int = 30):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = aiohttp.ClientTimeout(
            total=timeout,
            connect=10,
            sock_read=timeout,
        )

    async def fetch(self, url: str, index: int) -> dict | None:
        start = time.time()
        print(f"[{index}] Starting fetch: {url[:80]}...")

        try:
            async with self.semaphore:
                print(f"[{index}] Got semaphore, making request...")

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=self.timeout) as resp:
                        print(f"[{index}] Got response status: {resp.status}")
                        data = await resp.json()
                        print(f"[{index}] Done in {time.time() - start:.1f}s")
                        return data

        except asyncio.TimeoutError:
            print(f"[{index}] TIMEOUT after {time.time() - start:.1f}s")
            return None
        except aiohttp.ClientError as e:
            print(f"[{index}] CLIENT ERROR after {time.time() - start:.1f}s: {e}")
            return None
        except Exception as e:
            print(f"[{index}] ERROR after {time.time() - start:.1f}s: {type(e).__name__}: {e}")
            return None

    async def fetch_all(self, urls: list[str]) -> list:
        tasks = [asyncio.create_task(self.fetch(url, i)) for i, url in enumerate(urls)]

        print(f"\n{'='*60}")
        print(f"Starting {len(tasks)} requests (max_concurrent=2, timeout=30s)")
        print(f"{'='*60}\n")

        start = time.time()

        # 用 wait 而不是 gather
        done, pending = await asyncio.wait(
            tasks,
            timeout=90,  # 最多等 90 秒
            return_when=asyncio.ALL_COMPLETED,
        )

        for task in pending:
            print(f"Cancelling pending task...")
            task.cancel()

        results = []
        for task in done:
            try:
                results.append(task.result())
            except Exception:
                results.append(None)

        print(f"\n{'='*60}")
        print(f"Total time: {time.time() - start:.1f}s")
        print(f"Completed: {len(done)}, Cancelled: {len(pending)}")
        print(f"Success: {len([r for r in results if r is not None])}")
        print(f"{'='*60}\n")

        return results


async def main():
    test_urls = [
        # 用 httpbin 模拟慢响应 (delay 5 秒)
        "https://httpbin.org/delay/5",
        "https://httpbin.org/delay/5",
        "https://httpbin.org/delay/5",
        "https://httpbin.org/delay/5",
        # 或者换成你的实际 API:
        # "https://your-api.com/extract?url=...",
    ]

    fetcher = ImageFetcherDebug(max_concurrent=2, timeout=30)
    results = await fetcher.fetch_all(test_urls)

    print("Results:")
    for i, r in enumerate(results):
        if r:
            print(f"  [{i}] OK - got data")
        else:
            print(f"  [{i}] FAILED")


if __name__ == "__main__":
    asyncio.run(main())
