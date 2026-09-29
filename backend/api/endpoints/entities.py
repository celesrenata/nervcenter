"""Entities endpoints for the NerveCenter API."""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from backend.api.models import ListResponse, ApiResponseMeta
from datetime import datetime

router = APIRouter(prefix="/api/entities", tags=["entities"])


@router.get("/", response_model=ListResponse)
async def list_entities():
    """List all entities."""
    entities = [
        {"id": "ent-1", "type": "person", "name": "Ada Lovelace"},
        {"id": "ent-2", "type": "organization", "name": "NerveCenter"},
    ]
    return ListResponse(
        data=entities,
        meta=ApiResponseMeta(
            version="1.0.0",
            request_id="req-123",
            timestamp=datetime.utcnow(),
            pagination={"total": len(entities), "page": 1, "per_page": 10},
        ),
    )


@router.get("/{entity_id}")
async def get_entity(entity_id: str):
    """Get entity by ID."""
    if entity_id not in ["ent-1", "ent-2"]:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"id": entity_id, "type": "person", "name": "Ada Lovelace"}
