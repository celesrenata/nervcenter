"""Tool model, JSON-schema input validation, and the tool registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


class ToolError(Exception):
    """A tool invocation failed with a reportable error."""


def validate_args(schema: dict[str, Any], args: dict[str, Any]) -> None:
    """Light JSON-schema validation: required keys plus primitive types.

    Full JSON-schema semantics are out of scope for this v0 surface; the
    input schema is still published per tool (spec §45) for client use.
    """
    properties = schema.get("properties") or {}
    for key in schema.get("required", []):
        if key not in args:
            raise ToolError(f"missing required argument: {key}")
    for key, value in args.items():
        spec = properties.get(key) or {}
        expected = spec.get("type")
        if expected is None or expected not in TYPE_MAP:
            continue
        if isinstance(value, bool) and expected in ("integer", "number"):
            raise ToolError(f"argument {key!r} expected {expected}")
        if not isinstance(value, TYPE_MAP[expected]):
            raise ToolError(f"argument {key!r} expected type {expected}")


@dataclass
class Tool:
    """A single MCP tool: name, description, input schema, handler."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any], Any], Awaitable[Any]]

    def descriptor(self) -> dict[str, Any]:
        """Return the ``tools/list`` descriptor with a JSON-schema input."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": dict(self.input_schema.get("properties", {})),
                "required": list(self.input_schema.get("required", [])),
            },
        }


class ToolRegistry:
    """Holds the tools a server exposes plus call dispatch."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        """Register a tool; later registrations of the same name win."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP tool descriptors in stable registration order."""
        return [tool.descriptor() for tool in self._tools.values()]

    async def call(self, name: str, args: dict[str, Any], api: Any) -> dict[str, Any]:
        """Execute a tool and wrap the result as an MCP tool result."""
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"unknown tool: {name}")
        try:
            validate_args(tool.input_schema, args)
            result = await tool.handler(args, api)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(f"{exc.__class__.__name__}: {exc}") from exc
        if result is None:
            result = {}
        text = result if isinstance(result, str) else json.dumps(result, indent=2, default=str)
        return {
            "content": [{"type": "text", "text": text}],
            "structuredContent": result,
            "isError": False,
        }
