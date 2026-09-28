"""Scheduler: DAG-based scheduling and parallel execution.

This package provides the DAG scheduler and parallel executor:

- :mod:`~backend.scheduler.scheduler` — :class:`~backend.scheduler.scheduler.DAGScheduler`
  (identify runnable tasks from goal/tasks DAG).
- :mod:`~backend.scheduler.parallelism` — :class:`~backend.scheduler.parallelism.ParallelExecutor`
  (concurrent task execution with dependency resolution).
"""
