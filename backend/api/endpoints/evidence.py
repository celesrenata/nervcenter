"""Evidence service endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from backend.api.models import ListResponse, ApiResponseMeta
from datetime import datetime

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/", response_model=ListResponse)
async def list_evidence():
    """List all evidence items."""
    # In a real implementation, this would query the database
    evidence = [
        {"id": "ev-1", "name": "Evidence 1", "type": "document"},
        {"id": "ev-2", "name": "Evidence 2", "type": "data"},
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
    """Get evidence details."""
    # In a real implementation, this would query the database
    if evidence_id not in ["ev-1", "ev-2"]:
        raise HTTPException(status_code=404, detail="Evidence not found")

    return {
        "id": evidence_id,
        "name": f"Evidence {evidence_id[-1]}",
        "type": "document" if evidence_id == "ev-1" else "data",
    }