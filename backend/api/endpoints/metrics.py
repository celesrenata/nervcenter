"""Metrics endpoints for the NerveCenter API.

This endpoint is a **stub** — it returns 501 Not Implemented until the
metrics service is connected via `app.state.services`.

Note: This differs from `backend/api/observability.py` which serves
the OpenTelemetry/Prometheus metrics. This is for the web Systems view.
"""
from fastapi import APIRouter, HTTPException
from backend.api.models import ListResponse

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/", response_model=ListResponse)
async def list_metrics():
    """List metrics.

    Returns a 501 response until the metrics service is wired.
    """
    raise HTTPException(
        status_code=501,
        detail="Metrics list endpoint requires the metrics service to be wired via app.state.services."
    )
