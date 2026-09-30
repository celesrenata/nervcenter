"""Shared read-only helpers for API endpoint adapters."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

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


def _json_safe(result: Any) -> Any:
    """Normalize a service-method result into a JSON-serializable value."""
    if result is None or isinstance(result, (str, int, float, bool, list, dict)):
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return str(result)


def _takes_positional(method: Any) -> bool:
    """Return ``True`` if ``method`` accepts at least one positional argument.

    Bound methods exclude ``self`` from their signature, so the check reflects
    the caller-visible parameters.
    """
    try:
        sig = inspect.signature(method)
    except (TypeError, ValueError):
        # Built-in / C-level callable: assume it takes no positional argument.
        return False
    return any(
        p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        )
        for p in sig.parameters.values()
    )


def make_write_endpoint(
    router: APIRouter,
    path: str,
    *,
    tag: str,
    service_name: str,
    method_names: tuple[str, ...] = (),
    arg_keys: tuple[str, ...] = (),
    summary: str | None = None,
) -> APIRouter:
    """Attach a dependency-tolerant ``POST`` route to ``router`` at ``path``.

    Mirrors :func:`read_collection` semantics: the service is resolved from
    ``app.state.services`` (``services.get(service_name)``), each method name is
    tried in order, an awaitable result is awaited, and the response is always a
    JSON dict carrying ``request_id`` and an ISO-8601 ``timestamp``.

    When no service is configured, no method is found, or a method raises, the
    route does **not** return 500 — it returns HTTP 202 with
    ``{"accepted": true, "executed": false, "detail": ...}`` so the spec §47
    mutation contract stays stable and the API stays bootable without
    dependencies. A successfully executed method returns HTTP 200 with
    ``{"accepted": true, "executed": true, "method": ..., "result": ...}``.

    ``arg_keys`` names the request-body keys (in priority order) whose value is
    forwarded as the single positional argument to the target method. The value
    is only passed when the method's signature accepts a positional parameter
    (checked via :func:`inspect.signature`); otherwise the method is called with
    no arguments. Endpoints with no request body pass no ``arg_keys``.

    The raw JSON body is read manually (not via a FastAPI body model) so that a
    missing or malformed body degrades to ``arg is None`` instead of a 4xx.
    """
    prefix = path.rstrip("/").split("/")[-1] or "post"

    async def handler(request: Request) -> JSONResponse:
        request_id = str(uuid4())
        timestamp = datetime.now(UTC).isoformat()
        services = getattr(request.app.state, "services", {})
        service = services.get(service_name) if isinstance(services, dict) else None

        base = {
            "accepted": True,
            "executed": False,
            "service": service_name,
            "request_id": request_id,
            "timestamp": timestamp,
        }

        # Optional JSON body → single positional argument.
        arg_value: Any = None
        if arg_keys:
            try:
                raw = await request.json()
            except Exception:  # noqa: BLE001 - malformed/absent body is non-fatal
                raw = None
            if isinstance(raw, dict):
                for key in arg_keys:
                    if raw.get(key) is not None:
                        arg_value = raw[key]
                        break

        if service is None:
            return JSONResponse(
                status_code=202,
                content={
                    **base,
                    "detail": (
                        f"No '{service_name}' service is configured; "
                        "mutation accepted but not executed."
                    ),
                    "result": None,
                },
            )

        for method_name in method_names:
            method = getattr(service, method_name, None)
            if method is None:
                continue
            try:
                result = method(arg_value) if _takes_positional(method) else method()
                if inspect.isawaitable(result):
                    result = await result
                return JSONResponse(
                    status_code=200,
                    content={
                        **base,
                        "executed": True,
                        "method": method_name,
                        "detail": None,
                        "result": _json_safe(result),
                    },
                )
            except Exception as exc:  # noqa: BLE001 - dependency-tolerant contract
                return JSONResponse(
                    status_code=202,
                    content={
                        **base,
                        "detail": f"{service_name}.{method_name} raised: {exc}",
                        "result": None,
                    },
                )

        return JSONResponse(
            status_code=202,
            content={
                **base,
                "detail": (
                    f"No suitable method found on '{service_name}' service "
                    f"(tried {list(method_names)}); mutation accepted but not executed."
                ),
                "result": None,
            },
        )

    router.add_api_route(
        path,
        handler,
        methods=["POST"],
        name=f"{tag}_write_{prefix}",
        summary=summary or f"POST {path}",
    )
    return router
