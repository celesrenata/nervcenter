"""NerveCenter Model Context Protocol (MCP) package.

NerveCenter functions as both an MCP *client* and an MCP *server* (spec §45).
The server exposes the §45 tool list (18 tools) over stdio (``python -m mcp``)
and over HTTP (``POST /mcp`` + ``GET /mcp/health`` via ``uvicorn mcp.core:app``),
proxying every call to the §46 NerveCenter HTTP API. The client can speak to
any MCP server implementing the same subset: ``initialize``, ``ping``,
``tools/list``, ``tools/call``.
"""

from mcp.api import ApiError, ContractError, NerveAPI, UnreachableError
from mcp.client import MCPClient
from mcp.core import build_registry, build_server, handle_message, register_all_tools
from mcp.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    PROTOCOL_VERSION,
    SERVER_INFO,
    make_error,
    make_result,
)
from mcp.tools import Tool, ToolError, ToolRegistry, validate_args
from mcp.tools_module import ALL_TOOLS, build_tools

__all__ = [
    "ALL_TOOLS",
    "ApiError",
    "ContractError",
    "INTERNAL_ERROR",
    "INVALID_PARAMS",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "PARSE_ERROR",
    "PROTOCOL_VERSION",
    "MCPClient",
    "NerveAPI",
    "SERVER_INFO",
    "Tool",
    "ToolError",
    "ToolRegistry",
    "UnreachableError",
    "build_registry",
    "build_server",
    "build_tools",
    "handle_message",
    "make_error",
    "make_result",
    "register_all_tools",
    "validate_args",
]
