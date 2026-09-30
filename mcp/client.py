"""MCP client for the NerveCenter MCP server (new wire model).

Speaks the wave-2 JSON-RPC 2.0 subset — ``initialize``, ``ping``,
``tools/list``, ``tools/call`` — over HTTP (``POST /mcp`` on the mcp
service). This is the client side of spec §45 ("NerveCenter must function as
both MCP client and MCP server"); any server implementing the same subset is
usable.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from mcp.api import TRACE_HEADER

DEFAULT_BASE_URL = "http://localhost:8000"


class MCPError(Exception):
    """The MCP server answered with a JSON-RPC error envelope."""

    def __init__(self, error: dict[str, Any]) -> None:
        super().__init__(f"MCP error {error.get('code')}: {error.get('message')}")
        self.code = error.get("code")
        self.message = error.get("message")
        self.data = error.get("data")


class MCPClient:
    """Async client for the NerveCenter MCP server over HTTP.

    Usage::

        async with MCPClient("http://localhost:8000") as client:
            await client.initialize()
            tools = await client.list_tools()
            result = await client.call_tool("get_compute")
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url, timeout=timeout, transport=transport
        )
        self._next_id = 0

    def _make_message(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        self._next_id += 1
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            message["params"] = params
        return message

    async def _rpc(
        self, method: str, params: dict[str, Any] | None = None, *, notification: bool = False
    ) -> Any:
        """Send one JSON-RPC message to ``POST /mcp`` and return the result."""
        message = self._make_message(method, params)
        if notification:
            message.pop("id")
        response = await self._client.post(
            "/mcp", json=message, headers={TRACE_HEADER: uuid.uuid4().hex}
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.text:
            return None
        body = response.json()
        if "error" in body:
            raise MCPError(body["error"])
        return body.get("result")

    async def initialize(self) -> dict[str, Any] | None:
        """Perform the MCP ``initialize`` handshake."""
        return await self._rpc("initialize", {})

    async def ping(self) -> dict[str, Any] | None:
        """Send ``ping``; a healthy server returns an empty result."""
        return await self._rpc("ping")

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the server's ``tools/list`` descriptors."""
        result = await self._rpc("tools/list")
        return list(result.get("tools", [])) if result else []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Invoke one tool (``tools/call``) and return the result envelope."""
        return await self._rpc(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> MCPClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
