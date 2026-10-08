"""Systems endpoints for the NerveCenter API.

This endpoint is a **stub** — it returns 501 Not Implemented until the
systems service is connected via `app.state.services`.

The web Systems view calls these endpoints to display system health and metrics.
"""
from fastapi import APIRouter, HTTPException
from backend.api.models import ListResponse

router = APIRouter(prefix="/api/systems", tags=["systems"])


@router.get("/", response_model=ListResponse)
async def list_systems():
    """List systems.

    Returns a 501 response until the systems service is wired.
    """
    raise HTTPException(
        status_code=501,
        detail="Systems list endpoint requires the systems service to be wired via app.state.services."
    )
