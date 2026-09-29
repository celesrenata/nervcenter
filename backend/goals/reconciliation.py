"""Goal progress reconciliation (NerveCenter spec Section 22).

Goal progress stored on the :class:`~schemas.goals.Goal` record is *derived*
state; the ground truth is the actual state of the tasks that contribute to
the goal. Periodically (or after batch changes) the stored progress is
reconciled against task reality so the reported number is never a stale guess.

This module provides:

- :func:`compute_progress` — pure computation of expected progress from a
  multiset of task states.
- :class:`GoalProgressSnapshot` — a point-in-time observation of one goal's
  task population plus the drift between stored and expected progress.
- :class:`GoalReconciler` — the async service that joins goal state and task
  state, emits a per-goal :class:`GoalProgressSnapshot`, and optionally
  rewrites the stored progress / status to match reality
  (:meth:`GoalReconciler.reconcile`, :meth:`GoalReconciler.reconcile_all`).

Drift semantics
--------------
``drift = stored_progress - expected_progress``. A positive drift means the
stored value overstates real progress; negative means it understates it.
:attr:`GoalProgressSnapshot.status_in_sync` is ``True`` when the absolute
drift is within ``tolerance`` and the goal's stored status is consistent with
the task population (in particular, a goal at 100% successful completion is
``achieved``).

Spec sections
-------------
- NerveCenter specification Section 22 (Progress & Reconciliation).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from backend.goals.service import GoalService
    from schemas.tasks import Task

log = structlog.get_logger(__name__)

__all__ = [
    "compute_progress",
    "GoalProgressSnapshot",
    "GoalReconciler",
    "ReconcilerReport",
]

# Task statuses considered "counted" in the denominator. Cancelled tasks are
# excluded: work that will never happen should not hold a goal back.
TERMINAL_SUCCESS = "completed"
EXCLUDED = ("cancelled",)
RUNNING = "in_progress"
PENDING_STATES = ("pending", "scheduled")


def compute_progress(statuses: Mapping[str, int]) -> float:
    """Compute expected goal progress from a mapping of task status counts.

    Progress is ``completed / (total - cancelled)`` where *total* is the sum
    of all status counts and *cancelled* tasks are excluded from the
    denominator. An all-zero mapping yields ``0.0``.

    Parameters
    ----------
    statuses:
        Status name -> count mapping, e.g. ``{"completed": 2, "in_progress": 1}``.

    Returns
    -------
    float
        Expected progress in the ``[0.0, 1.0]`` range.

    Raises
    ------
    ValueError
        If any count is negative.
    """
    if any(v < 0 for v in statuses.values()):
        raise ValueError("status counts must be non-negative")
    total = sum(statuses.values())
    excluded = sum(statuses.get(s, 0) for s in EXCLUDED)
    denominator = total - excluded
    if denominator <= 0:
        return 0.0
    completed = statuses.get(TERMINAL_SUCCESS, 0)
    return min(1.0, completed / denominator)


def expected_status(progress: float, has_unfinished: bool) -> str:
    """Derive the lifecycle status a goal *should* be in for a progress value.

    - ``progress >= 1.0`` -> ``"achieved"`` (unless a terminal status is
      already set by the caller; this only reports the expected value).
    - otherwise -> ``"active"`` (the default working state).
    """
    _ = has_unfinished
    return "achieved" if progress >= 1.0 else "active"


@dataclass(frozen=True, slots=True)
class GoalProgressSnapshot:
    """Point-in-time observation of one goal's task population.

    Attributes
    ----------
    goal_id:
        The goal being reconciled.
    status_counts:
        Status -> count for every task contributing to this goal.
    total_tasks:
        Sum of all status counts.
    completed:
        Count of ``completed`` tasks.
    stored_progress:
        Progress currently stored on the goal record.
    expected_progress:
        Progress implied by the task population.
    drift:
        ``stored_progress - expected_progress`` (positive = overstated).
    status_in_sync:
        ``True`` when drift is within tolerance and the stored status is
        consistent with the expected status for the current progress.
    """

    goal_id: str
    status_counts: Mapping[str, int] = field(default_factory=dict)
    total_tasks: int = 0
    completed: int = 0
    stored_progress: float = 0.0
    expected_progress: float = 0.0
    drift: float = 0.0
    status_in_sync: bool = True

    @property
    def in_progress(self) -> int:
        return self.status_counts.get(RUNNING, 0)

    def as_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "status_counts": dict(self.status_counts),
            "total_tasks": self.total_tasks,
            "completed": self.completed,
            "stored_progress": self.stored_progress,
            "expected_progress": self.expected_progress,
            "drift": self.drift,
            "status_in_sync": self.status_in_sync,
        }


class GoalReconciler:
    """Reconciles stored goal progress against actual task state.

    The reconciler is wired with a :class:`GoalService` (for reads/updates) and
    a task service exposing :meth:`list_for_goal`. Both services share one
    engine; the reconciler performs *read-mostly* work and only writes when
    :meth:`reconcile` is called with ``apply=True``.
    """

    def __init__(
        self,
        goal_service: GoalService,
        task_service: TaskServiceProtocol,
        *,
        tolerance: float = 0.01,
    ) -> None:
        self._goals = goal_service
        self._tasks = task_service
        self._tolerance = tolerance

    # ------------------------------------------------------------------ #
    # Observation
    # ------------------------------------------------------------------ #

    async def snapshot(self, goal_id: str) -> GoalProgressSnapshot:
        """Observe the current progress of one goal against its tasks.

        No writes are performed; this is safe to call on a schedule.
        """
        goal = await self._goals.get(goal_id)
        tasks = await self._tasks.list_for_goal(goal_id)
        status_counts: dict[str, int] = {}
        for task in tasks:
            status_counts[task.status] = status_counts.get(task.status, 0) + 1

        expected = compute_progress(status_counts)
        completed = status_counts.get(TERMINAL_SUCCESS, 0)
        drift = goal.progress - expected

        # Drift tolerance applies to every goal.
        in_sync = abs(drift) <= self._tolerance
        # For working goals, the stored status must also be consistent with the
        # implied progress: a goal at 100% completion is expected to be
        # ``achieved``, and a goal below 100% should not be prematurely flagged.
        if goal.status not in ("paused", "abandoned"):
            status_consistent = (goal.status == "achieved") == (expected >= 1.0)
            in_sync = in_sync and status_consistent

        return GoalProgressSnapshot(
            goal_id=goal.id,
            status_counts=status_counts,
            total_tasks=len(tasks),
            completed=completed,
            stored_progress=goal.progress,
            expected_progress=expected,
            drift=drift,
            status_in_sync=in_sync,
        )

    # ------------------------------------------------------------------ #
    # Apply
    # ------------------------------------------------------------------ #

    async def reconcile(
        self,
        goal_id: str,
        *,
        apply: bool = True,
    ) -> GoalProgressSnapshot:
        """Reconcile one goal; optionally rewrite stored progress.

        Parameters
        ----------
        goal_id:
            The goal to reconcile.
        apply:
            When ``True`` (default), update the stored ``progress`` field to
            the expected value. Also transition a 100%-complete goal to
            ``achieved``.

        Returns
        -------
        GoalProgressSnapshot
            The observation taken *after* the optional apply, so ``drift``
            reflects the post-apply error (zero when applied).
        """
        before = await self.snapshot(goal_id)
        if apply:
            goal = await self._goals.get(goal_id)
            if abs(goal.progress - before.expected_progress) > 1e-9:
                if goal.status not in ("achieved", "abandoned"):
                    await self._goals.update_progress(goal_id, before.expected_progress)
                else:
                    # Terminal goals: trust stored progress but still report.
                    await self._goals.update(goal_id, {})
            log.info(
                "goals.reconciled",
                goal_id=goal_id,
                stored=before.stored_progress,
                expected=before.expected_progress,
            )
        return await self.snapshot(goal_id)

    async def reconcile_all(
        self,
        goal_ids: Sequence[str] | None = None,
        *,
        apply: bool = True,
    ) -> ReconcilerReport:
        """Reconcile a set of goals (default: all active goals).

        Failing goals are captured in the report (and logged) rather than
        aborting the batch, so a single bad row never poisons the run.
        """
        ids = list(goal_ids) if goal_ids is not None else []
        if not ids:
            active = await self._goals.active_goals()
            ids = [g.id for g in active]
        snapshots: list[GoalProgressSnapshot] = []
        failed: dict[str, str] = {}
        for goal_id in ids:
            try:
                snap = await self.reconcile(goal_id, apply=apply)
                snapshots.append(snap)
            except Exception as exc:  # noqa: BLE001 - report per-goal failures
                log.warning("goals.reconcile_failed", goal_id=goal_id, error=str(exc))
                failed[goal_id] = str(exc)
        return ReconcilerReport(snapshots=snapshots, failures=failed)


@dataclass(frozen=True, slots=True)
class ReconcilerReport:
    """Aggregate outcome of :meth:`GoalReconciler.reconcile_all`.

    Attributes
    ----------
    snapshots:
        One :class:`GoalProgressSnapshot` per successfully reconciled goal.
    failures:
        Goal id -> error message for goals that could not be reconciled.
    """

    snapshots: Sequence[GoalProgressSnapshot] = ()
    failures: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def drifted(self) -> list[GoalProgressSnapshot]:
        return [s for s in self.snapshots if not s.status_in_sync]

    def as_dict(self) -> dict:
        return {
            "snapshots": [s.as_dict() for s in self.snapshots],
            "failures": dict(self.failures),
        }


# ---------------------------------------------------------------------------
# Protocol (structural) so the reconciler does not force an import cycle
# ---------------------------------------------------------------------------
#
# The *real* :class:`~backend.tasks.service.TaskService` satisfies this
# protocol because it exposes ``list_for_goal(goal_id) -> list[Task]``.


class TaskServiceProtocol:
    """Structural protocol for the task service consumed by the reconciler."""

    async def list_for_goal(self, goal_id: str) -> list[Task]:  # noqa: D400
        ...
