"""Error hierarchy for the NerveCenter object storage layer (spec Section 14)."""

from __future__ import annotations


class ObjectStoreError(RuntimeError):
    """Base class for every object-store failure raised by this package."""


class ObjectStoreConfigError(ObjectStoreError):
    """A configured object store is missing required settings.

    Raised by :mod:`backend.storage.config` when an S3/MinIO endpoint is named
    without the required bucket/credentials, or when a URL scheme is not
    supported.  The :attr:`missing` attribute lists every environment
    variable that is absent so operators can fix the configuration without
    guesswork.
    """

    def __init__(self, message: str, missing: tuple[str, ...] = ()) -> None:
        self.missing: list[str] = list(missing)
        super().__init__(message)


class ObjectStoreNotConfigured(ObjectStoreConfigError):
    """No object store is configured at all.

    Raised — and never swallowed — when ``NERVECENTER_OBJECT_STORE_URL`` is
    absent and no explicit :class:`~backend.storage.config.ObjectStoreConfig`
    was supplied.  The factory refuses to substitute an in-memory store
    silently; call sites that are "not configured" report it honestly
    (same precedent as :mod:`backend.api.health`).
    """


class ObjectNotFoundError(ObjectStoreError):
    """``get`` was called for a key that does not exist in the store.

    ``head``/``exists`` do not raise for missing keys: they return
    ``None``/``False`` respectively.
    """

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"object not found: {key!r}")
