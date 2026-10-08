"""Claims API adapters.

Reads are served by the shared read router (empty when the claims service is
not configured). Writes are **not** backed by a real persistence/service
contract yet, so ``POST /api/claims`` returns an explicit, honest ``501 Not
Implemented`` instead of a fake ``202 accepted`` that would pretend the claim
was recorded.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/claims",
    tag="claims",
    service_name="claims",
    method_names=("list_claims", "list"),
)


@router.post("", status_code=501)
async def create_claim() -> dict[str, Any]:
    """Report a new claim.

    There is no claim persistence/service contract behind this endpoint yet,
    so we refuse to pretend the write succeeded. Clients should treat a ``501``
    as "not implemented" and NOT assume the claim was stored.
    """
    return {
        "status": "not_implemented",
        "detail": (
            "POST /api/claims is not implemented: no claim persistence/service "
            "contract exists. This endpoint returns 501 rather than a fake "
            "202 acceptance, so callers cannot assume the claim was recorded."
        ),
    }
