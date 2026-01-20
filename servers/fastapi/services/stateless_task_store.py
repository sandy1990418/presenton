"""
Stateless Task Store for temporary file storage.

This service manages temporary files generated during SSE streaming
and provides download endpoints for completed tasks.
"""

import asyncio
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

from services.temp_file_service import TEMP_FILE_SERVICE


@dataclass
class TaskInfo:
    """Information about a stored task."""

    task_id: str
    file_path: str
    filename: str
    media_type: str
    created_at: datetime
    expires_at: datetime


class StatelessTaskStore:
    """
    Store for managing temporary task files.

    Files are stored with a TTL and automatically cleaned up after expiration.
    """

    def __init__(self, ttl_minutes: int = 30):
        self._tasks: Dict[str, TaskInfo] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        self._cleanup_task: Optional[asyncio.Task[None]] = None
        self._lock = asyncio.Lock()

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        """Background loop to clean up expired tasks."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log but don't crash the cleanup loop
                pass

    async def _cleanup_expired(self) -> None:
        """Remove expired tasks and their files."""
        now = datetime.now()
        async with self._lock:
            expired_ids = [
                task_id
                for task_id, info in self._tasks.items()
                if info.expires_at < now
            ]

            for task_id in expired_ids:
                info = self._tasks.pop(task_id)
                try:
                    if os.path.exists(info.file_path):
                        os.remove(info.file_path)
                except OSError:
                    pass

    def create_task_id(self) -> str:
        """Generate a unique task ID."""
        return str(uuid.uuid4())

    async def store_file(
        self,
        task_id: str,
        file_path: str,
        filename: str,
        media_type: str,
    ) -> TaskInfo:
        """
        Store a file for later download.

        Args:
            task_id: Unique task identifier
            file_path: Path to the file to store
            filename: Original filename for download
            media_type: MIME type of the file

        Returns:
            TaskInfo with storage details
        """
        now = datetime.now()
        info = TaskInfo(
            task_id=task_id,
            file_path=file_path,
            filename=filename,
            media_type=media_type,
            created_at=now,
            expires_at=now + self._ttl,
        )

        async with self._lock:
            self._tasks[task_id] = info

        return info

    async def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """
        Retrieve task info by ID.

        Args:
            task_id: Task identifier

        Returns:
            TaskInfo if found and not expired, None otherwise
        """
        async with self._lock:
            info = self._tasks.get(task_id)
            if info is None:
                return None

            # Check if expired
            if info.expires_at < datetime.now():
                # Clean up expired task
                self._tasks.pop(task_id)
                try:
                    if os.path.exists(info.file_path):
                        os.remove(info.file_path)
                except OSError:
                    pass
                return None

            return info

    async def remove_task(self, task_id: str) -> bool:
        """
        Remove a task and its file.

        Args:
            task_id: Task identifier

        Returns:
            True if task was found and removed
        """
        async with self._lock:
            info = self._tasks.pop(task_id, None)
            if info is None:
                return False

            try:
                if os.path.exists(info.file_path):
                    os.remove(info.file_path)
            except OSError:
                pass

            return True


# Global instance
STATELESS_TASK_STORE = StatelessTaskStore()
