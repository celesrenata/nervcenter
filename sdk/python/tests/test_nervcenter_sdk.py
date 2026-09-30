"""Tests for the NerveCenter Python SDK.

Runs fully offline against ``httpx.MockTransport`` — no live server needed.
Covers (per T102): a GET, a POST, and §29 correlation-header presence.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import pytest
from nervcenter_sdk import (
    ContractError,
    NerveClient,
    NerveSync,
    UnreachableError,
)
from nervcenter_sdk.client import TRACE_HEADER


def _respond(status: int, body: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=body if body is not None else {})


def _trace(request: httpx.Request) -> str:
    """Read the §29 correlation header (case-insensitive)."""
    value = request.headers.get(TRACE_HEADER)
    assert value is not None, "Nerve-Trace-Id header missing from request"
    return value


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------


async def test_get_unwraps_envelope_and_correlation_header_is_present() -> None:
    """GET /api/goals returns the §46 envelope; Nerve-Trace-Id is sent."""
    seen_traces: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_traces.append(_trace(request))
        return httpx.Response(
            200,
            json={
                "data": [{"id": "goal-1", "name": "Goal 1", "status": "active"}],
                "meta": {"version": "1.0.0", "request_id": "req-1"},
            },
        )

    transport = httpx.MockTransport(handler)
    async with NerveClient(base_url="http://test.example", transport=transport) as client:
        goals = await client.goals.list()

    assert goals == [{"id": "goal-1", "name": "Goal 1", "status": "active"}]
    # §29: every request carries the correlation header with a valid UUID.
    trace = seen_traces[0]
    assert uuid.UUID(trace.replace("-", "")) is not None


async def test_get_caller_supplied_trace_id_is_used() -> None:
    """When the caller supplies a trace id, exactly that value is sent."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert _trace(request) == "fixed-trace-abc123"
        return _respond(200, {"status": "ok"})

    transport = httpx.MockTransport(handler)
    async with NerveClient(base_url="http://test.example", transport=transport) as client:
        await client.health(trace_id="fixed-trace-abc123")


# ---------------------------------------------------------------------------
# POST
# ---------------------------------------------------------------------------


async def test_post_sends_json_body_and_returns_payload() -> None:
    """POST /api/context/ask sends the question body and returns the answer."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["body"] = json.loads(request.content)
        captured["trace"] = _trace(request)
        return httpx.Response(200, json={"answer": "because the deploy restarted it"})

    transport = httpx.MockTransport(handler)
    async with NerveClient(base_url="http://test.example", transport=transport) as client:
        result = await client.context.ask("why did hellodj restart?")

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/context/ask"
    assert captured["body"] == {"question": "why did hellodj restart?"}
    # §29 correlation header on POSTs as well.
    assert uuid.UUID(captured["trace"].replace("-", "")) is not None
    assert result == {"answer": "because the deploy restarted it"}


# ---------------------------------------------------------------------------
# Retry on 5xx — exactly one
# ---------------------------------------------------------------------------


async def test_5xx_is_retried_exactly_once_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"detail": "unavailable"})
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    async with NerveClient(base_url="http://test.example", transport=transport) as client:
        result = await client.health()

    assert result == {"status": "ok"}
    assert calls["n"] == 2  # one retry, no more


async def test_5xx_retries_once_then_raises_contract_error() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"detail": "boom"})

    transport = httpx.MockTransport(handler)
    async with NerveClient(base_url="http://test.example", transport=transport) as client:
        with pytest.raises(ContractError) as excinfo:
            await client.health()

    assert calls["n"] == 2  # initial + exactly one retry
    assert excinfo.value.status == 500


async def test_4xx_is_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, json={"detail": "Entity not found"})

    transport = httpx.MockTransport(handler)
    async with NerveClient(base_url="http://test.example", transport=transport) as client:
        with pytest.raises(ContractError) as excinfo:
            await client.entities.get("ent-99")

    assert calls["n"] == 1  # no retry on 4xx
    assert excinfo.value.status == 404


async def test_unreachable_after_retry_raises() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("refused")

    transport = httpx.MockTransport(handler)
    async with NerveClient(base_url="http://test.example", transport=transport) as client:
        with pytest.raises(UnreachableError):
            await client.health()

    assert calls["n"] == 2  # one retry on connect failure


# ---------------------------------------------------------------------------
# Sync convenience wrapper
# ---------------------------------------------------------------------------


def test_sync_wrapper_gets_health_with_mock_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """NerveSync wraps the async client and returns decoded JSON."""
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["trace"] = _trace(request)
        return httpx.Response(
            200, json={"status": "ok", "version": "0.1.0", "checks": {}}
        )

    # Patch the module-level AsyncClient so NerveSync's internal client uses
    # the mock transport without a live server.
    import nervcenter_sdk.client as sdk_client

    original = sdk_client.httpx.AsyncClient

    def fake_async_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = kwargs.get("transport") or httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(sdk_client.httpx, "AsyncClient", fake_async_client)
    sync = NerveSync(base_url="http://test.example")
    result = sync.health()
    assert result == {"status": "ok", "version": "0.1.0", "checks": {}}
    assert uuid.UUID(captured["trace"].replace("-", "")) is not None
