"""Overview aggregate endpoint — returns consolidated overview data.

``GET /api/overview`` synthesizes the §49 Overview contract from *real*
backend data instead of hardcoded fixtures:

- ``tasks`` — real per-status counts from
  :class:`~backend.tasks.service.TaskService.count_by_status`.
- ``goals`` — real goal rows from
  :class:`~backend.goals.service.GoalService.list_goals` (plus the
  ``activeGoals`` subset).
- ``agents`` — the *same* merged roster ``GET /api/agents`` returns: the 14
  native agent types from the in-memory ``AgentRegistry`` first, then any
  persisted agent instances (created via ``POST /api/agents``). ``counts.agents``
  therefore always equals the ``/api/agents`` total (see :mod:`agents`).
- ``incidents`` / ``pendingIncidents`` — empty (no persistence-backed incident
  service exists; reported as a blocker, never fabricated).

Honesty contract
----------------
- DB-backed services present (``app.state.services`` has ``tasks`` and
  ``goals``) → HTTP 200 with the real aggregate.
- Genuinely unwired (no DB engine, so those services are absent) → the
  precise 501 below, so the frontend banner stays truthful instead of
  rendering zeros that look like "everything is fine".

Fields with no backing store (``computeUtilization``, ``pendingApprovals``,
per-agent telemetry) are returned as honest zeros/empty lists, not invented.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request

from backend.api.docs import get_version_info
from backend.api.endpoints.agents import list_agents as _list_agents

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/overview", tags=["overview"])

# Process start ≈ when this module first loaded; used to report a real
# ``uptime`` on the ``health`` field rather than a fabricated duration.
_PROCESS_START = datetime.now(UTC)

_UNWIRED_DETAIL = (
    "Overview endpoint requires service wiring (app.state.services). "
    "Connect goals, tasks, incidents, and compute services to enable this endpoint."
)


def _iso(value: Any) -> Any:
    """Normalize a datetime (or ISO string) to an ISO-8601 string passthrough."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _uptime() -> str:
    delta = datetime.now(UTC) - _PROCESS_START
    total = int(delta.total_seconds())
    days, rem = divmod(total, 86_400)
    hours, rem = divmod(rem, 3_600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


async def _goal_rows(goals_service: Any) -> list[dict[str, Any]]:
    """Map real goal records to the §49 shape; ``[]`` when the call fails."""
    try:
        goals = await goals_service.list_goals(limit=100)
    except Exception as exc:  # noqa: BLE001 - one bad probe must not sink the page
        log.warning("overview.goals_failed", error=str(exc))
        return []
    rows = []
    for g in goals:
        data = g.model_dump(mode="json") if hasattr(g, "model_dump") else dict(g)
        progress = data.get("progress")
        rows.append(
            {
                "id": data.get("id"),
                "title": data.get("title"),
                "status": data.get("status"),
                "progress": int(round(progress * 100)) if isinstance(progress, (int, float)) else 0,
                "dueDate": _iso(data.get("deadline")),
            }
        )
    return rows


async def get_overview(request: Request):
    """Return the consolidated Overview view data.

    200 with real data when the DB-backed services are wired; the precise 501
    when they are genuinely unwired (see module docstring).
    """
    services = getattr(request.app.state, "services", {}) or {}
    services = services if isinstance(services, dict) else {}
    goals_service = services.get("goals")
    tasks_service = services.get("tasks")
    if goals_service is None or tasks_service is None:
        raise HTTPException(status_code=501, detail=_UNWIRED_DETAIL)

    # Real per-status task counts.
    try:
        task_counts = await tasks_service.count_by_status()
    except Exception as exc:  # noqa: BLE001
        log.warning("overview.tasks_failed", error=str(exc))
        task_counts = {}

    task_concurrency = {
        "total": int(sum(task_counts.values()) or 0),
        "running": int(task_counts.get("in_progress", 0) or 0),
        "ready": int(task_counts.get("scheduled", 0) or 0),
        "pending": int(task_counts.get("pending", 0) or 0),
        "completed": int(task_counts.get("completed", 0) or 0),
        "failed": int(task_counts.get("failed", 0) or 0),
        "cancelled": int(task_counts.get("cancelled", 0) or 0),
    }

    goal_rows = await _goal_rows(goals_service)
    active_goals = [
        {"id": g["id"], "title": g["title"], "progress": g["progress"]}
        for g in goal_rows
        if (g.get("status") or "").lower() == "active"
    ]

    # Real agent roster — the *same* merged list ``GET /api/agents`` returns
    # (14 native registry types first, then persisted instances when an agent
    # service is wired). ``counts.agents`` is therefore always equal to the
    # ``/api/agents`` total; reusing :func:`_list_agents` keeps the two
    # endpoints in lockstep (N-4) instead of drift when persisted instances
    # exist (14 native + N instances).
    agent_rows = (await _list_agents(request)).data
    agents = [
        {
            "id": a.get("id"),
            "name": a.get("name"),
            "status": a.get("status"),
            "task": a.get("currentTask") or a.get("task"),
        }
        for a in agent_rows
    ]

    version_info = get_version_info()

    return {
        "health": {
            "status": "healthy",
            "uptime": _uptime(),
            "version": version_info.get("version"),
            "lastCheck": datetime.now(UTC).isoformat(),
        },
        "counts": {
            "tasks": task_concurrency["total"],
            "goals": len(goal_rows),
            "activeGoals": len(active_goals),
            "agents": len(agents),
            # No persistence-backed incident service exists yet.
            "incidents": 0,
        },
        "taskConcurrency": task_concurrency,
        "goals": goal_rows,
        "activeGoals": active_goals,
        "runningAgents": agents,
        # No backing stores exist for these yet — honest zeros, not fabricated.
        "incidents": [],
        "pendingIncidents": [],
        "pendingApprovals": [],
        "computeUtilization": {
            "totalNodes": 0,
            "totalGpus": 0,
            "usedGpus": 0,
            "gpuUtilization": 0,
            "gpuAllocated": 0,
            "pendingGpus": 0,
            "pendingAllocated": 0,
        },
    }
