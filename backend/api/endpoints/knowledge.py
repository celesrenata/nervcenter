"""Knowledge service endpoints."""
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.api.models import ApiResponseMeta, ListResponse

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/", response_model=ListResponse)
async def list_knowledge():
    """List all knowledge items."""
    # In a real implementation, this would query the database
    knowledge = [
        {"id": "k-1", "name": "Knowledge 1", "type": "entity"},
        {"id": "k-2", "name": "Knowledge 2", "type": "relationship"},
    ]

    return ListResponse(
        data=knowledge,
        meta=ApiResponseMeta(
            version="1.0.0",
            request_id="req-123",
            timestamp=datetime.utcnow(),
            pagination={"total": len(knowledge), "page": 1, "per_page": 10},
        ),
    )


@router.get("/{knowledge_id}")
async def get_knowledge(knowledge_id: str):
    """Get knowledge details."""
    # In a real implementation, this would query the database
    if knowledge_id not in ["k-1", "k-2"]:
        raise HTTPException(status_code=404, detail="Knowledge not found")

    return {
        "id": knowledge_id,
        "name": f"Knowledge {knowledge_id[-1]}",
        "type": "entity" if knowledge_id == "k-1" else "relationship",
    }
