"""Briefing endpoints (prompt2 §30 — Briefings).

Contract:
- ``GET /api/briefing``  → one composed briefing; query ``?kind=
                          morning|midday|evening`` (default ``morning``).

A read-only, deterministic aggregation across the personal-operations planes
(attention, waiting-on, calendar, email, messages, voicemail). The store is
the process-wide :func:`backend.briefing.get_briefing_service` singleton
(bound onto ``app.state.briefing_service`` at startup). It is *always*
available — an empty store returns an ``empty: true`` brief. There is no
ingest, no write, and no ``now`` query param: the clock is pinned by the
compose call (defaults to the wall clock) so the four §30 sections render
exactly and the screen shows the honest closing line when nothing needs
attention.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from backend.api.models import Briefing, BriefingKind
from backend.briefing.service import BriefingService, get_briefing_service

router = APIRouter(prefix="/api/briefing", tags=["briefing"])


def _service(request: Request) -> BriefingService:
    svc = getattr(request.app.state, "briefing_service", None)
    if svc is None:
        # Defensive: the singleton is always resolvable even if startup wiring
        # has not run yet (e.g. unit tests hitting the router directly).
        svc = get_briefing_service()
        request.app.state.briefing_service = svc
    return svc


# -- routes -----------------------------------------------------------------
@router.get("", response_model=Briefing)
@router.get("/", response_model=Briefing)
async def get_briefing(
    request: Request,
    kind: str = Query(
        default="morning",
        description=(
            "Which slot of the day to render: 'morning' (the full daily "
            "brief, §30 example) | 'midday' | 'evening'. The four sections are "
            "identical for all three; the kind is echoed back as metadata."
        ),
    ),
) -> Briefing:
    """Compose one briefing from the live plane state (§30)."""
    kind_key = (kind or "").strip() or BriefingKind.MORNING.value
    try:
        kind_enum = BriefingKind(kind_key)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid kind '{kind}'. Use morning|midday|evening.",
        )
    svc = _service(request)
    return svc.compose(kind=kind_enum)
