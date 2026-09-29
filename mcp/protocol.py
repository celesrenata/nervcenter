"""JSON-RPC 2.0 wire model for the NerveCenter MCP server and client.

Implements the wire subset of the Model Context Protocol (MCP) that
NerveCenter needs: ``initialize``, ``ping``, ``tools/list``, and
``tools/call``. The message shape is the only contract; the stdio and HTTP
transports both share the same handler implementation.
"""

from __future__ import annotations

from typing import Any

JSONRPC_VERSION = "2.0"
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO: dict[str, str] = {"name": "nervcenter-mcp", "version": "0.1.0"}

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
INVALID_PARAMS = -32602
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603


class InvalidRequestError(ValueError):
    """The received message is not a valid JSON-RPC 2.0 request."""


class MethodNotFoundError(Exception):
    """The server has no method with the given name."""

    def __init__(self, method: str) -> None:
        super().__init__(f"method not found: {method}")
        self.method = method


def is_notification(message: dict[str, Any]) -> bool:
    """A JSON-RPC notification has no ``id`` and expects no response."""
    return "id" not in message


def make_result(request_id: object, result: Any) -> dict[str, Any]:
    """Build a JSON-RPC result envelope."""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "result": result,
    }


def make_error(request_id: object, code: int, message: str, data: Any = None) -> dict[str, Any]:
    """Build a JSON-RPC error envelope."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": error,
    }
