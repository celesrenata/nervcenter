"""Evidence endpoints for the NerveCenter API.

Wired to the real :class:`backend.evidence.service.EvidenceService` through
``app.state.services`` (same pattern as the other service-backed routers —
see :mod:`backend.api.endpoints._helpers`).  When the service is not
configured (local dev without PostgreSQL) the list endpoint returns an empty
collection, mirroring the honest-degradation behaviour of the events API.

Contract (spec Section 46 + MCP ``report_artifact`` proxy):
- ``GET  /api/evidence``           → list all evidence records (capture index)
- ``POST /api/evidence``           → capture a new evidence record
- ``GET  /api/evidence/{id}``      → provenance lookup by stable id
- ``GET  /api/evidence/{id}/verify`` → recompute the content digest and compare
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request

from backend.api.models import ApiResponseMeta, ListResponse
from schemas.evidence import EvidenceCaptureRequest

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


def _meta(**pagination: int | None) -> ApiResponseMeta:
    return ApiResponseMeta(
        version="1.0.0",
        request_id=f"req-{uuid4().hex[:12]}",
        timestamp=datetime.now(UTC),
        pagination={k: v for k, v in pagination.items() if v is not None} or None,
    )


def _service(request: Request):
    services = getattr(request.app.state, "services", {})
    service = services.get("evidence") if isinstance(services, dict) else None
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Evidence service not configured (NERVE_DB_URL unset).",
        )
    return service


@router.get("/", response_model=ListResponse)
async def list_evidence(
    request: Request,
    limit: int = 100,
    offset: int = 0,
) -> ListResponse:
    """List all evidence records, newest capture first.

    Returns an empty collection when no evidence service is configured
    (local dev without PostgreSQL) — honest degradation, no fabricated
    records.
    """
    services = getattr(request.app.state, "services", {})
    service = services.get("evidence") if isinstance(services, dict) else None
    if service is None:
        return ListResponse(data=[], meta=_meta(total=0, page=1, per_page=limit))
    rows = await service.list_evidence(limit=limit, offset=offset)
    data = [row.model_dump(mode="json") for row in rows]
    return ListResponse(
        data=data,
        meta=_meta(total=len(data), page=offset // max(limit, 1) + 1, per_page=limit),
    )


@router.post("/", status_code=202)
async def create_evidence(
    request: Request, payload: EvidenceCaptureRequest
) -> dict[str, Any]:
    """Capture a new evidence record (spec Section 15).

    Stores the captured content together with its SHA-256 digest and the
    capture timestamp; the record is immutable after capture.
    """
    service = _service(request)
    record = await service.create(
        source_type=payload.source_type,
        source_ref=payload.source_ref,
        content=payload.content,
        captured_at=payload.captured_at,
        trust=payload.trust,
        metadata=payload.metadata,
        redacted=payload.redacted,
        content_hash=payload.content_hash,
    )
    return record.model_dump(mode="json")


@router.get("/{evidence_id}")
async def get_evidence(request: Request, evidence_id: str) -> dict[str, Any]:
    """Get a single evidence record (provenance lookup) by stable id."""
    service = _service(request)
    record = await service.get(evidence_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return record.model_dump(mode="json")


@router.delete("/{evidence_id}", status_code=204)
async def delete_evidence(request: Request, evidence_id: str) -> None:
    """Delete an evidence record by stable id."""
    service = _service(request)
    deleted = await service.delete(evidence_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return None


@router.get("/{evidence_id}/verify")
async def verify_evidence(
    request: Request,
    evidence_id: str,
    expected_hash: str = Query(
        default="",
        description=(
            "Expected SHA-256 digest; when omitted, the stored content_hash "
            "is used as the expected value."
        ),
    ),
) -> dict[str, Any]:
    """Verify evidence integrity by recomputing the stored content digest."""
    service = _service(request)
    record = await service.get(evidence_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    expected = expected_hash or (record.content_hash or "")
    if not expected:
        raise HTTPException(
            status_code=422,
            detail="No content hash available to verify against",
        )
    ok = await service.verify_content(evidence_id, expected)
    return {
        "evidence_id": record.id,
        "stored_content_hash": record.content_hash,
        "expected_hash": expected,
        "match": ok,
    }
