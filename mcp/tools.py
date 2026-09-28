from typing import Any, Dict, Callable, Awaitable, Optional


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        execute: Callable[[Dict[str, Any]], Awaitable[Any]]
    ) -> None:
        self.name = name
        self.description = description
        self.execute = execute


class ToolRegistry:
    def __init__(self) -> None:
        self.tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        """Register a tool with the registry."""
        self.tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)

    def list_tools(self) -> Dict[str, str]:
        """List all available tools."""
        return {name: tool.description for name, tool in self.tools.items()}