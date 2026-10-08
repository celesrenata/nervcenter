"""Historical model performance endpoint.

This endpoint is a **stub** — it returns 501 Not Implemented until the
inference telemetry service is connected via `app.state.services`.

The web Inference view calls GET /api/models/history to display historical
performance data (per CONTRACT_GAPS.md: "Missing /models/history endpoint for historical performance data").

Contract (web/src/api/client.ts):
- GET /api/models/history → { "model_id": "m-001", "timestamp": "...", "latency_p50": 0.123, "latency_p95": 0.456, "success_rate": 0.99 }
"""
from fastapi import APIRouter, HTTPException
from backend.api.models import ListResponse

router = APIRouter(prefix="/api/models/history", tags=["historical-models"])


@router.get("/", response_model=ListResponse)
async def get_model_history():
    """Get historical model performance data.

    Returns a 501 response until the inference telemetry service is wired.
    """
    raise HTTPException(
        status_code=501,
        detail="Model history endpoint requires the inference telemetry service to be wired via app.state.services."
    )
