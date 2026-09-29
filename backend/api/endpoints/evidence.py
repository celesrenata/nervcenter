"""Evidence endpoints for the NerveCenter API."""
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.api.models import ApiResponseMeta, ListResponse

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/", response_model=ListResponse)
async def list_evidence():
    """List all evidence records."""
    evidence = [
        {"id": "ev-1", "source_type": "web_page", "source_ref": "https://example.com"},
    ]
    return ListResponse(
        data=evidence,
        meta=ApiResponseMeta(
            version="1.0.0",
            request_id="req-123",
            timestamp=datetime.utcnow(),
            pagination={"total": len(evidence), "page": 1, "per_page": 10},
        ),
    )


@router.get("/{evidence_id}")
async def get_evidence(evidence_id: str):
    """Get evidence by ID."""
    if evidence_id != "ev-1":
        raise HTTPException(status_code=404, detail="Evidence not found")
    return {"id": evidence_id, "source_type": "web_page", "source_ref": "https://example.com"}
