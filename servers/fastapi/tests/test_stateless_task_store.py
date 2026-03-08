"""
Unit tests for stateless_task_store.py

Tests the StatelessTaskStore service that manages temporary files
for SSE streaming downloads.
"""

import asyncio
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from services.stateless_task_store import (
    TaskInfo,
    StatelessTaskStore,
    STATELESS_TASK_STORE,
)


class TestTaskInfo:
    """Tests for TaskInfo dataclass."""

    def test_initialization(self):
        """Test TaskInfo initialization."""
        now = datetime.now()
        expires = now + timedelta(minutes=30)

        task_info = TaskInfo(
            task_id="task-123",
            file_path="/tmp/test.pptx",
            filename="presentation.pptx",
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            created_at=now,
            expires_at=expires,
        )

        assert task_info.task_id == "task-123"
        assert task_info.file_path == "/tmp/test.pptx"
        assert task_info.filename == "presentation.pptx"
        assert task_info.media_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        assert task_info.created_at == now
        assert task_info.expires_at == expires


class TestStatelessTaskStore:
    """Tests for StatelessTaskStore class."""

    @pytest.fixture
    def task_store(self):
        """Create a fresh task store for each test."""
        return StatelessTaskStore(ttl_minutes=30)

    @pytest.fixture
    def task_store_short_ttl(self):
        """Create a task store with short TTL for testing expiration."""
        return StatelessTaskStore(ttl_minutes=1)

    def test_initialization(self, task_store):
        """Test StatelessTaskStore initialization."""
        assert task_store._ttl == timedelta(minutes=30)
        assert task_store._tasks == {}
        assert task_store._cleanup_task is None

    def test_initialization_custom_ttl(self):
        """Test initialization with custom TTL."""
        store = StatelessTaskStore(ttl_minutes=60)
        assert store._ttl == timedelta(minutes=60)

    def test_create_task_id(self, task_store):
        """Test task ID generation."""
        task_id_1 = task_store.create_task_id()
        task_id_2 = task_store.create_task_id()

        # Should be valid UUIDs
        assert isinstance(task_id_1, str)
        assert len(task_id_1) == 36  # UUID format with dashes

        # Each call should generate unique ID
        assert task_id_1 != task_id_2

    def test_create_task_id_format(self, task_store):
        """Test task ID UUID format."""
        import uuid
        task_id = task_store.create_task_id()

        # Should be valid UUID format
        try:
            uuid.UUID(task_id)
            is_valid = True
        except ValueError:
            is_valid = False

        assert is_valid is True

    @pytest.mark.anyio
    async def test_store_file(self, task_store, tmp_path):
        """Test storing a file."""
        # Create a test file
        test_file = tmp_path / "test.pptx"
        test_file.write_text("test content")

        task_id = "test-task-123"
        task_info = await task_store.store_file(
            task_id=task_id,
            file_path=str(test_file),
            filename="presentation.pptx",
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

        assert task_info.task_id == task_id
        assert task_info.file_path == str(test_file)
        assert task_info.filename == "presentation.pptx"
        assert task_info.media_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        assert task_info.created_at is not None
        assert task_info.expires_at > task_info.created_at

    @pytest.mark.anyio
    async def test_store_file_sets_expiration(self, task_store, tmp_path):
        """Test that stored file has correct expiration time."""
        test_file = tmp_path / "test.pptx"
        test_file.write_text("content")

        before_store = datetime.now()
        task_info = await task_store.store_file(
            task_id="task-1",
            file_path=str(test_file),
            filename="test.pptx",
            media_type="application/octet-stream",
        )
        after_store = datetime.now()

        # Expiration should be approximately 30 minutes from creation
        expected_expiration_min = before_store + timedelta(minutes=30)
        expected_expiration_max = after_store + timedelta(minutes=30)

        assert task_info.expires_at >= expected_expiration_min
        assert task_info.expires_at <= expected_expiration_max

    @pytest.mark.anyio
    async def test_get_task_success(self, task_store, tmp_path):
        """Test retrieving a stored task."""
        test_file = tmp_path / "test.pptx"
        test_file.write_text("content")

        await task_store.store_file(
            task_id="task-get-test",
            file_path=str(test_file),
            filename="test.pptx",
            media_type="application/octet-stream",
        )

        retrieved = await task_store.get_task("task-get-test")

        assert retrieved is not None
        assert retrieved.task_id == "task-get-test"
        assert retrieved.file_path == str(test_file)

    @pytest.mark.anyio
    async def test_get_task_not_found(self, task_store):
        """Test retrieving a non-existent task."""
        retrieved = await task_store.get_task("non-existent-task")
        assert retrieved is None

    @pytest.mark.anyio
    async def test_get_task_expired(self, task_store, tmp_path):
        """Test that expired tasks are cleaned up on retrieval."""
        test_file = tmp_path / "test.pptx"
        test_file.write_text("content")

        # Store a task
        await task_store.store_file(
            task_id="expired-task",
            file_path=str(test_file),
            filename="test.pptx",
            media_type="application/octet-stream",
        )

        # Manually set expiration to past
        async with task_store._lock:
            task_store._tasks["expired-task"].expires_at = datetime.now() - timedelta(minutes=1)

        # Retrieval should return None for expired task
        retrieved = await task_store.get_task("expired-task")
        assert retrieved is None

        # Task should be removed from store
        async with task_store._lock:
            assert "expired-task" not in task_store._tasks

    @pytest.mark.anyio
    async def test_get_task_expired_removes_file(self, task_store, tmp_path):
        """Test that expired task's file is removed."""
        test_file = tmp_path / "test.pptx"
        test_file.write_text("content")

        await task_store.store_file(
            task_id="expired-file-task",
            file_path=str(test_file),
            filename="test.pptx",
            media_type="application/octet-stream",
        )

        # Manually set expiration to past
        async with task_store._lock:
            task_store._tasks["expired-file-task"].expires_at = datetime.now() - timedelta(minutes=1)

        # Trigger cleanup by getting task
        await task_store.get_task("expired-file-task")

        # File should be deleted
        assert not test_file.exists()

    @pytest.mark.anyio
    async def test_remove_task_success(self, task_store, tmp_path):
        """Test removing a task."""
        test_file = tmp_path / "test.pptx"
        test_file.write_text("content")

        await task_store.store_file(
            task_id="remove-test",
            file_path=str(test_file),
            filename="test.pptx",
            media_type="application/octet-stream",
        )

        # File exists before removal
        assert test_file.exists()

        result = await task_store.remove_task("remove-test")

        assert result is True
        assert not test_file.exists()

        # Task should be removed from store
        retrieved = await task_store.get_task("remove-test")
        assert retrieved is None

    @pytest.mark.anyio
    async def test_remove_task_not_found(self, task_store):
        """Test removing a non-existent task."""
        result = await task_store.remove_task("non-existent")
        assert result is False

    @pytest.mark.anyio
    async def test_remove_task_file_already_deleted(self, task_store, tmp_path):
        """Test removing a task when file is already deleted."""
        test_file = tmp_path / "test.pptx"
        test_file.write_text("content")

        await task_store.store_file(
            task_id="file-deleted-task",
            file_path=str(test_file),
            filename="test.pptx",
            media_type="application/octet-stream",
        )

        # Delete file manually
        test_file.unlink()

        # Should not raise error
        result = await task_store.remove_task("file-deleted-task")
        assert result is True

    @pytest.mark.anyio
    async def test_cleanup_expired_tasks(self, task_store, tmp_path):
        """Test cleanup of expired tasks."""
        # Create test files
        file1 = tmp_path / "test1.pptx"
        file2 = tmp_path / "test2.pptx"
        file1.write_text("content1")
        file2.write_text("content2")

        # Store tasks
        await task_store.store_file(
            task_id="task1",
            file_path=str(file1),
            filename="test1.pptx",
            media_type="application/octet-stream",
        )
        await task_store.store_file(
            task_id="task2",
            file_path=str(file2),
            filename="test2.pptx",
            media_type="application/octet-stream",
        )

        # Set task1 as expired
        async with task_store._lock:
            task_store._tasks["task1"].expires_at = datetime.now() - timedelta(minutes=1)

        # Run cleanup
        await task_store._cleanup_expired()

        # task1 should be removed, task2 should remain
        async with task_store._lock:
            assert "task1" not in task_store._tasks
            assert "task2" in task_store._tasks

        # file1 should be deleted, file2 should remain
        assert not file1.exists()
        assert file2.exists()

    @pytest.mark.anyio
    async def test_start_cleanup_task(self, task_store):
        """Test starting the cleanup background task."""
        assert task_store._cleanup_task is None

        await task_store.start_cleanup_task()

        assert task_store._cleanup_task is not None
        assert not task_store._cleanup_task.done()

        # Clean up
        await task_store.stop_cleanup_task()

    @pytest.mark.anyio
    async def test_start_cleanup_task_idempotent(self, task_store):
        """Test that starting cleanup task multiple times is safe."""
        await task_store.start_cleanup_task()
        first_task = task_store._cleanup_task

        await task_store.start_cleanup_task()
        second_task = task_store._cleanup_task

        # Should be the same task
        assert first_task is second_task

        # Clean up
        await task_store.stop_cleanup_task()

    @pytest.mark.anyio
    async def test_stop_cleanup_task(self, task_store):
        """Test stopping the cleanup background task."""
        await task_store.start_cleanup_task()
        assert task_store._cleanup_task is not None

        await task_store.stop_cleanup_task()

        assert task_store._cleanup_task is None

    @pytest.mark.anyio
    async def test_stop_cleanup_task_when_not_started(self, task_store):
        """Test stopping when no cleanup task is running."""
        assert task_store._cleanup_task is None

        # Should not raise error
        await task_store.stop_cleanup_task()

        assert task_store._cleanup_task is None

    @pytest.mark.anyio
    async def test_cleanup_loop_continues_on_exception(self, task_store):
        """Test that cleanup loop continues even if cleanup fails."""
        await task_store.start_cleanup_task()

        # Mock _cleanup_expired to raise an exception
        original_cleanup = task_store._cleanup_expired
        call_count = 0

        async def mock_cleanup():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test error")
            await original_cleanup()

        with patch.object(task_store, '_cleanup_expired', mock_cleanup):
            # Give time for loop to run (sleep is 60 seconds, so we mock it)
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                mock_sleep.return_value = None

                # Let the loop run a few iterations
                await asyncio.sleep(0.1)

        await task_store.stop_cleanup_task()

    @pytest.mark.anyio
    async def test_concurrent_store_and_get(self, task_store, tmp_path):
        """Test concurrent store and get operations."""
        # Create test files
        files = []
        for i in range(10):
            f = tmp_path / f"test{i}.pptx"
            f.write_text(f"content{i}")
            files.append(f)

        # Store concurrently
        async def store_task(idx):
            await task_store.store_file(
                task_id=f"task-{idx}",
                file_path=str(files[idx]),
                filename=f"test{idx}.pptx",
                media_type="application/octet-stream",
            )

        await asyncio.gather(*[store_task(i) for i in range(10)])

        # Get concurrently
        async def get_task(idx):
            return await task_store.get_task(f"task-{idx}")

        results = await asyncio.gather(*[get_task(i) for i in range(10)])

        # All should succeed
        for i, result in enumerate(results):
            assert result is not None
            assert result.task_id == f"task-{i}"

    @pytest.mark.anyio
    async def test_store_file_with_pdf(self, task_store, tmp_path):
        """Test storing a PDF file."""
        test_file = tmp_path / "test.pdf"
        test_file.write_text("PDF content")

        task_info = await task_store.store_file(
            task_id="pdf-task",
            file_path=str(test_file),
            filename="presentation.pdf",
            media_type="application/pdf",
        )

        assert task_info.filename == "presentation.pdf"
        assert task_info.media_type == "application/pdf"


class TestStatelessTaskStoreGlobalInstance:
    """Tests for the global STATELESS_TASK_STORE instance."""

    def test_global_instance_exists(self):
        """Test that global instance is created."""
        assert STATELESS_TASK_STORE is not None
        assert isinstance(STATELESS_TASK_STORE, StatelessTaskStore)

    def test_global_instance_default_ttl(self):
        """Test that global instance has default TTL."""
        assert STATELESS_TASK_STORE._ttl == timedelta(minutes=30)

    @pytest.mark.anyio
    async def test_global_instance_operations(self, tmp_path):
        """Test operations on global instance."""
        # Note: This test uses the actual global instance
        # Be careful not to interfere with other tests

        test_file = tmp_path / "global_test.pptx"
        test_file.write_text("global test content")

        task_id = STATELESS_TASK_STORE.create_task_id()

        await STATELESS_TASK_STORE.store_file(
            task_id=task_id,
            file_path=str(test_file),
            filename="global_test.pptx",
            media_type="application/octet-stream",
        )

        retrieved = await STATELESS_TASK_STORE.get_task(task_id)
        assert retrieved is not None

        # Clean up
        await STATELESS_TASK_STORE.remove_task(task_id)


class TestStatelessTaskStoreEdgeCases:
    """Edge case tests for StatelessTaskStore."""

    @pytest.fixture
    def task_store(self):
        """Create a fresh task store for each test."""
        return StatelessTaskStore(ttl_minutes=30)

    @pytest.mark.anyio
    async def test_store_same_task_id_twice(self, task_store, tmp_path):
        """Test storing with same task ID overwrites previous."""
        file1 = tmp_path / "test1.pptx"
        file2 = tmp_path / "test2.pptx"
        file1.write_text("content1")
        file2.write_text("content2")

        await task_store.store_file(
            task_id="same-id",
            file_path=str(file1),
            filename="first.pptx",
            media_type="application/octet-stream",
        )

        await task_store.store_file(
            task_id="same-id",
            file_path=str(file2),
            filename="second.pptx",
            media_type="application/octet-stream",
        )

        retrieved = await task_store.get_task("same-id")
        assert retrieved.filename == "second.pptx"

    @pytest.mark.anyio
    async def test_get_task_with_empty_string_id(self, task_store):
        """Test getting task with empty string ID."""
        result = await task_store.get_task("")
        assert result is None

    @pytest.mark.anyio
    async def test_cleanup_with_nonexistent_file(self, task_store, tmp_path):
        """Test cleanup when file doesn't exist."""
        test_file = tmp_path / "deleted.pptx"
        test_file.write_text("content")

        await task_store.store_file(
            task_id="deleted-file-task",
            file_path=str(test_file),
            filename="deleted.pptx",
            media_type="application/octet-stream",
        )

        # Delete file manually
        test_file.unlink()

        # Set as expired
        async with task_store._lock:
            task_store._tasks["deleted-file-task"].expires_at = datetime.now() - timedelta(minutes=1)

        # Cleanup should not raise error
        await task_store._cleanup_expired()

        async with task_store._lock:
            assert "deleted-file-task" not in task_store._tasks

    @pytest.mark.anyio
    async def test_very_short_ttl(self, tmp_path):
        """Test with very short TTL (1 second simulation)."""
        store = StatelessTaskStore(ttl_minutes=1)

        test_file = tmp_path / "short_ttl.pptx"
        test_file.write_text("content")

        await store.store_file(
            task_id="short-ttl-task",
            file_path=str(test_file),
            filename="short_ttl.pptx",
            media_type="application/octet-stream",
        )

        # Immediately check - should exist
        retrieved = await store.get_task("short-ttl-task")
        assert retrieved is not None

        # Manually expire
        async with store._lock:
            store._tasks["short-ttl-task"].expires_at = datetime.now() - timedelta(seconds=1)

        # Should be expired
        retrieved = await store.get_task("short-ttl-task")
        assert retrieved is None

    @pytest.mark.anyio
    async def test_unicode_filename(self, task_store, tmp_path):
        """Test storing file with unicode filename."""
        test_file = tmp_path / "test.pptx"
        test_file.write_text("content")

        task_info = await task_store.store_file(
            task_id="unicode-task",
            file_path=str(test_file),
            filename="演示文稿_プレゼンテーション.pptx",
            media_type="application/octet-stream",
        )

        assert task_info.filename == "演示文稿_プレゼンテーション.pptx"

        retrieved = await task_store.get_task("unicode-task")
        assert retrieved.filename == "演示文稿_プレゼンテーション.pptx"

    @pytest.mark.anyio
    async def test_special_characters_in_path(self, task_store, tmp_path):
        """Test storing file with special characters in path."""
        special_dir = tmp_path / "special dir with spaces"
        special_dir.mkdir()
        test_file = special_dir / "test file.pptx"
        test_file.write_text("content")

        task_info = await task_store.store_file(
            task_id="special-path-task",
            file_path=str(test_file),
            filename="test.pptx",
            media_type="application/octet-stream",
        )

        assert "special dir with spaces" in task_info.file_path

        retrieved = await task_store.get_task("special-path-task")
        assert retrieved is not None
