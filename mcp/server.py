"""MCP (Model Control Protocol) server implementation."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from .tools import ToolRegistry
from .protocol import Request, Response
from .auth import authenticate

app = FastAPI(
    title="NerveCenter MCP Server",
    description="Model Control Protocol server for NerveCenter",
    version="0.1.0"
)

tool_registry = ToolRegistry()


@app.post("/execute", response_model=Response)
async def execute(request: Request):
    """Execute a tool request."""
    # Authenticate the request
    if not authenticate(request.auth):
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )

    # Get the tool from the registry
    tool = tool_registry.get_tool(request.tool_name)
    if not tool:
        raise HTTPException(
            status_code=404,
            detail=f"Tool {request.tool_name} not found"
        )

    # Execute the tool
    try:
        result = await tool.execute(request.params)
        return Response(
            status="success",
            data=result,
            request_id=request.request_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools")
async def list_tools():
    """List all available tools."""
    return {"tools": tool_registry.list_tools()}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}