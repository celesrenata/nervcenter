"""Async object-store contract for NerveCenter (spec Section 14 Persistence).

Section 14 of the NerveCenter specification pairs PostgreSQL with an object
store holding *logs, diffs, model transcripts, artifacts, and snapshots*.
This module defines the small async contract every NerveCenter object store
must satisfy:

- :meth:`ObjectStore.put` — write an object and return its metadata;
- :meth:`ObjectStore.get` — read object bytes (raises
  :class:`~backend.storage.errors.ObjectNotFoundError` when absent);
- :meth:`ObjectStore.delete` — remove an object; returns ``True`` when a key
  was deleted and ``False`` when no key was present (idempotent delete);
- :meth:`ObjectStore.exists` — cheap presence probe;
- :meth:`ObjectStore.head` — fetch metadata without the payload
  (``None`` when the key is absent).

Metadata
--------
:class:`ObjectMetadata` is the single currency for object identity: the
opaque ``key`` plus ``size``, a store-generated ``etag`` content digest, an
optional ``content_type``, timezone-aware ``created_at`` / ``updated_at``
timestamps, and the caller-supplied free-form ``metadata`` map
(``str -> str``) recorded at put time and returned by ``head``.

Implementers
------------
- :class:`~backend.storage.memory.InMemoryObjectStore` — explicit, process-local
  backend for tests and ephemeral local runs;
- :class:`~backend.storage.s3.S3ObjectStore` — S3/MinIO-compatible REST
  adapter built on :mod:`httpx` (an existing dependency) with SigV4 signing.

Neither backend is a default:
:func:`~backend.storage.config.create_object_store_from_env` raises
:class:`~backend.storage.errors.ObjectStoreNotConfigured` when no URL is
configured rather than silently substituting an in-memory store, and an
S3/MinIO endpoint configured without credentials raises
:class:`~backend.storage.errors.ObjectStoreConfigError` naming the missing
variables.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

#: Caller-supplied per-object metadata (free-form ``str -> str`` pairs).
MetadataMap = Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    """Metadata about a stored object.

    Attributes
    ----------
    key:
        Opaque object key (store-specific path semantics).
    size:
        Size of the object in bytes.
    etag:
        Store-generated content digest (quoted values are stripped).
    content_type:
        MIME type recorded at put time, if any.
    created_at / updated_at:
        Timezone-aware storage timestamps.
    metadata:
        Caller-supplied key/value pairs, returned verbatim.
    """

    key: str
    size: int
    etag: str
    content_type: str | None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, str]

    def with_payload(
        self,
        *,
        size: int,
        etag: str,
        content_type: str | None,
        metadata: dict[str, str],
        updated_at: datetime,
    ) -> ObjectMetadata:
        """Return a copy with the re-put payload fields replaced.

        ``created_at`` is preserved across re-puts; every other caller-facing
        field is taken from the new payload.
        """

        return ObjectMetadata(
            key=self.key,
            size=size,
            etag=etag,
            content_type=content_type,
            created_at=self.created_at,
            updated_at=updated_at,
            metadata=dict(metadata),
        )


class ObjectStore(Protocol):
    """Async object-store contract (put/get/delete/exists + metadata)."""

    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: MetadataMap | None = None,
    ) -> ObjectMetadata:
        """Store ``data`` under ``key`` and return the resulting metadata.

        Re-putting an existing key replaces the payload; ``created_at`` is
        preserved, ``updated_at`` moves, and the caller-supplied
        ``content_type``/``metadata`` become what a subsequent ``head``
        returns (an absent argument clears the value on re-put).
        """
        ...

    async def get(self, key: str) -> bytes:
        """Return the object bytes for ``key``.

        Raises :class:`~backend.storage.errors.ObjectNotFoundError` when the
        key does not exist.
        """
        ...

    async def delete(self, key: str) -> bool:
        """Delete ``key``; return ``True`` when removed, ``False`` when absent."""
        ...

    async def exists(self, key: str) -> bool:
        """Return whether ``key`` exists (never raises for missing keys)."""
        ...

    async def head(self, key: str) -> ObjectMetadata | None:
        """Return the metadata for ``key`` without the payload (``None`` if absent)."""
        ...


def validate_key(key: str) -> str:
    """Validate an object key (non-empty ``str``) and return it unchanged."""
    if not isinstance(key, str) or not key:
        raise ValueError("object key must be a non-empty string")
    return key


def validate_metadata(metadata: MetadataMap | None = None) -> dict[str, str]:
    """Validate and copy caller-supplied ``str -> str`` object metadata."""
    if metadata is None:
        return {}
    copied = dict(metadata)
    for key, value in copied.items():
        if not isinstance(key, str) or not key:
            raise ValueError("object metadata keys must be non-empty strings")
        if not isinstance(value, str):
            raise ValueError(f"object metadata value for {key!r} must be a string")
    return copied
