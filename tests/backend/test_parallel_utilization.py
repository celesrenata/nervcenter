"""Focused tests for the Parallel Utilization Ratio (PUR) metric.

Covers ``backend/scheduler/utilization.py`` (spec Section 80, ``T-H37`` /
``D-H37``): the metric must be pure and deterministic, must handle the
documented edge cases (no tasks, zero denominators, zero-duration and
inverted intervals, naive timestamps), and must detect fake parallelism
(sequential execution reporting ``W``-way capacity collapses toward ``1/W``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from backend.scheduler.utilization import (
    ParallelUtilizationReport,
    TaskExecution,
    compute_from_concurrency_samples,
    compute_parallel_utilization,
)

UTC_TZ = UTC


def _dt(offset_seconds: float) -> datetime:
    """Deterministic UTC timestamp at ``T0 + offset_seconds``."""
    return datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ) + timedelta(seconds=offset_seconds)


def _ex(
    task_id: str,
    start: float,
    finish: float,
    success: bool = True,
) -> TaskExecution:
    return TaskExecution(task_id=task_id, started_at=_dt(start), finished_at=_dt(finish), success=success)


class TestEdgeCases:
    """Edge cases: no tasks, zero denominators, malformed intervals."""

    def test_no_tasks_yields_all_zero_report(self) -> None:
        report = compute_parallel_utilization([])
        assert report.task_count == 0
        assert report.failed_count == 0
        assert report.peak_concurrent_tasks == 0.0
        assert report.mean_concurrent_tasks == 0.0
        assert report.parallel_utilization_ratio == 0.0
        assert report.capacity_utilization_ratio == 0.0
        assert report.compute_time_seconds == 0.0
        assert report.wall_time_seconds == 0.0
        assert report.critical_path_ratio == 0.0
        # No ZeroDivisionError anywhere — the function is total.

    def test_no_tasks_samples_path_yields_none_timings(self) -> None:
        report = compute_from_concurrency_samples([])
        assert report.task_count == 0
        assert report.peak_concurrent_tasks == 0.0
        assert report.parallel_utilization_ratio == 0.0
        assert report.compute_time_seconds is None
        assert report.wall_time_seconds is None
        assert report.critical_path_ratio is None

    def test_zero_denominator_capacity_ratio(self) -> None:
        # available_workers = None → capacity ratio 0.0, no exception.
        report = compute_parallel_utilization([_ex("a", 0, 10)], available_workers=None)
        assert report.capacity_utilization_ratio == 0.0
        # available_workers = 0 → capacity ratio 0.0, no exception.
        report = compute_parallel_utilization([_ex("a", 0, 10)], available_workers=0)
        assert report.capacity_utilization_ratio == 0.0

    def test_zero_wall_span_single_instant_task(self) -> None:
        # One zero-duration task: wall span 0 → mean 0, PUR 0, no exception.
        report = compute_parallel_utilization([_ex("a", 5, 5)])
        assert report.task_count == 1
        assert report.wall_time_seconds == 0.0
        assert report.mean_concurrent_tasks == 0.0
        assert report.parallel_utilization_ratio == 0.0
        assert report.critical_path_ratio == 0.0
        assert report.compute_time_seconds == 0.0

    def test_inverted_interval_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="inverted"):
            compute_parallel_utilization([_ex("a", 10, 0)])

    def test_negative_sample_count_raises(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            compute_from_concurrency_samples([(0.0, -1)])

    def test_unordered_samples_raise(self) -> None:
        with pytest.raises(ValueError, match="ordered"):
            compute_from_concurrency_samples([(1.0, 2), (0.0, 2)])


class TestDeterminism:
    """Pure/deterministic behavior: identical inputs → identical reports."""

    def test_pure_function_no_state(self) -> None:
        executions = [_ex("a", 0, 2), _ex("b", 0, 2)]
        first = compute_parallel_utilization(executions, available_workers=2)
        second = compute_parallel_utilization(executions, available_workers=2)
        assert first == second
        # The input list is not mutated (pure function).
        assert len(executions) == 2

    def test_naive_datetimes_treated_as_utc(self) -> None:
        # Naive timestamps must not depend on the machine's local timezone.
        naive = TaskExecution(task_id="a", started_at=datetime(2026, 1, 1, 0, 0, 0), finished_at=datetime(2026, 1, 1, 0, 0, 10))
        aware = TaskExecution(
            task_id="a",
            started_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC_TZ),
            finished_at=datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC_TZ),
        )
        r_naive = compute_parallel_utilization([naive], available_workers=1)
        r_aware = compute_parallel_utilization([aware], available_workers=1)
        assert r_naive == r_aware

    def test_report_is_serializable(self) -> None:
        report = compute_parallel_utilization([_ex("a", 0, 1)], available_workers=2)
        payload = report.as_dict()
        assert isinstance(payload, dict)
        assert payload["parallel_utilization_ratio"] == report.parallel_utilization_ratio


class TestRatioSemantics:
    """The PUR and capacity ratio semantics from spec Section 80."""

    def test_fully_parallel_run(self) -> None:
        # 4 tasks, all overlapping exactly, wall span 10s.
        executions = [_ex(f"t{i}", 0, 10) for i in range(4)]
        report = compute_parallel_utilization(executions, available_workers=4)
        assert report.task_count == 4
        assert report.peak_concurrent_tasks == 4.0
        assert report.mean_concurrent_tasks == 4.0
        assert report.parallel_utilization_ratio == 1.0  # mean == peak
        assert report.capacity_utilization_ratio == 1.0  # mean == capacity
        assert report.compute_time_seconds == 40.0
        assert report.wall_time_seconds == 10.0
        assert report.critical_path_ratio == 4.0  # 4x overlap

    def test_fully_sequential_run_is_fake_parallelism(self) -> None:
        # Sequential back-to-back: peak 1, mean 1, PUR 1 (peak-sustained) but
        # capacity ratio collapses to 1/W — the fake-parallelism detector.
        executions = [_ex("a", 0, 10), _ex("b", 10, 20), _ex("c", 20, 30), _ex("d", 30, 40)]
        report = compute_parallel_utilization(executions, available_workers=4)
        assert report.peak_concurrent_tasks == 1.0
        assert report.mean_concurrent_tasks == 1.0
        assert report.parallel_utilization_ratio == 1.0
        assert report.capacity_utilization_ratio == pytest.approx(0.25)
        assert report.critical_path_ratio == 1.0  # zero overlap

    def test_equal_start_finish_not_counted_as_overlap(self) -> None:
        # Conservative tie rule: A finishing exactly when B starts does not
        # count as an overlap.
        executions = [_ex("a", 0, 10), _ex("b", 10, 20)]
        report = compute_parallel_utilization(executions)
        assert report.peak_concurrent_tasks == 1.0
        assert report.mean_concurrent_tasks == 1.0

    def test_partial_parallelism_pur_below_one(self) -> None:
        # Two tasks overlap for half the span: peak 2, mean 1.5, PUR 0.75.
        executions = [_ex("a", 0, 20), _ex("b", 10, 20)]
        report = compute_parallel_utilization(executions)
        assert report.peak_concurrent_tasks == 2.0
        assert report.mean_concurrent_tasks == pytest.approx(1.5)
        assert report.parallel_utilization_ratio == pytest.approx(0.75)
        assert report.critical_path_ratio == pytest.approx(1.5)

    def test_staircase_release_pattern(self) -> None:
        # Staggered starts: concurrency 1→2→3→4→3→2→1 over 12s.
        # Area = 1+2+3+4+3+2+1 = 16; mean = 16/12; peak = 4.
        executions = [
            _ex("a", 0, 4),
            _ex("b", 1, 5),
            _ex("c", 2, 6),
            _ex("d", 3, 7),
            _ex("e", 4, 8),
            _ex("f", 5, 9),
            _ex("g", 6, 10),
        ]
        report = compute_parallel_utilization(executions, available_workers=4)
        # Concurrency per second (each task lasts 4s, starts staggered by 1s):
        # t0-1:1, t1-2:2, t2-3:3, t3-4:4 (peak: a,b,c,d), t4-5:4 (a done, e in),
        # t5-6:4, t6-7:4, t7-8:3, t8-9:2, t9-10:1. Verified by recomputation
        # below instead of a hand-derived constant.
        assert report.peak_concurrent_tasks == 4.0
        assert report.wall_time_seconds == pytest.approx(10.0)
        # mean = area / span; verify deterministically by recompute below.
        expected_area = 0.0
        for t in range(0, 10):
            running = sum(1 for (s, f) in [(0, 4), (1, 5), (2, 6), (3, 7), (4, 8), (5, 9), (6, 10)] if s <= t < f)
            expected_area += running
        expected_mean = expected_area / 10.0
        assert report.mean_concurrent_tasks == pytest.approx(expected_mean)
        assert report.parallel_utilization_ratio == pytest.approx(expected_mean / 4.0)
        assert report.capacity_utilization_ratio == pytest.approx(expected_mean / 4.0)

    def test_over_subscription_not_clamped(self) -> None:
        # 5 concurrent tasks with 4 configured workers: capacity ratio > 1.
        executions = [_ex(f"t{i}", 0, 10) for i in range(5)]
        report = compute_parallel_utilization(executions, available_workers=4)
        assert report.capacity_utilization_ratio == pytest.approx(1.25)

    def test_failed_executions_count_toward_concurrency(self) -> None:
        executions = [_ex("a", 0, 10, success=False), _ex("b", 0, 10, success=False)]
        report = compute_parallel_utilization(executions, available_workers=2)
        assert report.failed_count == 2
        assert report.peak_concurrent_tasks == 2.0
        assert report.capacity_utilization_ratio == 1.0

    def test_zero_duration_tasks_do_not_inflate_concurrency(self) -> None:
        # A zero-duration task among long ones must not raise the peak.
        executions = [_ex("a", 0, 10), _ex("instant", 5, 5), _ex("b", 0, 10)]
        report = compute_parallel_utilization(executions)
        assert report.task_count == 3
        assert report.peak_concurrent_tasks == 2.0
        assert report.mean_concurrent_tasks == pytest.approx(2.0)
        assert report.parallel_utilization_ratio == 1.0


class TestSamplesPath:
    """Explicit (timestamp, running_count) samples entry point."""

    def test_constant_samples(self) -> None:
        report = compute_from_concurrency_samples([(0, 2), (10, 2)], available_workers=4)
        assert report.peak_concurrent_tasks == 2.0
        assert report.mean_concurrent_tasks == 2.0
        assert report.parallel_utilization_ratio == 1.0
        assert report.capacity_utilization_ratio == pytest.approx(0.5)
        assert report.compute_time_seconds is None
        assert report.critical_path_ratio is None
        assert report.wall_time_seconds == pytest.approx(10.0)

    def test_step_samples(self) -> None:
        # 2 running for 5s, then 0 for 5s: mean = 1, peak = 2.
        report = compute_from_concurrency_samples([(0, 2), (5, 0), (10, 0)])
        assert report.peak_concurrent_tasks == 2.0
        assert report.mean_concurrent_tasks == pytest.approx(1.0)
        assert report.parallel_utilization_ratio == pytest.approx(0.5)

    def test_empty_samples_zero_report(self) -> None:
        report = compute_from_concurrency_samples([], available_workers=2)
        assert report.task_count == 0
        assert report.capacity_utilization_ratio == 0.0

    def test_zero_denominator_without_workers(self) -> None:
        report = compute_from_concurrency_samples([(0, 3), (5, 3)], available_workers=None)
        assert report.capacity_utilization_ratio == 0.0
        assert report.parallel_utilization_ratio == 1.0


class TestExecutionResultAdaptor:
    """Duck-typed coercion of executor results (integration path)."""

    def test_from_execution_result_object(self) -> None:
        # Stand-in for backend.scheduler.parallelism.ExecutionResult.
        class FakeResult:
            task_id = "r1"
            started_at = _dt(0)
            finished_at = _dt(5)
            success = False

        report = compute_parallel_utilization([FakeResult()], available_workers=1)
        assert report.task_count == 1
        assert report.failed_count == 1
        assert report.peak_concurrent_tasks == 1.0
        assert report.mean_concurrent_tasks == pytest.approx(5.0 / 5.0)

    def test_mixed_records_and_results(self) -> None:
        class FakeResult:
            task_id = "r2"
            started_at = _dt(0)
            finished_at = _dt(4)

        mixed: list[Any] = [TaskExecution(task_id="r1", started_at=_dt(0), finished_at=_dt(4)), FakeResult()]
        report = compute_parallel_utilization(mixed, available_workers=2)
        assert report.task_count == 2
        assert report.peak_concurrent_tasks == 2.0
        assert report.capacity_utilization_ratio == 1.0
