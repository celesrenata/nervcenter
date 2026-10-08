"""Agent service endpoints.

Read routes expose the (read-only) agent registry data. The ``pause``
mutation under ``/api/agents`` has **no** backing persistence/service
contract (the agent registry is an in-memory, non-mutable surface), so the
endpoint returns an explicit, honest ``501 Not Implemented`` rather than a
fake ``202 accepted`` that would pretend the pause was applied.
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.api.models import ApiResponseMeta, ListResponse

# The agents collection spans two prefix families:
#   - legacy read routes under ``/agents`` (``GET /agents/``, ``GET /agents/{id}``);
#   - the spec §47 mutation endpoint under the canonical ``/api/agents`` prefix.
# ``backend.api.app`` registers this single router and *separately* installs the
# ``/api/agents`` GET canonical aliases (see ``canonical_aliases``), which
# delegate to the module-level :func:`list_agents` / :func:`get_agent` below.
# The router is therefore prefix-less and declares full paths so both families
# resolve without a trailing-slash redirect.
router = APIRouter(tags=["agents"])


@router.get("/agents/", response_model=ListResponse)
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


@router.get("/agents/{agent_id}")
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


# §47 `nerve pause-agents` → POST /api/agents/pause (canonical path).
@router.post("/api/agents/pause", status_code=501)
async def pause_agents() -> dict[str, Any]:
    """Pause all agents.

    There is no durable agent-mutation persistence/service contract behind
    this endpoint yet, so we refuse to pretend the pause took effect.
    Callers must treat a ``501`` as "not implemented".
    """
    return {
        "status": "not_implemented",
        "detail": (
            "POST /api/agents/pause is not implemented: no agent-mutation "
            "persistence/service contract exists. This endpoint returns 501 "
            "rather than a fake 202 acceptance, so callers cannot assume "
            "the agents were paused."
        ),
    }
