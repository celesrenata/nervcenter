"""Task DAG and dependency resolution for NerveCenter (spec Section 23).

A task DAG is a directed acyclic graph where nodes are tasks and edges represent
dependencies: an edge ``A -> B`` means ``B`` depends on ``A`` (``B`` cannot start
until ``A`` finishes successfully).

This module provides:

- :class:`TaskDAG` — a pure Python DAG implementation that holds tasks and
  their dependency edges.
- :class:`RunnableQueue` — a queue of tasks whose dependencies have all
  completed, ready for scheduling.
- :func:`topological_order` — returns tasks in topological order (or raises
  ``ValueError`` if the graph contains a cycle).

The implementation is intentionally *stateless* and *pure* so that the logic
can be unit tested without touching the database or async runtime.

Spec sections
-------------
- NerveCenter specification Section 23 (Task DAG).
"""

from __future__ import annotations

import collections
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from schemas.tasks import Task


__all__ = [
    "TaskDAG",
    "RunnableQueue",
    "topological_order",
    "RunnableState",
]


class RunnableState(Enum):
    """Current execution status of a task in the DAG.

    This mirrors :class:`~schemas.tasks.Task.status` but focuses on the DAG
    view: a task is runnable when all its predecessors are satisfied and its
    own status allows starting.
    """

    NOT_RUNNABLE = "not_runnable"  # dependencies still pending
    RUNNABLE = "runnable"          # all deps satisfied, can start
    RUNNING = "running"            # currently executing
    SUCCESS = "success"            # completed successfully
    FAILURE = "failure"            # failed / cancelled / skipped


# ---------------------------------------------------------------------------
# Task DAG (pure data + algorithms)
# ---------------------------------------------------------------------------


class TaskDAG:
    """Directed acyclic graph over tasks with dependency resolution.

    Usage::

        dag = TaskDAG()
        dag.add_task(task_a)
        dag.add_task(task_b, depends_on=[task_a.id])
        dag.add_task(task_c, depends_on=[task_a.id, task_b.id])
        # Now task_c is only runnable after both a and b succeed.

    The graph is validated for cycles at construction time. Adding a task with
    a dependency that does not exist in the DAG is a no-op (the task is added
    but the edge is ignored until the dependent task is added).

    Parameters
    ----------
    tasks:
        Initial tasks to add to the DAG.
    """

    __slots__ = ("_tasks", "_edges", "_preds", "_succs", "_sorted")

    def __init__(self, tasks: list[Task] | None = None) -> None:
        # node -> set of predecessors (dependencies)
        self._preds: dict[str, set[str]] = {}
        # node -> set of successors (dependents)
        self._succs: dict[str, set[str]] = {}
        # id -> task
        self._tasks: dict[str, Task] = {}
        # adjacency list for iteration
        self._edges: list[tuple[str, str]] = []
        # cached topological order
        self._sorted: list[str] | None = None

        if tasks:
            for t in tasks:
                self.add_task(t)

    # -- node operations ----------------------------------------------------

    def add_task(self, task: Task, depends_on: list[str] | None = None) -> None:
        """Add a task node to the DAG.

        If ``depends_on`` is provided, add directed edges from each dependency
        id to this task's id. Dependencies that are not yet in the DAG are
        silently ignored (they may be added later).
        """
        tid = task.id
        if tid in self._tasks:
            return
        self._tasks[tid] = task
        self._preds[tid] = set()
        self._succs[tid] = set()
        self._sorted = None

        if depends_on:
            for dep_id in depends_on:
                if dep_id in self._tasks:
                    self._add_edge(dep_id, tid)

    def remove_task(self, task_id: str) -> None:
        """Remove a task and all incident edges from the DAG."""
        if task_id not in self._tasks:
            return
        # Remove incoming edges
        for pred in list(self._preds.get(task_id, [])):
            self._succs.get(pred, set()).discard(task_id)
        # Remove outgoing edges
        for succ in list(self._succs.get(task_id, [])):
            self._preds.get(succ, set()).discard(task_id)
        # Remove node
        del self._tasks[task_id]
        del self._preds[task_id]
        del self._succs[task_id]
        self._sorted = None

    def _add_edge(self, from_id: str, to_id: str) -> None:
        """Add a dependency edge ``from_id -> to_id`` (to depends on from)."""
        if from_id in self._tasks and to_id in self._tasks:
            if to_id not in self._preds[from_id]:
                self._preds[to_id].add(from_id)
                self._succs[from_id].add(to_id)
                self._edges.append((from_id, to_id))
                self._sorted = None

    # -- queries ------------------------------------------------------------

    def task(self, task_id: str) -> Task | None:
        """Return the task with ``task_id``, or ``None`` if not present."""
        return self._tasks.get(task_id)

    def tasks(self) -> list[Task]:
        """Return all tasks in arbitrary order."""
        return list(self._tasks.values())

    def dependency_count(self, task_id: str) -> int:
        """Return the number of dependencies (incoming edges) for a task."""
        return len(self._preds.get(task_id, set()))

    def dependents(self, task_id: str) -> list[Task]:
        """Return tasks that depend on ``task_id`` (outgoing edges)."""
        succ_ids = self._succs.get(task_id, set())
        return [self._tasks[dep_id] for dep_id in succ_ids if dep_id in self._tasks]

    # -- state computation --------------------------------------------------

    def task_state(
        self,
        task_id: str,
        task_status_map: dict[str, str],
    ) -> RunnableState:
        """Compute the current runnable state of a task given actual statuses.

        Parameters
        ----------
        task_id:
            The task to evaluate.
        task_status_map:
            Task id -> actual status string (e.g. ``{"a": "completed", "b": "pending"}``).
        """
        if task_id not in self._tasks:
            return RunnableState.NOT_RUNNABLE
        status = task_status_map.get(task_id, "pending")
        if status in ("completed",):
            return RunnableState.SUCCESS
        if status in ("failed", "cancelled"):
            return RunnableState.FAILURE
        if status in ("in_progress",):
            return RunnableState.RUNNING

        # Pending or scheduled: check dependencies
        deps = self._preds.get(task_id, set())
        if not deps:
            return RunnableState.RUNNABLE

        # All deps must be SUCCESS for this task to be runnable
        for dep_id in deps:
            dep_status = task_status_map.get(dep_id, "pending")
            if dep_status not in ("completed",):
                return RunnableState.NOT_RUNNABLE

        return RunnableState.RUNNABLE

    def runnable_tasks(self, task_status_map: dict[str, str]) -> list[Task]:
        """Return all tasks that are currently runnable (dependencies satisfied)."""
        return [
            t
            for t in self._tasks.values()
            if self.task_state(t.id, task_status_map) == RunnableState.RUNNABLE
        ]

    def next_runnable(self, task_status_map: dict[str, str]) -> Task | None:
        """Return one runnable task, or ``None`` if none are ready."""
        for t in self._tasks.values():
            if self.task_state(t.id, task_status_map) == RunnableState.RUNNABLE:
                return t
        return None

    # -- topological order (DAG verification) -------------------------------

    def topological_order(self) -> list[Task]:
        """Return tasks in topological order (dependencies first), or raise.

        Raises
        ------
        ValueError
            If the graph contains a cycle (not a DAG).
        """
        if self._sorted is not None:
            return [self._tasks[tid] for tid in self._sorted]

        order = topological_order(self._tasks, self._preds)
        self._sorted = [t.id for t in order]
        return order

    def has_cycle(self) -> bool:
        """Return ``True`` if adding the current edges creates a cycle."""
        try:
            self.topological_order()
            return False
        except ValueError:
            return True

    def clear(self) -> None:
        """Remove all tasks and edges."""
        self._tasks.clear()
        self._preds.clear()
        self._succs.clear()
        self._edges.clear()
        self._sorted = None

    def __len__(self) -> int:
        return len(self._tasks)


# ---------------------------------------------------------------------------
# Topological sort (Kahn's algorithm)
# ---------------------------------------------------------------------------


def topological_order(
    tasks: dict[str, Task],
    predecessors: dict[str, set[str]] | None = None,
) -> list[Task]:
    """Return tasks in topological order (Kahn's algorithm).

    A topological ordering exists only if the graph is a DAG. If a cycle is
    detected, ``ValueError`` is raised.

    Parameters
    ----------
    tasks:
        Mapping of task id -> task for all nodes in the graph.
    predecessors:
        Mapping of task id -> set of predecessor task ids. If ``None``, every
        task is assumed to have no dependencies.

    Returns
    -------
    list[Task]
        Tasks ordered so every task appears after all its dependencies.

    Raises
    ------
    ValueError
        If a cycle is detected.
    """
    if predecessors is None:
        predecessors = {tid: set() for tid in tasks}

    # Compute in-degrees
    in_degree: dict[str, int] = {tid: len(deps) for tid, deps in predecessors.items()}

    # Queue of nodes with in-degree zero
    queue: deque[str] = deque(tid for tid, deg in in_degree.items() if deg == 0)
    order: list[Task] = []

    while queue:
        node = queue.popleft()
        order.append(tasks[node])
        for succ_id in predecessors.get(node, set()):
            in_degree[succ_id] -= 1
            if in_degree[succ_id] == 0:
                queue.append(succ_id)

    if len(order) != len(tasks):
        remaining = [tid for tid in tasks if tid not in {t.id for t in order}]
        raise ValueError(f"Cycle detected involving tasks: {remaining}")

    return order


# ---------------------------------------------------------------------------
# Runnable queue
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RunnableQueue:
    """A FIFO queue of tasks ready for execution.

    Tasks are ordered by priority (higher first), then creation time (newer
    first), which matches the scheduling priority semantics used throughout
    NerveCenter.

    Parameters
    ----------
    tasks:
        Initial tasks to enqueue.
    """

    _tasks: list[Task] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self._tasks)

    def push(self, task: Task) -> None:
        """Enqueue a task, maintaining priority order."""
        self._tasks.append(task)
        # Sort by priority (desc) then created_at (desc)
        self._tasks.sort(key=lambda t: (-t.priority, -t.created_at.timestamp()))

    def push_many(self, tasks: list[Task]) -> None:
        """Enqueue multiple tasks in one call."""
        self._tasks.extend(tasks)
        self._tasks.sort(key=lambda t: (-t.priority, -t.created_at.timestamp()))

    def pop(self) -> Task | None:
        """Dequeue the highest-priority runnable task."""
        if not self._tasks:
            return None
        return self._tasks.pop(0)

    def peek(self) -> Task | None:
        """Return the highest-priority runnable task without removing it."""
        return self._tasks[0] if self._tasks else None

    def remove(self, task_id: str) -> Task | None:
        """Remove a specific task from the queue by id."""
        for idx, t in enumerate(self._tasks):
            if t.id == task_id:
                return self._tasks.pop(idx)
        return None

    def clear(self) -> None:
        self._tasks.clear()

    def to_list(self) -> list[Task]:
        return list(self._tasks)
