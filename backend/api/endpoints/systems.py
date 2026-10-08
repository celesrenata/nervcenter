"""Systems endpoints for the NerveCenter API.

``GET /api/systems`` returns live system-status rows (the web Systems view
contract: ``{name, status, version, message, checkedAt}``) from the
``systems`` service on ``app.state.services``.

Honesty contract
----------------
- Service **present** on ``app.state.services`` → HTTP 200 with the rows the
  service composes from the *real* dependency probes (PostgreSQL / NATS / the
  API itself). See :class:`backend.services.systems.SystemsService`.
- Service **absent** (genuinely unwired) → the *precise* 501 below is kept so
  the frontend banner stays truthful rather than rendering a fabricated list.
"""
from fastapi import APIRouter, HTTPException, Request

from backend.api.models import ListResponse
from backend.api.endpoints._helpers import list_response

router = APIRouter(prefix="/api/systems", tags=["systems"])

_UNWIRED_DETAIL = (
    "Systems list endpoint requires the systems service to be wired via app.state.services."
)


@router.get("/", response_model=ListResponse)
async def list_systems(request: Request):
    """List live system-status rows.

    Returns 200 with data when the ``systems`` service is wired, and the
    precise 501 (see module docstring) when it is genuinely unwired.
    """
    services = getattr(request.app.state, "services", {}) or {}
    service = services.get("systems") if isinstance(services, dict) else None
    if service is None:
        raise HTTPException(status_code=501, detail=_UNWIRED_DETAIL)

    try:
        rows = await service.list_systems()
    except Exception:
        # A live systems report is the whole point of this endpoint; if the
        # probe pass blows up we degrade to the honest 501 rather than emit
        # a partially fabricated list.
        raise HTTPException(status_code=501, detail=_UNWIRED_DETAIL) from None

    return list_response(rows)
