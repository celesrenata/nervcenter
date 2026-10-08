"""S3/MinIO-compatible object store adapter backed by ``httpx`` (AWS SigV4).

This is the production adapter for the ``"s3"``
:class:`~backend.storage.config.ObjectStoreConfig` scheme.  It speaks the
S3 REST API (PUT / GET / HEAD / DELETE Object) with AWS Signature Version 4
and works against AWS S3, MinIO, and LocalStack without extra dependencies —
``httpx`` is already a NerveCenter dependency (see ``pyproject.toml``).

Honest-failure rules
--------------------
- The constructor refuses to build a store from an incomplete configuration:
  missing endpoint URL, bucket, or credentials raise
  :class:`~backend.storage.errors.ObjectStoreError`.  There is no fallback
  to :class:`~backend.storage.memory.InMemoryObjectStore`.
- Failed object operations raise
  :class:`~backend.storage.errors.ObjectStoreError` carrying the HTTP status
  and a bounded body excerpt; they are never swallowed or retried into
  success.
- S3 exposes no separate creation timestamp, so both ``created_at`` and
  ``updated_at`` are derived from the server's ``Last-Modified`` header.  A
  re-put preserves the *pre-put* ``Last-Modified`` as ``created_at`` (via a
  HEAD on the existing key) — the closest honest equivalent of the contract.

Addressing is always path-style (``{endpoint}/{bucket}/{key}``) which is
what MinIO and LocalStack expect by default.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

import httpx

from .contracts import MetadataMap, ObjectMetadata, validate_key, validate_metadata
from .errors import ObjectNotFoundError, ObjectStoreError

if TYPE_CHECKING:  # pragma: no cover
    from .config import ObjectStoreConfig

#: S3 "hash" token permitted in the canonical request for non-PUT operations.
UNSIGNED_PAYLOAD = "UNSIGNED-PAYLOAD"

#: Maximum characters of an error body retained on raised errors.
_ERROR_BODY_EXCERPT = 300


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _parse_last_modified(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _strip_etag(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().strip('"')


def _parse_user_metadata(response_headers: httpx.Headers) -> dict[str, str]:
    meta: dict[str, str] = {}
    for name, value in response_headers.items():
        lowered = name.lower()
        if lowered.startswith("x-amz-meta-"):
            meta[lowered.removeprefix("x-amz-meta-")] = value
    return meta


def _amz_metadata_headers(metadata: dict[str, str]) -> dict[str, str]:
    return {f"x-amz-meta-{key}": value for key, value in sorted(metadata.items())}


def _as_error(response: httpx.Response, operation: str) -> ObjectStoreError:
    body = response.text
    if len(body) > _ERROR_BODY_EXCERPT:
        body = body[:_ERROR_BODY_EXCERPT] + "…"
    return ObjectStoreError(f"{operation} failed: HTTP {response.status_code}: {body}")


class S3ObjectStore:
    """S3/MinIO implementation of :class:`~backend.storage.contracts.ObjectStore`.

    Constructed from a validated :class:`~backend.storage.config.ObjectStoreConfig`
    (the production path — see the factory in :mod:`backend.storage.config`).
    ``transport`` is a seam for tests: any httpx-compatible transport (e.g.
    ``httpx.MockTransport``) may be injected so the request path can be
    exercised without network access.
    """

    def __init__(
        self,
        config: ObjectStoreConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        if config.scheme != "s3":
            raise ValueError(
                "S3ObjectStore requires an 's3' configuration; "
                f"got scheme {config.scheme!r}"
            )
        if not config.url or not (
            config.bucket and config.access_key and config.secret_key
        ):
            raise ObjectStoreError(
                "S3ObjectStore requires object store URL, bucket, and "
                "access key / secret key credentials"
            )
        split = urlsplit(config.url if "//" in config.url else f"//{config.url}")
        host = split.netloc
        if not host:
            raise ValueError(f"S3 endpoint URL has no host: {config.url!r}")
        self._bucket: str = config.bucket
        self._access_key: str = config.access_key
        self._secret_key: str = config.secret_key
        self._region: str = config.region
        self._host: str = host
        self._scheme: str = "https" if config.secure else "http"
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=timeout, transport=transport
        )

    # -- lifecycle -----------------------------------------------------------

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # -- request plumbing ----------------------------------------------------

    def _object_path(self, key: str) -> str:
        """Path-style resource path ``/bucket/key`` (bucket and key segments quoted)."""
        return f"/{quote(self._bucket, safe='')}/{quote(key, safe='/')}"

    def _canonical_request(
        self,
        method: str,
        path: str,
        signed_headers: dict[str, str],
        payload_hash: str,
    ) -> str:
        canonical = [
            method.upper(),
            path,
            "",  # no query string for these operations
            "".join(f"{h.lower()}:{v}\n" for h, v in sorted(signed_headers.items())),
            ";".join(h.lower() for h in sorted(signed_headers)),
            payload_hash,
        ]
        return "\n".join(canonical)

    def _sign(
        self,
        method: str,
        path: str,
        payload_hash: str,
        timestamp: datetime,
    ) -> dict[str, str]:
        amz_date = timestamp.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = timestamp.strftime("%Y%m%d")
        signed_headers: dict[str, str] = {
            "Host": self._host,
            "X-Amz-Date": amz_date,
            "X-Amz-Content-Sha256": payload_hash,
        }
        canonical = self._canonical_request(method, path, signed_headers, payload_hash)
        scope = f"{date_stamp}/{self._region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                _sha256_hex(canonical.encode("utf-8")),
            ]
        )
        key = _hmac_sha256(f"AWS4{self._secret_key}".encode(), date_stamp)
        key = _hmac_sha256(key, self._region)
        key = _hmac_sha256(key, "s3")
        key = _hmac_sha256(key, "aws4_request")
        signature = hmac.new(
            key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        signed_names = ";".join(h.lower() for h in sorted(signed_headers))
        return {
            "Authorization": (
                "AWS4-HMAC-SHA256 "
                f"Credential={self._access_key}/{scope}, "
                f"SignedHeaders={signed_names}, "
                f"Signature={signature}"
            ),
            "X-Amz-Date": amz_date,
            "X-Amz-Content-Sha256": payload_hash,
        }

    async def _request(
        self,
        method: str,
        key: str,
        *,
        payload: bytes | None = None,
        payload_hash: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        key = validate_key(key)
        path = self._object_path(key)
        timestamp = datetime.now(tz=UTC)
        if payload_hash is None:
            payload_hash = _sha256_hex(payload) if payload is not None else UNSIGNED_PAYLOAD
        headers = dict(extra_headers) if extra_headers else {}
        headers.update(self._sign(method, path, payload_hash, timestamp))
        url = f"{self._scheme}://{self._host}{path}"
        return await self._client.request(
            method, url, content=payload, headers=headers
        )

    @staticmethod
    def _metadata_from_headers(response_headers: httpx.Headers, key: str) -> ObjectMetadata:
        modified = _parse_last_modified(response_headers.get("Last-Modified"))
        stamped = modified if modified is not None else datetime.now(tz=UTC)
        content_length = response_headers.get("Content-Length", "0")
        return ObjectMetadata(
            key=key,
            size=int(content_length) if content_length.isdigit() else 0,
            etag=_strip_etag(response_headers.get("ETag")),
            content_type=response_headers.get("Content-Type"),
            created_at=stamped,
            updated_at=stamped,
            metadata=_parse_user_metadata(response_headers),
        )

    # -- contract --------------------------------------------------------------

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

        # S3 has no creation timestamp: preserve the pre-existing object's
        # Last-Modified as "created" so a re-put keeps an honest history.
        created_at: datetime | None = None
        if await self.exists(key):
            existing = await self.head(key)
            if existing is not None:
                created_at = existing.updated_at

        headers: dict[str, str] = _amz_metadata_headers(stored_meta)
        if content_type:
            headers["Content-Type"] = content_type
        response = await self._request("PUT", key, payload=payload, extra_headers=headers)
        if response.status_code != 200:
            raise _as_error(response, f"PUT object {key!r}")

        server_modified = _parse_last_modified(response.headers.get("Last-Modified"))
        updated_at = server_modified or datetime.now(tz=UTC)
        if created_at is None:
            created_at = updated_at
        return ObjectMetadata(
            key=key,
            size=len(payload),
            etag=_strip_etag(response.headers.get("ETag")) or _sha256_hex(payload),
            content_type=content_type,
            created_at=created_at,
            updated_at=updated_at,
            metadata=stored_meta,
        )

    async def get(self, key: str) -> bytes:
        key = validate_key(key)
        response = await self._request("GET", key, payload_hash=UNSIGNED_PAYLOAD)
        if response.status_code == 404:
            raise ObjectNotFoundError(key)
        if response.status_code != 200:
            raise _as_error(response, f"GET object {key!r}")
        return response.content

    async def delete(self, key: str) -> bool:
        key = validate_key(key)
        # S3 DELETE is unconditionally 204 (idempotent) and carries no signal
        # about prior existence; probe first so the boolean result is honest.
        response = await self._request("HEAD", key, payload_hash=UNSIGNED_PAYLOAD)
        if response.status_code == 404:
            return False
        if response.status_code != 200:
            raise _as_error(response, f"HEAD object {key!r} before delete")
        deleted = await self._request("DELETE", key, payload_hash=UNSIGNED_PAYLOAD)
        if deleted.status_code not in (202, 204):
            raise _as_error(deleted, f"DELETE object {key!r}")
        return True

    async def exists(self, key: str) -> bool:
        key = validate_key(key)
        response = await self._request("HEAD", key, payload_hash=UNSIGNED_PAYLOAD)
        if response.status_code == 404:
            return False
        return response.status_code == 200

    async def head(self, key: str) -> ObjectMetadata | None:
        key = validate_key(key)
        response = await self._request("HEAD", key, payload_hash=UNSIGNED_PAYLOAD)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise _as_error(response, f"HEAD object {key!r}")
        return self._metadata_from_headers(response.headers, key)
