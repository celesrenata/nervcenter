"""MCP (Model Control Protocol) client implementation."""
import httpx
from typing import Any, Dict

from .protocol import Request, Response


class MCPClient:
    """Client for the MCP server."""

    def __init__(self, base_url: str):
        """Initialize the MCP client.

        Args:
            base_url: The base URL of the MCP server.
        """
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient()

    async def execute(self, tool_name: str, params: Dict[str, Any], auth: Dict[str, str]) -> Response:
        """Execute a tool on the server.

        Args:
            tool_name: The name of the tool to execute.
            params: The parameters to pass to the tool.
            auth: Authentication information (token).

        Returns:
            The response from the server.
        """
        request = Request(
            tool_name=tool_name,
            params=params,
            auth=auth,
            request_id="client-" + str(hash((tool_name, params, auth)))
        )
        response = await self.client.post(
            f"{self.base_url}/execute",
            json=request.model_dump()
        )
        return Response(**response.json())

    async def list_tools(self) -> Dict[str, Any]:
        """List all available tools on the server.

        Returns:
            A dictionary mapping tool names to their descriptions.
        """
        response = await self.client.get(f"{self.base_url}/tools")
        return response.json()

    async def close(self):
        """Close the client connection."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()