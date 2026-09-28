"""Parallel task execution for NerveCenter (spec Section 23).

The :class:`ParallelExecutor` dispatches runnable tasks concurrently while
respecting DAG dependencies. It uses a worker-pool pattern where each worker
runs tasks that are currently runnable and then re-evaluates the DAG to find
newly-released tasks.

Design notes
------------
- Workers pull from a shared :class:`~backend.tasks.dag.RunnableQueue`.
- After completing a task, the DAG is re-evaluated to uncover newly runnable
  tasks (their dependencies have just succeeded).
- The executor stops when there are no runnable tasks and no tasks currently
  in progress.

Spec sections
-------------
- NerveCenter specification Section 23 (Task DAG).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

import structlog

from backend.tasks.dag import RunnableQueue, TaskDAG, RunnableState

if TYPE_CHECKING:
    from schemas.tasks import Task

log = structlog.get_logger(__name__)

__all__ = ["ParallelExecutor", "ExecutionResult", "WorkerConfig"]


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result of executing a single task.

    Attributes
    ----------
    task_id:
        The task that was executed.
    success:
        ``True`` when the task completed without error.
    started_at:
        When execution began (UTC).
    finished_at:
        When execution ended (UTC).
    error:
        Error message if the task failed (``None`` on success).
    """

    task_id: str
    success: bool
    started_at: datetime
    finished_at: datetime
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "error": self.error,
        }


@dataclass(slots=True)
class WorkerConfig:
    """Configuration for the parallel executor.

    Attributes
    ----------
    max_workers:
        Maximum number of concurrent workers. Defaults to 4.
    task_timeout:
        Maximum seconds a task may run before being cancelled. ``None`` means
        no timeout.
    on_task_start:
        Optional callback invoked when a task begins execution.
    on_task_complete:
        Optional callback invoked after a task finishes.
    """

    max_workers: int = 4
    task_timeout: int | None = None
    on_task_start: Callable[[Task], None] | None = None
    on_task_complete: Callable[[Task, ExecutionResult], None] | None = None


class ParallelExecutor:
    """Execute tasks in parallel, respecting DAG dependencies.

    Usage::

        async def runner(task: Task) -> ExecutionResult:
            # Your task runner implementation
            ...

        executor = ParallelExecutor(runner, config)
        results = await executor.execute(dag, runnable_queue)

    The executor:
    1. Starts ``max_workers`` coroutines.
    2. Each worker pulls tasks from the queue.
    3. After completion, the DAG is re-evaluated to find newly runnable tasks.
    4. Workers terminate when no runnable tasks remain and no tasks are running.
    """

    def __init__(
        self,
        task_runner: Callable[[Task], asyncio.Task[ExecutionResult]],
        config: WorkerConfig | None = None,
    ) -> None:
        self._runner = task_runner
        self._config = config or WorkerConfig()
        self._queue = RunnableQueue()

    async def execute(
        self,
        dag: TaskDAG,
        runnable_queue: RunnableQueue | None = None,
    ) -> list[ExecutionResult]:
        """Execute all runnable tasks in parallel until the DAG is exhausted.

        Parameters
        ----------
        dag:
            The task DAG (updated in-place as tasks complete).
        runnable_queue:
            Optional pre-populated queue of runnable tasks. If ``None``, the
            queue is built from the current DAG state.

        Returns
        -------
        list[ExecutionResult]
            One result per task executed, in completion order.
        """
        if runnable_queue:
            self._queue = runnable_queue
        else:
            task_status_map = {t.id: t.status for t in dag.tasks()}
            runnable = dag.runnable_tasks(task_status_map)
            for t in runnable:
                self._queue.push(t)

        results: list[ExecutionResult] = []
        tasks_by_id: dict[str, asyncio.Task[None]] = {}

        # Re-evaluation state (shared across workers)
        task_status_map = {t.id: t.status for t in dag.tasks()}

        async def worker() -> None:
            while True:
                rt = self._queue.pop()
                if rt is None:
                    # No more tasks queued; if no tasks are running, exit
                    if not tasks_by_id:
                        return
                    await asyncio.sleep(0.05)
                    continue

                task = rt.task
                if self._config.on_task_start:
                    self._config.on_task_start(task)

                task_id = task.id
                log.info("tasks.executing", task_id=task_id, title=task.title)

                async def run_one(t: Task, tid: str) -> None:
                    try:
                        result_task = self._runner(t)
                        result = await asyncio.wait_for(result_task, timeout=self._config.task_timeout)
                        results.append(result)
                        tasks_by_id.pop(tid, None)

                        # Update DAG and re-evaluate runnable tasks
                        task_status_map[tid] = "completed" if result.success else "failed"
                        new_runnable = dag.runnable_tasks(task_status_map)
                        for tt in new_runnable:
                            if tt.id not in tasks_by_id:
                                self._queue.push(tt)

                        if self._config.on_task_complete:
                            self._config.on_task_complete(t, result)

                        log.info("tasks.completed", task_id=tid, success=result.success)
                    except asyncio.TimeoutError:
                        err_result = ExecutionResult(
                            task_id=tid,
                            success=False,
                            started_at=datetime.now(timezone.utc),
                            finished_at=datetime.now(timezone.utc),
                            error="timeout",
                        )
                        results.append(err_result)
                        tasks_by_id.pop(tid, None)
                        task_status_map[tid] = "failed"
                        if self._config.on_task_complete:
                            self._config.on_task_complete(t, err_result)
                        log.warning("tasks.timed_out", task_id=tid)
                    except Exception as exc:  # noqa: BLE001
                        err_result = ExecutionResult(
                            task_id=tid,
                            success=False,
                            started_at=datetime.now(timezone.utc),
                            finished_at=datetime.now(timezone.utc),
                            error=str(exc),
                        )
                        results.append(err_result)
                        tasks_by_id.pop(tid, None)
                        task_status_map[tid] = "failed"
                        if self._config.on_task_complete:
                            self._config.on_task_complete(t, err_result)
                        log.error("tasks.failed", task_id=tid, error=str(exc))

                tasks_by_id[task_id] = asyncio.create_task(run_one(task, task_id))

        workers = [asyncio.create_task(worker()) for _ in range(self._config.max_workers)]
        await asyncio.gather(*workers)

        return results

    async def execute_one(
        self,
        task: Task,
    ) -> ExecutionResult:
        """Execute a single task (for tests or manual dispatch)."""
        started = datetime.now(timezone.utc)
        try:
            result_task = self._runner(task)
            result = await asyncio.wait_for(result_task, timeout=self._config.task_timeout)
            return result
        except asyncio.TimeoutError:
            return ExecutionResult(
                task_id=task.id,
                success=False,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                error="timeout",
            )
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(
                task_id=task.id,
                success=False,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Default runner factory for integration with backend services
# ---------------------------------------------------------------------------


def make_default_runner() -> Callable[[Task], asyncio.Task[ExecutionResult]]:
    """Create a runner stub for testing or mock execution.

    The runner returns a successful result immediately without actually
    executing any work. Real implementations would dispatch to agent runtimes
    or external workers.
    """
    import asyncio

    async def runner(task: Task) -> ExecutionResult:
        await asyncio.sleep(0.01)  # Simulate minimal work
        return ExecutionResult(
            task_id=task.id,
            success=True,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            error=None,
        )

    # Create a task that wraps the coroutine
    def factory(task: Task) -> asyncio.Task[ExecutionResult]:
        return asyncio.create_task(runner(task))

    return factory
