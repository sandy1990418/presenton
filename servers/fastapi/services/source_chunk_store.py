"""
MinIO-backed store for source chunks between Step 1 and Step 2.

Each chunk is stored as a separate object so Step 2 can fetch only the
chunks referenced by a slide's ``chunk_refs`` instead of loading all at
once.

Object layout::

    source_chunks/{context_id}/meta.json      # summary + lightweight list
    source_chunks/{context_id}/{chunk_id}.json # individual chunk w/ content

Objects auto-expire via MinIO lifecycle rules.

Required env vars:
    MINIO_ENDPOINT       - e.g. "localhost:9000"
    MINIO_ACCESS_KEY     - access key
    MINIO_SECRET_KEY     - secret key
    MINIO_BUCKET         - bucket name (default: "presenton-chunks")
    MINIO_SECURE         - "true" for HTTPS (default: "false")
    MINIO_CHUNK_TTL_DAYS - object expiry in days (default: 1)
"""

import asyncio
import io
import json
import logging
import os
import uuid
from typing import Dict, List, Optional

from minio import Minio
from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule

from models.stateless_models import SourceChunk

logger = logging.getLogger(__name__)

_PREFIX = "source_chunks/"


def _build_client() -> Minio:
    return Minio(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", ""),
        secret_key=os.getenv("MINIO_SECRET_KEY", ""),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )


def _put_json(client: Minio, bucket: str, key: str, obj: object) -> None:
    payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    client.put_object(
        bucket,
        key,
        io.BytesIO(payload),
        length=len(payload),
        content_type="application/json",
    )


def _get_json(client: Minio, bucket: str, key: str) -> object:
    response = client.get_object(bucket, key)
    try:
        return json.loads(response.read())
    finally:
        response.close()
        response.release_conn()


class SourceChunkStore:
    """MinIO-backed per-chunk store."""

    def __init__(self, bucket: str = "", ttl_days: int = 1) -> None:
        self._bucket = bucket or os.getenv("MINIO_BUCKET", "presenton-chunks")
        self._ttl_days = ttl_days
        self._client: Optional[Minio] = None
        self._bucket_ready = False

    def _get_client(self) -> Minio:
        if self._client is None:
            self._client = _build_client()
        if not self._bucket_ready:
            self._ensure_bucket()
            self._bucket_ready = True
        return self._client

    def _ensure_bucket(self) -> None:
        if self._client is None:
            return
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
        try:
            rule = Rule(
                rule_id="auto-expire-chunks",
                status="Enabled",
                expiration=Expiration(days=self._ttl_days),
                rule_filter=None,
            )
            self._client.set_bucket_lifecycle(self._bucket, LifecycleConfig([rule]))
        except Exception:
            logger.exception("Failed to set bucket lifecycle")

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _meta_key(context_id: str) -> str:
        return f"{_PREFIX}{context_id}/meta.json"

    @staticmethod
    def _chunk_key(context_id: str, chunk_id: int) -> str:
        return f"{_PREFIX}{context_id}/{chunk_id}.json"

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def store(self, chunks: List[SourceChunk]) -> str:
        """Store all chunks individually + a meta index. Returns context_id."""
        context_id = uuid.uuid4().hex
        client = self._get_client()

        # Limit concurrent MinIO uploads to avoid connection pool exhaustion
        upload_sem = asyncio.Semaphore(10)

        async def _put_one(chunk: SourceChunk) -> None:
            async with upload_sem:
                key = self._chunk_key(context_id, chunk.id)
                await asyncio.to_thread(
                    _put_json, client, self._bucket, key, chunk.model_dump()
                )

        await asyncio.gather(*[_put_one(c) for c in chunks])

        # Upload meta (lightweight index without content)
        meta = {
            "source_summary": None,  # filled by caller if needed
            "chunks": [
                {
                    "id": c.id,
                    "document_id": c.document_id,
                    "title": c.title,
                    "summary": c.summary,
                }
                for c in chunks
            ],
        }
        await asyncio.to_thread(
            _put_json,
            client,
            self._bucket,
            self._meta_key(context_id),
            meta,
        )
        return context_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_chunks_by_ids(
        self,
        context_id: str,
        chunk_ids: List[int],
    ) -> List[SourceChunk]:
        """Fetch only the specified chunks from MinIO (parallel)."""
        if not chunk_ids:
            return []

        client = self._get_client()

        async def _get_one(chunk_id: int) -> Optional[SourceChunk]:
            key = self._chunk_key(context_id, chunk_id)
            try:
                data = await asyncio.to_thread(_get_json, client, self._bucket, key)
                return SourceChunk(**data)  # type: ignore[arg-type]
            except Exception:
                logger.debug("Chunk %s/%d not found in MinIO", context_id, chunk_id)
                return None

        results = await asyncio.gather(*[_get_one(cid) for cid in chunk_ids])
        return [r for r in results if r is not None]

    async def get_all(self, context_id: str) -> Optional[List[SourceChunk]]:
        """Fetch all chunks for a context (fallback for legacy callers)."""
        client = self._get_client()
        try:
            meta = await asyncio.to_thread(
                _get_json,
                client,
                self._bucket,
                self._meta_key(context_id),
            )
        except Exception:
            return None

        chunk_ids = [c["id"] for c in meta.get("chunks", [])]  # type: ignore[union-attr]
        if not chunk_ids:
            return []
        return await self.get_chunks_by_ids(context_id, chunk_ids)

    async def get_meta(self, context_id: str) -> Optional[Dict]:
        """Return the lightweight meta index (no content)."""
        try:
            return await asyncio.to_thread(  # type: ignore[return-value]
                _get_json,
                self._get_client(),
                self._bucket,
                self._meta_key(context_id),
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def remove(self, context_id: str) -> None:
        """Remove all objects for a context."""
        client = self._get_client()
        prefix = f"{_PREFIX}{context_id}/"
        try:
            objects = await asyncio.to_thread(
                lambda: list(client.list_objects(self._bucket, prefix=prefix))
            )

            async def _del(name: str) -> None:
                await asyncio.to_thread(client.remove_object, self._bucket, name)

            await asyncio.gather(*[_del(obj.object_name) for obj in objects])
        except Exception:
            logger.debug("Failed to remove context %s", context_id)


_ttl_days = int(os.getenv("MINIO_CHUNK_TTL_DAYS", "1"))
SOURCE_CHUNK_STORE = SourceChunkStore(ttl_days=_ttl_days)
