"""Decisions endpoints for the NerveCenter API.

This endpoint is a **stub** — it returns 501 Not Implemented until the
decisions service is connected via `app.state.services`.

The web Timeline view calls these endpoints to display decisions.
Contract (web/src/api/client.ts):
- GET /api/decisions → list decisions
- GET /api/decisions/{decision_id} → get single decision
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from backend.api.models import ApiResponseMeta, ListResponse

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


@router.get("/", response_model=ListResponse)
async def list_decisions():
    """List decisions.

    Returns a 501 response until the decisions service is wired.
    """
    raise HTTPException(
        status_code=501,
        detail="Decisions list endpoint requires the decisions service to be wired via app.state.services."
    )


@router.get("/{decision_id}")
async def get_decision(decision_id: str):
    """Get a single decision by ID.

    Returns a 501 response until the decisions service is wired.
    """
    raise HTTPException(
        status_code=501,
        detail=f"Decision {decision_id} requires the decisions service to be wired via app.state.services."
    )
