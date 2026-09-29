"""Task service endpoints."""
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.api.models import ApiResponseMeta, ListResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=ListResponse)
async def list_tasks():
    """List all tasks."""
    # In a real implementation, this would query the database
    tasks = [
        {"id": "task-1", "name": "Task 1", "status": "pending"},
        {"id": "task-2", "name": "Task 2", "status": "completed"},
    ]

    return ListResponse(
        data=tasks,
        meta=ApiResponseMeta(
            version="1.0.0",
            request_id="req-123",
            timestamp=datetime.utcnow(),
            pagination={"total": len(tasks), "page": 1, "per_page": 10},
        ),
    )


@router.get("/{task_id}")
async def get_task(task_id: str):
    """Get task details."""
    # In a real implementation, this would query the database
    if task_id not in ["task-1", "task-2"]:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task_id,
        "name": f"Task {task_id[-1]}",
        "status": "pending" if task_id == "task-1" else "completed",
    }
