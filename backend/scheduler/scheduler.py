"""DAG-based scheduler for NerveCenter (spec Section 23).

The :class:`DAGScheduler` coordinates the intersection of three domains:

1. **Goal state** — Which goals are active and ready for scheduling.
2. **Task DAG** — The dependency graph of tasks (which tasks depend on which).
3. **Task state** — The current status of each task (pending, in_progress, etc.).

Given this context, the scheduler produces a :class:`SchedulingPlan` that
identifies which tasks are currently runnable (all dependencies satisfied) and
should be dispatched for execution.

The scheduler is pure and stateless: it never modifies the database directly.
Instead, it reads goal/task state, builds the DAG, and returns a plan that
the caller (a worker) executes.

Spec sections
-------------
- NerveCenter specification Section 23 (Task DAG).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from backend.tasks.dag import RunnableQueue, TaskDAG, RunnableState, topological_order

if TYPE_CHECKING:
    from schemas.goals import Goal
    from schemas.tasks import Task

log = structlog.get_logger(__name__)

__all__ = [
    "DAGScheduler",
    "SchedulingPlan",
    "RunnableTask",
]


@dataclass(frozen=True, slots=True)
class RunnableTask:
    """A task ready for execution, ordered by priority and dependencies.

    Attributes
    ----------
    task:
        The task record (pydantic schema).
    priority:
        The task's scheduling priority (higher = more urgent).
    created_at:
        When the task was created (used for tie-breaking).
    """

    task: Task
    priority: int = field(default=0)
    created_at: float = field(default=0.0)

    def __lt__(self, other: "RunnableTask") -> bool:
        # Higher priority first, then newer task first
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.created_at > other.created_at


@dataclass(frozen=True, slots=True)
class SchedulingPlan:
    """A plan produced by :class:`DAGScheduler` with runnable tasks.

    Attributes
    ----------
    goals:
        Active goals considered for scheduling.
    dag:
        The task DAG built from the goals' tasks.
    runnable:
        Tasks whose dependencies have all been satisfied.
    blocked:
        Tasks still waiting on dependencies (id -> set of unfinished deps).
    stats:
        Simple summary counts for observability.
    """

    goals: list[Goal]
    dag: TaskDAG
    runnable: list[RunnableTask]
    blocked: dict[str, set[str]]
    stats: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "runnable_count": len(self.runnable),
            "blocked_count": len(self.blocked),
            "total_tasks": len(self.dag),
            "stats": self.stats,
        }


class DAGScheduler:
    """Scheduler that identifies runnable tasks from a DAG of goal-associated tasks.

    The scheduler operates in three phases:

    1. **Load** — Fetch all active goals and their tasks.
    2. **Build DAG** — Construct the dependency graph from task dependencies.
    3. **Identify runnable** — Walk the DAG and mark tasks whose predecessors
       are all ``completed`` as runnable.

    Usage::

        scheduler = DAGScheduler(goal_service, task_service)
        plan = await scheduler.build_plan()
        for rt in plan.runnable:
            await worker.dispatch(rt.task)
    """

    def __init__(
        self,
        goal_service: "GoalServiceProtocol",
        task_service: "TaskServiceProtocol",
    ) -> None:
        self._goals = goal_service
        self._tasks = task_service

    async def build_plan(self) -> SchedulingPlan:
        """Build a complete scheduling plan from active goals.

        Returns
        -------
        SchedulingPlan
            With runnable tasks, blocked tasks, and statistics.
        """
        goals = await self._goals.active_goals()
        if not goals:
            return SchedulingPlan(goals=[], dag=TaskDAG(), runnable=[], blocked={}, stats={})

        # Load all tasks belonging to active goals
        all_tasks: list[Task] = []
        for goal in goals:
            goal_tasks = await self._tasks.list_for_goal(goal.id)
            all_tasks.extend(goal_tasks)

        # Build the DAG from tasks (dependencies are stored in Task.dependencies)
        dag = TaskDAG(all_tasks)
        for task in all_tasks:
            if task.dependencies:
                dag.add_task(task, depends_on=task.dependencies)

        # Build status map from actual task records
        task_status_map: dict[str, str] = {t.id: t.status for t in all_tasks}

        # Identify runnable vs blocked tasks
        runnable: list[RunnableTask] = []
        blocked: dict[str, set[str]] = {}
        stats: dict[str, int] = {
            "pending": 0,
            "scheduled": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }

        for task in all_tasks:
            status = task.status
            stats[status] = stats.get(status, 0) + 1

            rstate = dag.task_state(task.id, task_status_map)
            if rstate == RunnableState.RUNNABLE:
                runnable.append(RunnableTask(task=task, priority=task.priority, created_at=task.created_at.timestamp()))
            elif rstate == RunnableState.NOT_RUNNABLE:
                # Collect which deps are still blocking
                preds = dag._preds.get(task.id, set())
                unfinished = {p for p in preds if task_status_map.get(p, "pending") not in ("completed",)}
                if unfinished:
                    blocked[task.id] = unfinished

        # Sort runnable tasks by priority/created_at
        runnable.sort()

        log.info(
            "scheduler.plan_built",
            goals=len(goals),
            tasks=len(all_tasks),
            runnable=len(runnable),
            blocked=len(blocked),
        )
        return SchedulingPlan(
            goals=goals,
            dag=dag,
            runnable=runnable,
            blocked=blocked,
            stats=stats,
        )


# ---------------------------------------------------------------------------
# Protocol (structural) so the scheduler does not force an import cycle
# ---------------------------------------------------------------------------


class GoalServiceProtocol:
    """Structural protocol for the goal service consumed by the scheduler."""

    async def active_goals(self) -> list["Goal"]:  # noqa: D400
        ...


class TaskServiceProtocol:
    """Structural protocol for the task service consumed by the scheduler."""

    async def list_for_goal(self, goal_id: str) -> list["Task"]:  # noqa: D400
        ...
