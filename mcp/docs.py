"""MCP (Model Control Protocol) documentation.

This module provides the documentation for the MCP server and client.

MCP Overview
------------
The Model Control Protocol (MCP) enables communication between model clients
and the NerveCenter core. It provides:

- Tool execution: Execute registered tools on the server
- Tool discovery: List available tools
- Authentication: Token-based authentication for requests
- Request/Response protocol: Structured communication between client and server

Setup
-----
To set up the MCP server:

```python
from mcp.server import app, tool_registry
from mcp.tools import Tool

# Define a tool
async def example_tool(params: dict) -> dict:
    return {"result": "Hello, World!"}

# Register the tool
tool_registry.register_tool(Tool(
    name="example_tool",
    description="An example tool",
    execute=example_tool
))
```

To use the MCP client:

```python
import asyncio
from mcp.client import MCPClient

async def main():
    client = MCPClient("http://localhost:8000")
    
    # List tools
    tools = await client.list_tools()
    print(tools)
    
    # Execute a tool
    response = await client.execute(
        tool_name="example_tool",
        params={},
        auth={"token": "your-token"}
    )
    print(response)
    
    await client.close()

asyncio.run(main())
```

API Reference
-------------
The MCP server exposes the following endpoints:

- POST /execute: Execute a tool
  - Request body:
    - tool_name: str
    - params: dict
    - auth: dict (optional)
  - Response:
    - status: str (success, error, pending)
    - data: any (result data)
    - message: str (optional)

- GET /tools: List available tools
  - Response:
    - tools: dict (tool_name -> description)

Authentication
--------------
The MCP uses token-based authentication. Clients must include a valid token
in the `auth` field of their requests.

To authenticate:

1. Login with credentials:
```bash
curl -X POST http://localhost:8000/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"username": "admin", "password": "password"}'
```

2. Use the returned token in your requests:
```bash
curl -X POST http://localhost:8000/execute \\
  -H "Content-Type: application/json" \\
  -d '{
    "tool_name": "example_tool",
    "params": {},
    "auth": {"token": "your-token"}
  }'
```
"""