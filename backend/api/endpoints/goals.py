"""Goal service endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from backend.api.models import ListResponse, ApiResponseMeta
from datetime import datetime

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("/", response_model=ListResponse)
async def list_goals():
    """List all goals."""
    # In a real implementation, this would query the database
    goals = [
        {"id": "goal-1", "name": "Goal 1", "status": "active"},
        {"id": "goal-2", "name": "Goal 2", "status": "completed"},
    ]

    return ListResponse(
        data=goals,
        meta=ApiResponseMeta(
            version="1.0.0",
            request_id="req-123",
            timestamp=datetime.utcnow(),
            pagination={"total": len(goals), "page": 1, "per_page": 10},
        ),
    )


@router.get("/{goal_id}")
async def get_goal(goal_id: str):
    """Get goal details."""
    # In a real implementation, this would query the database
    if goal_id not in ["goal-1", "goal-2"]:
        raise HTTPException(status_code=404, detail="Goal not found")

    return {
        "id": goal_id,
        "name": f"Goal {goal_id[-1]}",
        "status": "active" if goal_id == "goal-1" else "completed",
    }