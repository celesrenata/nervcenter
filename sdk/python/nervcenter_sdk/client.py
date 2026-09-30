"""Core async HTTP client for the NerveCenter §46 API.

Contract:
- Async ``httpx`` client; configurable base URL (default ``http://localhost:8000``).
- One method per §46 group (see :mod:`nervcenter_sdk.groups`).
- Configurable timeout; exactly ONE retry on HTTP 5xx (and on connect errors).
- Spec §29 correlation: every request carries a ``Nerve-Trace-Id`` header
  (a fresh UUID unless the caller supplies ``trace_id=`` per request or
  ``trace_header_value=`` at construction).
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
TRACE_HEADER = "Nerve-Trace-Id"

__all__ = ["NerveClient", "NerveSync", "ApiError", "ContractError", "UnreachableError"]


class ApiError(Exception):
    """Base error for NerveCenter API calls."""

    def __init__(self, message: str, *, status: int | None = None, detail: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.detail = detail


class ContractError(ApiError):
    """The API answered with HTTP >= 400 or a non-JSON body."""


class UnreachableError(ApiError):
    """Network-level failure (refused, DNS, timeout) after the single retry."""


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


class NerveClient:
    """Async client for the §46 NerveCenter HTTP API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        trace_header_value: str | None = None,
    ) -> None:
        """Create the client.

        Args:
            base_url: API base URL (trailing slash tolerated).
            timeout: Per-request timeout in seconds.
            transport: Optional httpx transport (tests inject MockTransport).
            trace_header_value: Fixed ``Nerve-Trace-Id`` to send on every
                request; when ``None`` a fresh UUID is generated per request.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._fixed_trace_id = trace_header_value
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={"Accept": "application/json"},
        )
        from .groups import (  # deferred to avoid a circular import
            Agents,
            Approvals,
            Changes,
            Claims,
            Clients,
            Compute,
            Context,
            Entities,
            Events,
            Evidence,
            Goals,
            Incidents,
            Models,
            Relationships,
            Routes,
            Runs,
            Search,
            Tasks,
        )

        self.agents = Agents(self)
        self.approvals = Approvals(self)
        self.changes = Changes(self)
        self.claims = Claims(self)
        self.clients = Clients(self)
        self.compute = Compute(self)
        self.context = Context(self)
        self.entities = Entities(self)
        self.events = Events(self)
        self.evidence = Evidence(self)
        self.goals = Goals(self)
        self.incidents = Incidents(self)
        self.models = Models(self)
        self.relationships = Relationships(self)
        self.routes = Routes(self)
        self.runs = Runs(self)
        self.search = Search(self)
        self.tasks = Tasks(self)

    # -- lifecycle ---------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> NerveClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- low-level request --------------------------------------------------

    def _trace_id(self, trace_id: str | None) -> str:
        if trace_id is not None:
            return trace_id
        if self._fixed_trace_id is not None:
            return self._fixed_trace_id
        return uuid.uuid4().hex

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> Any:
        """Perform one HTTP call (with exactly one 5xx/connect retry) and
        decode the JSON body.

        Raises:
            UnreachableError: no transport-level response after the retry.
            ContractError: HTTP status >= 400, or a non-JSON success body.
        """
        headers = {TRACE_HEADER: self._trace_id(trace_id)}
        retried = False
        while True:
            try:
                response = await self._client.request(
                    method, path, params=params, json=json_body, headers=headers
                )
            except httpx.HTTPError as exc:
                if not retried:
                    # Exactly one retry on connect-level failures as well.
                    retried = True
                    continue
                raise UnreachableError(
                    f"cannot reach NerveCenter API at {self.base_url} ({exc.__class__.__name__})",
                    detail=str(exc),
                ) from exc
            if response.status_code >= 500 and not retried:
                # Exactly one retry on 5xx.
                retried = True
                continue
            if response.status_code >= 400:
                raise ContractError(
                    f"{method} {path} returned HTTP {response.status_code}",
                    status=response.status_code,
                    detail=_safe_json(response),
                )
            if response.status_code == 204 or not response.text:
                return None
            try:
                return response.json()
            except ValueError as exc:
                raise ContractError(f"{method} {path} returned a non-JSON body") from exc

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> Any:
        """Perform a GET request."""
        return await self.request("GET", path, params=params, trace_id=trace_id)

    async def post(
        self,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> Any:
        """Perform a POST request."""
        return await self.request("POST", path, json_body=json_body, trace_id=trace_id)

    # -- convenience ---------------------------------------------------------

    async def health(self, *, trace_id: str | None = None) -> Any:
        """GET /api/health."""
        return await self.get("/api/health", trace_id=trace_id)

    async def version(self, *, trace_id: str | None = None) -> Any:
        """GET /version."""
        return await self.get("/version", trace_id=trace_id)


class NerveSync:
    """Small sync convenience wrapper around :class:`NerveClient`.

    Runs the async client on a private event loop per call; safe to use from
    plain (non-async) scripts.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 10.0,
        trace_header_value: str | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._trace_header_value = trace_header_value

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access (group names, health, version, ...) to
        a fresh async client."""

        def _proxy(*args: Any, **kwargs: Any) -> Any:
            async def _make() -> Any:
                async with NerveClient(
                    self._base_url,
                    timeout=self._timeout,
                    trace_header_value=self._trace_header_value,
                ) as client:
                    target = getattr(client, name)
                    if asyncio.iscoroutinefunction(target):
                        return await target(*args, **kwargs)
                    return target

            return asyncio.run(_make())

        return _proxy
