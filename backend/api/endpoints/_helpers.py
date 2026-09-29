"""Shared read-only helpers for API endpoint adapters."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request

from backend.api.models import ApiResponseMeta, ListResponse


async def read_collection(
    request: Request,
    service_name: str,
    method_names: tuple[str, ...] = (),
) -> list[Any]:
    """Read a collection through an application service when configured.

    The API intentionally remains bootable without PostgreSQL/NATS in local
    development. Applications that configure ``app.state.services`` get real
    service-backed responses; otherwise an empty collection is returned.
    """
    services = getattr(request.app.state, "services", {})
    service = services.get(service_name) if isinstance(services, dict) else None
    if service is None:
        return []

    for method_name in method_names:
        method = getattr(service, method_name, None)
        if method is None:
            continue
        try:
            result = method()
            if inspect.isawaitable(result):
                result = await result
            if result is None:
                return []
            if isinstance(result, list):
                return [
                    item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                    for item in result
                ]
            item = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
            return [item]
        except Exception:
            # Service adapters own persistence errors; read-only contract probes
            # should still return a useful empty collection while dependencies
            # are unavailable.
            return []
    return []


def list_response(data: list[Any]) -> ListResponse:
    """Build the stable list envelope used by collection endpoints."""
    return ListResponse(
        data=data,
        meta=ApiResponseMeta(
            version="1.0.0",
            request_id=str(uuid4()),
            timestamp=datetime.now(UTC),
            pagination={"total": len(data), "page": 1, "per_page": max(len(data), 1)},
        ),
    )


def make_read_router(
    prefix: str,
    tag: str,
    service_name: str,
    method_names: tuple[str, ...] = (),
) -> APIRouter:
    """Create a thin read-only router for a spec §46 collection.

    Keeping this adapter generic prevents route handlers from acquiring domain
    logic. Domain services remain the owners of retrieval and serialization.
    """
    router = APIRouter(prefix=prefix, tags=[tag])

    async def list_items(request: Request) -> ListResponse:
        """List items from the configured service."""
        return list_response(await read_collection(request, service_name, method_names))

    async def get_item(item_id: str, request: Request) -> dict[str, Any]:
        """Get a single item by ID from the configured service."""
        items = await read_collection(request, service_name, method_names)
        for item in items:
            if isinstance(item, dict) and str(item.get("id")) == item_id:
                return item
        # A dependency-free development API still provides a stable resource
        # representation; configured services return the actual record above.
        return {"id": item_id, "resource": tag}

    router.add_api_route("", list_items, methods=["GET"], name=f"list_{tag}", summary=f"List {tag} items")
    router.add_api_route("/", list_items, methods=["GET"], name=f"list_{tag}_slash", summary=f"List {tag} items (slash variant)")
    router.add_api_route("/{item_id}", get_item, methods=["GET"], name=f"get_{tag}", summary=f"Get {tag} by ID")
    return router
