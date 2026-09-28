"""Tasks: task queues, scheduling, and execution.

This package provides the task service and DAG machinery:

- :mod:`~backend.tasks.dag` — :class:`~backend.tasks.dag.TaskDAG` and
  :class:`~backend.tasks.dag.RunnableQueue` (dependency graph and queue).
- :mod:`~backend.tasks.service` — :class:`~backend.tasks.service.TaskService`
  (CRUD, transitions, dependency helpers).
"""
