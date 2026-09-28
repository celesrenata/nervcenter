"""Agent service endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from backend.api.models import ListResponse, ApiResponseMeta
from datetime import datetime

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=ListResponse)
async def list_agents():
    """List all agents."""
    # In a real implementation, this would query the database
    agents = [
        {"id": "agent-1", "name": "Agent 1", "status": "active"},
        {"id": "agent-2", "name": "Agent 2", "status": "inactive"},
    ]

    return ListResponse(
        data=agents,
        meta=ApiResponseMeta(
            version="1.0.0",
            request_id="req-123",
            timestamp=datetime.utcnow(),
            pagination={"total": len(agents), "page": 1, "per_page": 10},
        ),
    )


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details."""
    # In a real implementation, this would query the database
    if agent_id not in ["agent-1", "agent-2"]:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "id": agent_id,
        "name": f"Agent {agent_id[-1]}",
        "status": "active" if agent_id == "agent-1" else "inactive",
    }