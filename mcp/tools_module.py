"""§45 tool catalogue and construction.

``ALL_TOOLS`` holds the spec §45 tool list (18 tools) as plain schema entries
(name, description, JSON-schema input, plus the §46 API operation each one
proxies). ``build_tools()`` turns that catalogue into :class:`mcp.tools.Tool`
instances bound to a §46 API base URL (argument → ``NERVE_API`` env →
``http://localhost:8000``); every proxied call carries a fresh
``Nerve-Trace-Id`` (spec §29) via :class:`mcp.api.NerveAPI`.

POSTs the backend does not implement yet (create_goal, update_goal,
create_task, report_claim, report_artifact, create_planned_change) are still
proxied: the API is dependency-tolerant and answers 2xx — typically 202 with
``request_id`` + ``timestamp`` — and any 2xx is treated as success.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.api import DEFAULT_BASE_URL, ContractError, NerveAPI
from mcp.tools import Tool

Handler = Callable[[dict[str, Any], NerveAPI | None], Awaitable[Any]]


def resolve_base_url(base_url: str | None = None) -> str:
    """Base URL for the §46 API: argument → ``NERVE_API`` env → localhost default."""
    if base_url:
        return base_url
    return os.environ.get("NERVE_API") or DEFAULT_BASE_URL


def _string_arg(description: str) -> dict[str, Any]:
    """One string property spec for a JSON-schema input object."""
    return {"type": "string", "minLength": 1, "description": description}


def _id_arg(description: str) -> dict[str, Any]:
    """One id string property spec (loose identifier pattern)."""
    spec = _string_arg(description)
    spec["pattern"] = "^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    return spec


def _object_arg(description: str) -> dict[str, Any]:
    """One free-form JSON-object property spec (payload)."""
    return {"type": "object", "additionalProperties": True, "description": description}


async def _proxy(
    api: NerveAPI,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    """Proxy one tool call to the §46 API; any 2xx (incl. 202) is success."""
    if method == "GET":
        return await api.get(path, params=params)
    return await api.post(path, json_body=body if body is not None else {})


async def _entity_timeline(args: dict[str, Any], api: NerveAPI) -> Any:
    """GET /api/events?entity=<id> — the event timeline of one entity."""
    return await _proxy(api, "GET", "/api/events", params={"entity": args["id"]})


async def _compile_context(args: dict[str, Any], api: NerveAPI) -> Any:
    """POST /api/context/compile, falling back to GET /api/context on 405.

    The live API only guarantees ``GET /api/context`` and ``POST
    /api/context/ask``; the compile endpoint is the newer contract.
    """
    try:
        return await api.post("/api/context/compile", json_body=dict(args))
    except ContractError as exc:
        if exc.status != 405:
            raise
        return await api.get("/api/context")


def _plain_handler(method: str, path: str) -> Handler:
    """Executor that proxies straight to one §46 endpoint.

    Argument routing:
    - path ``{id}``: the ``id`` argument fills the path; for POSTs the
      ``body`` argument (if present) is the JSON body, else the whole args
      dict.
    - other GETs: every argument becomes a query parameter
      (e.g. ``GET /api/search?q=...``, ``GET /api/events?entity=<id>``).
    - other POSTs: the whole args dict is the JSON body.
    """

    async def handler(args: dict[str, Any], api: NerveAPI) -> Any:
        if "{id}" in path:
            filled = path.format(id=args["id"])
            if method == "GET":
                return await _proxy(api, method, filled)
            body = args.get("body")
            payload = dict(body) if body is not None else dict(args)
            return await _proxy(api, method, filled, body=payload)
        if method == "GET":
            return await _proxy(api, method, path, params=dict(args))
        return await _proxy(api, method, path, body=dict(args))

    return handler


def _make_handler(method: str, path: str, kind: str, base_url: str) -> Handler:
    """Bind an executor to the resolved §46 base URL (used when no API is injected)."""

    if kind == "context":
        runner: Handler = _compile_context
    elif kind == "timeline":
        runner = _entity_timeline
    elif kind == "plain":
        runner = _plain_handler(method, path)
    else:
        raise ValueError(f"unknown handler kind: {kind!r}")

    async def handler(args: dict[str, Any], api: NerveAPI | None) -> Any:
        if api is None:
            async with NerveAPI(base_url) as bound:
                return await runner(args, bound)
        return await runner(args, api)

    return handler


# name, description, properties, required, §46 method, §46 path, handler kind
_SPEC: list[tuple[str, str, dict[str, Any], list[str], str, str, str]] = [
    (
        "search_entities",
        "Search NerveCenter knowledge (entities, events, evidence) with a free-text query "
        "(§46 GET /api/search).",
        {"q": _string_arg("Free-text search query")},
        ["q"],
        "GET",
        "/api/search",
        "plain",
    ),
    (
        "get_entity",
        "Fetch a single entity by id from the knowledge plane (§46 GET /api/entities/{id}).",
        {"id": _id_arg("Entity id")},
        ["id"],
        "GET",
        "/api/entities/{id}",
        "plain",
    ),
    (
        "get_entity_timeline",
        "List the event timeline for one entity (§46 GET /api/events?entity={id}).",
        {"id": _id_arg("Entity id (sent as the ?entity= query parameter)")},
        ["id"],
        "GET",
        "/api/events",
        "timeline",
    ),
    (
        "get_recent_changes",
        "List recent change records across the knowledge plane (§46 GET /api/changes).",
        {},
        [],
        "GET",
        "/api/changes",
        "plain",
    ),
    (
        "get_goal",
        "Fetch one persistent goal by id (§46 GET /api/goals/{id}).",
        {"id": _id_arg("Goal id")},
        ["id"],
        "GET",
        "/api/goals/{id}",
        "plain",
    ),
    (
        "create_goal",
        "Create a persistent goal (spec §4.5). Proxies §46 POST /api/goals; a 202 accept is "
        "success.",
        {
            "name": _string_arg("Goal name"),
            "body": _object_arg(
                "Optional extra goal fields (description, criteria, ...) merged into the POST body"
            ),
        },
        ["name"],
        "POST",
        "/api/goals",
        "plain",
    ),
    (
        "update_goal",
        "Update an existing goal. Proxies §46 POST /api/goals/{id}; a 202 accept is success.",
        {
            "id": _id_arg("Goal id"),
            "body": _object_arg("Goal fields to update (status, progress, criteria, ...)"),
        },
        ["id"],
        "POST",
        "/api/goals/{id}",
        "plain",
    ),
    (
        "get_task",
        "Fetch one task from the execution plane by id (§46 GET /api/tasks/{id}).",
        {"id": _id_arg("Task id")},
        ["id"],
        "GET",
        "/api/tasks/{id}",
        "plain",
    ),
    (
        "create_task",
        "Create a task in the task DAG. Proxies §46 POST /api/tasks; a 202 accept is success.",
        {
            "name": _string_arg("Task name"),
            "body": _object_arg(
                "Optional extra task fields (goal_id, dependencies, ...) merged into the POST body"
            ),
        },
        ["name"],
        "POST",
        "/api/tasks",
        "plain",
    ),
    (
        "report_claim",
        "Report a claim (an evidence-backed assertion, spec §4.3). Proxies §46 POST /api/claims; "
        "a 202 accept is success.",
        {"body": _object_arg("Claim payload (statement, type, confidence, evidence, ...)")},
        [],
        "POST",
        "/api/claims",
        "plain",
    ),
    (
        "report_artifact",
        "Report an artifact / evidence record. Proxies §46 POST /api/evidence; a 202 accept is success",  # noqa: E501
        {"body": _object_arg("Artifact payload (kind, uri, hash, ...)")},
        [],
        "POST",
        "/api/evidence",
        "plain",
    ),
    (
        "compile_context",
        "Compile a context package (entities, events, evidence, claims) for a focus area.",
        {
            "question": _string_arg("Question or focus area to compile context for"),
            "body": _object_arg(
                "Optional compile options (entity ids, recency window, max tokens), the POST body"
            ),
        },
        [],
        "POST",
        "/api/context/compile",
        "context",
    ),
    (
        "get_compute",
        "Show compute fabric state: GPUs, hosts, utilization (§46 GET /api/compute).",
        {},
        [],
        "GET",
        "/api/compute",
        "plain",
    ),
    (
        "get_models",
        "List known inference models and their observed state (§46 GET /api/models).",
        {},
        [],
        "GET",
        "/api/models",
        "plain",
    ),
    (
        "get_route_history",
        "List recent OmniRoute routing decisions (§46 GET /api/routes).",
        {},
        [],
        "GET",
        "/api/routes",
        "plain",
    ),
    (
        "get_incident",
        "Fetch one incident and its investigation state by id (§46 GET /api/incidents/{id}).",
        {"id": _id_arg("Incident id")},
        ["id"],
        "GET",
        "/api/incidents/{id}",
        "plain",
    ),
    (
        "start_investigation",
        "Start (or resume) an investigation for an incident. Proxies §46 POST "
        "/api/incidents/investigate; a 202 accept is success.",
        {
            "id": _id_arg("Incident id"),
            "body": _object_arg("Optional investigation options (focus, constraints, ...)"),
        },
        ["id"],
        "POST",
        "/api/incidents/investigate",
        "plain",
    ),
    (
        "create_planned_change",
        "Create a planned change record. Proxies §46 POST /api/changes; a 202 accept is success.",
        {"body": _object_arg("Planned change payload (what/why/impact, rollback plan, ...)")},
        [],
        "POST",
        "/api/changes",
        "plain",
    ),
]


ALL_TOOLS: list[dict[str, Any]] = [
    {
        "name": name,
        "description": description,
        "input_schema": {"type": "object", "properties": properties, "required": required},
        "method": method,
        "path": path,
    }
    for name, description, properties, required, method, path, _kind in _SPEC
]


def build_tools(base_url: str | None = None) -> list[Tool]:
    """Build the 18 §45 :class:`Tool` instances bound to a §46 API base URL."""
    resolved = resolve_base_url(base_url)
    tools: list[Tool] = []
    for name, description, properties, required, method, path, kind in _SPEC:
        tools.append(
            Tool(
                name=name,
                description=description,
                input_schema={"type": "object", "properties": properties, "required": required},
                handler=_make_handler(method, path, kind, resolved),
            )
        )
    return tools
