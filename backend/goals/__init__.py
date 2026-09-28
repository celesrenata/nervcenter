"""Goals: goal models, decomposition, and progress tracking.

This package provides the goal lifecycle service and reconciliation:

- :mod:`~backend.goals.service` — :class:`~backend.goals.service.GoalService`
  (create, read, update, delete, transitions).
- :mod:`~backend.goals.reconciliation` — :class:`~backend.goals.reconciliation.GoalReconciler`
  (reconcile stored progress against actual task state).
"""
