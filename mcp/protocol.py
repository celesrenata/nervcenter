"""Protocol definitions for the MCP (Model Control Protocol)."""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Request(BaseModel):
    """MCP request model."""
    tool_name: str
    params: Dict[str, Any]
    auth: Optional[Dict[str, str]] = None
    request_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Response(BaseModel):
    """MCP response model."""
    status: str  # success, error, pending
    data: Optional[Any] = None
    message: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)