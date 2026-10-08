"""Explicit in-memory object store (test backend for the Section 14 contract).

This is the *only* store that ever runs without external configuration, and
it must always be requested explicitly: the env factory in
:mod:`backend.storage.config` never substitutes it for a missing S3/MinIO
configuration.  The backing data is a plain ``dict`` guarded by an
:class:`asyncio.Lock` so concurrent coroutines can interleave safely; the
store is intentionally process-local and non-durable — a restarted process
starts empty.

Semantics (identical to :class:`~backend.storage.s3.S3ObjectStore`):

- ``put`` overwrites; the first put sets ``created_at`` and re-puts move
  ``updated_at`` while preserving ``created_at``;
- absent ``content_type``/``metadata`` arguments on a re-put clear the
  previously stored values (they are part of the object identity, not
  add-on annotations);
- ``delete`` is idempotent (``False`` when the key was already absent);
- ``get`` raises :class:`~backend.storage.errors.ObjectNotFoundError`;
  ``exists``/``head`` are honest about missing keys without raising.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime

from .contracts import MetadataMap, ObjectMetadata, validate_key, validate_metadata
from .errors import ObjectNotFoundError


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _etag(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class InMemoryObjectStore:
    """In-memory implementation of :class:`~backend.storage.contracts.ObjectStore`.

    Construct explicitly for tests or ephemeral local runs::

        store = InMemoryObjectStore()
        await store.put("logs/2026/10/05.log", b"...", metadata={"run": "b1"})

    The constructor takes no configuration: there is nothing to configure and
    nothing to misconfigure.
    """

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, ObjectMetadata]] = {}
        self._lock = asyncio.Lock()

    # -- put ---------------------------------------------------------------

    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: MetadataMap | None = None,
    ) -> ObjectMetadata:
        key = validate_key(key)
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("object payload must be bytes, bytearray, or memoryview")
        payload = bytes(data)
        stored_meta = validate_metadata(metadata)
        now = _now()

        async with self._lock:
            existing = self._objects.get(key)
            if existing is None:
                created_at = now
            else:
                created_at = existing[1].created_at
            meta = ObjectMetadata(
                key=key,
                size=len(payload),
                etag=_etag(payload),
                content_type=content_type,
                created_at=created_at,
                updated_at=now,
                metadata=stored_meta,
            )
            self._objects[key] = (payload, meta)
            return meta

    # -- read --------------------------------------------------------------

    async def get(self, key: str) -> bytes:
        key = validate_key(key)
        async with self._lock:
            entry = self._objects.get(key)
        if entry is None:
            raise ObjectNotFoundError(key)
        return entry[0]

    # -- delete ------------------------------------------------------------

    async def delete(self, key: str) -> bool:
        key = validate_key(key)
        async with self._lock:
            return self._objects.pop(key, None) is not None

    # -- probe / metadata ----------------------------------------------------

    async def exists(self, key: str) -> bool:
        key = validate_key(key)
        async with self._lock:
            return key in self._objects

    async def head(self, key: str) -> ObjectMetadata | None:
        key = validate_key(key)
        async with self._lock:
            entry = self._objects.get(key)
        if entry is None:
            return None
        meta = entry[1]
        # Hand out a copy with its own metadata dict so callers cannot
        # mutate stored metadata through a returned instance.
        return ObjectMetadata(
            key=meta.key,
            size=meta.size,
            etag=meta.etag,
            content_type=meta.content_type,
            created_at=meta.created_at,
            updated_at=meta.updated_at,
            metadata=dict(meta.metadata),
        )
