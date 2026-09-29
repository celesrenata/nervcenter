"""Events endpoints for the NerveCenter API."""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from backend.api.models import ListResponse, ApiResponseMeta
from datetime import datetime

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/", response_model=ListResponse)
async def list_events():
    """List all events."""
    events = [
        {"id": "evt-1", "type": "entity.created", "timestamp": datetime.utcnow().isoformat()},
        {"id": "evt-2", "type": "task.assigned", "timestamp": datetime.utcnow().isoformat()},
    ]
    return ListResponse(
        data=events,
        meta=ApiResponseMeta(
            version="1.0.0",
            request_id="req-123",
            timestamp=datetime.utcnow(),
            pagination={"total": len(events), "page": 1, "per_page": 10},
        ),
    )


@router.get("/{event_id}")
async def get_event(event_id: str):
    """Get event by ID."""
    if event_id not in ["evt-1", "evt-2"]:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"id": event_id, "type": "entity.created", "timestamp": datetime.utcnow().isoformat()}
