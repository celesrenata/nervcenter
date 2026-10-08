"""Parallel Utilization Ratio (PUR) for NerveCenter (spec Section 80).

This module implements the ``T-H37`` / ``D-H37`` uplift item: a **pure,
deterministic** parallel-utilization metric computed from task execution
timestamps (or explicit worker-count samples). It never touches the database,
the async runtime, or any service — it only consumes plain data and returns a
plain report, so it can be unit tested without side effects.

Formula
-------

Given ``N`` task executions, each with an interval ``[started_at, finished_at]``
(UTC timestamps), define the instantaneous concurrency ``c(t)`` as the number
of executions whose interval contains ``t``. From the concurrency trace:

```
peak_concurrent_tasks   = max over all event times of c(t)
mean_concurrent_tasks   = (integral of c(t) dt) / (wall span)
wall_time_seconds       = max(finished_at) - min(started_at)
compute_time_seconds    = sum of (finished_at - started_at) per task
```

Two ratios are exposed (spec Section 80, [`prompot.md:2667`](prompot.md:2667),
"Expose Parallel Utilization Ratio to detect fake parallelism"):

1. **``parallel_utilization_ratio``** (the PUR) = ``mean_concurrent_tasks /
   peak_concurrent_tasks`` — how consistently the observed peak parallelism
   was sustained across the whole run.
2. **``capacity_utilization_ratio``** = ``mean_concurrent_tasks /
   available_workers`` — how much of the configured worker capacity was
   actually used. This is the fake-parallelism detector: a run that claims
   ``W``-way parallelism but executes everything sequentially has ``c(t) == 1``
   throughout, so this ratio collapses toward ``1/W``.

The **critical-path ratio** = ``compute_time_seconds / wall_time_seconds``
complements the ratios: ``1.0`` means zero overlap (fully serialized),
``> 1.0`` means tasks overlapped.

Tie-breaking and edge cases
---------------------------

- **Equal timestamps**: a task *finish* is applied before a task *start* at
  the same instant (conservative rule). Two tasks that are serialized back to
  back (``A`` finishes exactly when ``B`` starts) are therefore **not**
  counted as overlapping. This avoids over-counting parallelism, which would
  defeat the purpose of detecting fake parallelism.
- **No tasks** (empty input): every count and ratio is ``0.0``; there is no
  special exception — the report is all zeros.
- **Zero denominator**: when the denominator of a ratio is zero (no peak, no
  wall span, or ``available_workers`` is ``0`` / ``None``), the ratio is
  ``0.0`` rather than raising ``ZeroDivisionError``.
- **Zero-duration tasks** (``started_at == finished_at``): still count toward
  ``task_count`` and their timestamps bound the wall span, but they emit no
  concurrency events, so they occupy no concurrency footprint (they are
  instantaneous).
- **Inverted intervals** (``finished_at < started_at``): raise
  :class:`ValueError` — this is malformed input, not a utilization state.
- **Naive datetimes**: treated as UTC (deterministic; never depends on the
  machine's local timezone). Aware datetimes keep their offset.
- **Failures count**: failed/cancelled executions still occupied a worker, so
  they are included in the concurrency trace (the ``success`` flag is carried
  in the report only as informational counts).
- **Over-subscription**: if ``mean_concurrent_tasks`` exceeds
  ``available_workers`` (more tasks ran than configured workers),
  ``capacity_utilization_ratio`` may exceed ``1.0``. It is deliberately *not*
  clamped so that over-subscription remains observable.

Second entry point
------------------

:func:`compute_from_concurrency_samples` accepts explicit
``(timestamp, running_count)`` samples (the "explicit completed/available
worker inputs" path). For that path the per-task compute time is unknown, so
``compute_time_seconds`` and ``critical_path_ratio`` are ``None``.

Spec sections
-------------
- NerveCenter specification Section 80 (Parallel Utilization Metrics).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Sequence

__all__ = [
    "TaskExecution",
    "ParallelUtilizationReport",
    "compute_parallel_utilization",
    "compute_from_concurrency_samples",
]


# ---------------------------------------------------------------------------
# Input records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TaskExecution:
    """One task execution interval.

    Attributes
    ----------
    task_id:
        Identifier of the executed task (informational).
    started_at:
        When execution began. Naive datetimes are treated as UTC.
    finished_at:
        When execution ended. Must be >= ``started_at``.
    success:
        Whether the task completed without error. Failed executions still
        occupied a worker slot, so they count toward concurrency.
    """

    task_id: str
    started_at: datetime
    finished_at: datetime
    success: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "success": self.success,
        }

    @staticmethod
    def from_execution_result(result: Any) -> TaskExecution:
        """Coerce a duck-typed execution result (e.g.
        :class:`~backend.scheduler.parallelism.ExecutionResult`) into a
        :class:`TaskExecution`.

        Any object exposing ``task_id``, ``started_at``, ``finished_at`` (and
        optionally ``success``) is accepted; missing ``success`` defaults to
        ``True``.
        """
        return TaskExecution(
            task_id=str(getattr(result, "task_id", "")),
            started_at=result.started_at,
            finished_at=result.finished_at,
            success=bool(getattr(result, "success", True)),
        )


@dataclass(frozen=True, slots=True)
class ParallelUtilizationReport:
    """Deterministic parallel-utilization report (spec Section 80).

    Attributes
    ----------
    task_count:
        Number of executions analyzed.
    failed_count:
        Number of executions with ``success=False``.
    peak_concurrent_tasks:
        Maximum observed instantaneous concurrency.
    mean_concurrent_tasks:
        Time-weighted average concurrency over the wall span.
    parallel_utilization_ratio:
        ``mean / peak`` — the PUR. ``0.0`` when the denominator is zero.
    capacity_utilization_ratio:
        ``mean / available_workers``. ``0.0`` when ``available_workers`` is
        ``None`` or ``<= 0``. May exceed ``1.0`` on over-subscription.
    compute_time_seconds:
        Sum of per-task execution durations. ``None`` for the samples path.
    wall_time_seconds:
        ``max(finished) - min(started)``. ``None`` for the samples path.
    critical_path_ratio:
        ``compute_time / wall_time``; ``1.0`` == fully serialized. ``None``
        when either operand is unknown or the wall span is zero.
    available_workers:
        The worker capacity used for the capacity ratio (``None`` if unknown).
    """

    task_count: int
    failed_count: int
    peak_concurrent_tasks: float
    mean_concurrent_tasks: float
    parallel_utilization_ratio: float
    capacity_utilization_ratio: float
    compute_time_seconds: float | None
    wall_time_seconds: float | None
    critical_path_ratio: float | None
    available_workers: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_count": self.task_count,
            "failed_count": self.failed_count,
            "peak_concurrent_tasks": self.peak_concurrent_tasks,
            "mean_concurrent_tasks": self.mean_concurrent_tasks,
            "parallel_utilization_ratio": self.parallel_utilization_ratio,
            "capacity_utilization_ratio": self.capacity_utilization_ratio,
            "compute_time_seconds": self.compute_time_seconds,
            "wall_time_seconds": self.wall_time_seconds,
            "critical_path_ratio": self.critical_path_ratio,
            "available_workers": self.available_workers,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_timestamp(dt: datetime) -> float:
    """Convert a datetime to a POSIX timestamp deterministically.

    Naive datetimes are interpreted as UTC (never the local timezone), so the
    result does not depend on the machine's TZ setting.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def _ratio(numerator: float, denominator: float) -> float:
    """Divide with a zero-denominator guard: return ``0.0`` when the
    denominator is zero (documented edge case, no exception raised)."""
    if denominator == 0:
        return 0.0
    return numerator / denominator


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_parallel_utilization(
    executions: Iterable[Any],
    available_workers: int | None = None,
) -> ParallelUtilizationReport:
    """Compute the Parallel Utilization Ratio from execution intervals.

    Parameters
    ----------
    executions:
        Iterable of :class:`TaskExecution` records **or** duck-typed results
        such as :class:`~backend.scheduler.parallelism.ExecutionResult` (any
        object with ``task_id`` / ``started_at`` / ``finished_at`` and
        optionally ``success``).
    available_workers:
        Configured worker capacity used for the capacity ratio. ``None`` or
        ``<= 0`` yields a capacity ratio of ``0.0`` (zero denominator).

    Returns
    -------
    ParallelUtilizationReport
        All zeros for an empty input (no-task edge case).

    Raises
    ------
    ValueError
        If any execution has ``finished_at < started_at`` (inverted interval).
    """
    records: list[TaskExecution] = []
    for item in executions:
        if isinstance(item, TaskExecution):
            records.append(item)
        else:
            records.append(TaskExecution.from_execution_result(item))

    if not records:
        # No tasks: every metric is zero (documented edge case).
        return ParallelUtilizationReport(
            task_count=0,
            failed_count=0,
            peak_concurrent_tasks=0.0,
            mean_concurrent_tasks=0.0,
            parallel_utilization_ratio=0.0,
            capacity_utilization_ratio=0.0,
            compute_time_seconds=0.0,
            wall_time_seconds=0.0,
            critical_path_ratio=0.0,
            available_workers=available_workers,
        )

    failed = 0
    compute_time = 0.0
    events: list[tuple[float, int]] = []
    min_start: float | None = None
    max_finish: float | None = None

    for rec in records:
        start = _to_timestamp(rec.started_at)
        finish = _to_timestamp(rec.finished_at)
        if finish < start:
            raise ValueError(
                f"inverted execution interval for task {rec.task_id!r}: "
                f"finished_at < started_at"
            )
        if not rec.success:
            failed += 1
        compute_time += finish - start
        if min_start is None or start < min_start:
            min_start = start
        if max_finish is None or finish > max_finish:
            max_finish = finish
        if finish > start:
            # Conservative tie rule: ends are applied before starts at equal
            # timestamps (sorted by (time, delta); delta -1 sorts before +1),
            # so a task finishing exactly when another starts is *not* counted
            # as overlapping.
            events.append((start, 1))
            events.append((finish, -1))

    # Sweep the event trace: `cur` is the concurrency during each interval
    # between consecutive event times. Zero-duration tasks emit no events, so
    # they occupy no concurrency footprint (documented edge case).
    events.sort(key=lambda e: (e[0], e[1]))
    cur = 0
    peak = 0
    area = 0.0
    prev_t: float | None = None
    for t, delta in events:
        if prev_t is not None and t > prev_t:
            area += cur * (t - prev_t)
        cur += delta
        if cur > peak:
            peak = cur
        prev_t = t

    wall_span = (max_finish - min_start) if (max_finish is not None and min_start is not None) else 0.0
    mean_conc = _ratio(area, wall_span)
    peak_f = float(peak)

    cap = float(available_workers) if available_workers else 0.0
    capacity_ratio = _ratio(mean_conc, cap) if cap > 0 else 0.0

    return ParallelUtilizationReport(
        task_count=len(records),
        failed_count=failed,
        peak_concurrent_tasks=peak_f,
        mean_concurrent_tasks=mean_conc,
        parallel_utilization_ratio=_ratio(mean_conc, peak_f),
        capacity_utilization_ratio=capacity_ratio,
        compute_time_seconds=compute_time,
        wall_time_seconds=wall_span,
        critical_path_ratio=_ratio(compute_time, wall_span),
        available_workers=available_workers,
    )


def compute_from_concurrency_samples(
    samples: Sequence[tuple[float, int]],
    available_workers: int | None = None,
) -> ParallelUtilizationReport:
    """Compute the report from explicit ``(timestamp, running_count)`` samples.

    This is the "explicit completed/available worker inputs" path: the caller
    supplies worker-count observations (e.g. from an executor's internal
    counters) instead of per-task timestamps. Samples must be ordered by
    timestamp; counts are assumed piecewise-constant between samples.

    Because per-task durations are unknown, ``compute_time_seconds`` and
    ``critical_path_ratio`` are ``None`` in this path.

    Parameters
    ----------
    samples:
        Non-decreasing ``(timestamp, running_count)`` pairs. Empty input
        yields the all-zero report (no-task edge case).
    available_workers:
        Worker capacity for the capacity ratio (``None``/``<= 0`` → ``0.0``).

    Raises
    ------
    ValueError
        If samples are not ordered by non-decreasing timestamp, or a count is
        negative.
    """
    if not samples:
        return ParallelUtilizationReport(
            task_count=0,
            failed_count=0,
            peak_concurrent_tasks=0.0,
            mean_concurrent_tasks=0.0,
            parallel_utilization_ratio=0.0,
            capacity_utilization_ratio=0.0,
            compute_time_seconds=None,
            wall_time_seconds=None,
            critical_path_ratio=None,
            available_workers=available_workers,
        )

    peak = 0
    area = 0.0
    prev_t: float | None = None
    prev_c = 0
    for t, count in samples:
        if count < 0:
            raise ValueError("negative running_count sample")
        if prev_t is not None and t < prev_t:
            raise ValueError("samples must be ordered by non-decreasing timestamp")
        if prev_t is not None and t > prev_t:
            area += prev_c * (t - prev_t)
        if count > peak:
            peak = count
        prev_t = t
        prev_c = count

    first_t = samples[0][0]
    last_t = samples[-1][0]
    wall_span = last_t - first_t
    mean_conc = _ratio(area, wall_span)
    peak_f = float(peak)

    cap = float(available_workers) if available_workers else 0.0
    capacity_ratio = _ratio(mean_conc, cap) if cap > 0 else 0.0

    return ParallelUtilizationReport(
        task_count=0,
        failed_count=0,
        peak_concurrent_tasks=peak_f,
        mean_concurrent_tasks=mean_conc,
        parallel_utilization_ratio=_ratio(mean_conc, peak_f),
        capacity_utilization_ratio=capacity_ratio,
        compute_time_seconds=None,
        wall_time_seconds=wall_span,
        critical_path_ratio=None,
        available_workers=available_workers,
    )
