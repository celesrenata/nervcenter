"""Agent service endpoints."""
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.api.endpoints._helpers import make_write_endpoint
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
make_write_endpoint(
    router,
    "/api/agents/pause",
    tag="agents",
    service_name="agents",
    method_names=("pause", "pause_agents"),
    summary="Pause all agents (§47 `nerve pause-agents`)",
)
