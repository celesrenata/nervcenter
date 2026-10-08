"""Overview aggregate endpoint — returns consolidated overview data.

This endpoint is a **stub** — it returns 501 Not Implemented until the
underlying services (goals, tasks, incidents, compute, agents) are connected
to the API via `app.state.services` configuration.

The web Overview view expects 10 fields per spec §49. This endpoint synthesizes
them from multiple backend services when available.

Contract (web/src/api/client.ts getOverview):
```json
{
  "health": { "status": "healthy", "uptime": "14d 3h 22m", "version": "0.4.1", "lastCheck": "2026-09-28T23:55:00Z" },
  "incidents": [{ "id": "inc-001", "title": "...", "severity": "high", "status": "active", "createdAt": "...", "impact": "..." }],
  "goals": [{ "id": "goal-001", "title": "...", "status": "ACTIVE", "progress": 72, "dueDate": "2026-10-15" }],
  "runningAgents": [{ "id": "...", "name": "...", "status": "running", "task": "..." }],
  "taskConcurrency": { "total": 8, "running": 2, "ready": 2, "pending": 1, "blocked": 1, "verifying": 1, "succeeded": 1, "failed": 0 },
  "computeUtilization": { "totalNodes": 3, "totalGpus": 4, "usedGpus": 2, "gpuUtilization": 50, "gpuAllocated": 50, "pendingGpus": 2, "pendingAllocated": 50 },
  "pendingApprovals": [{ "id": "...", "type": "...", "description": "...", "requestedAt": "..." }],
  "pendingIncidents": [{ "id": "...", "title": "...", "severity": "..." }],
  "activeGoals": [{ "id": "...", "title": "...", "progress": 0 }]
}
```
"""
from datetime import UTC, datetime
from fastapi import APIRouter, HTTPException
from backend.api.models import ApiResponseMeta, ListResponse

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("/", response_model=dict)
async def get_overview():
    """Return consolidated Overview view data.

    Returns a 501 response until services are wired via `app.state.services`.
    The Overview view needs 10 data fields per spec §49.
    """
    raise HTTPException(
        status_code=501,
        detail="Overview endpoint requires service wiring (app.state.services). "
               "Connect goals, tasks, incidents, and compute services to enable this endpoint."
    )
