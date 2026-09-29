"""Persistence models package.

This module exports all ORM models used by NerveCenter. Models are grouped
by schema contract:

- :mod:`~backend.persistence.models.base` — declarative base, vector type, mixins.
- :mod:`~backend.persistence.models.events` — :class:`~schemas.events.Event`.
- :mod:`~backend.persistence.models.entities` — :class:`~schemas.entities.Entity`.
- :mod:`~backend.persistence.models.relationships` — :class:`~schemas.relationships.Relationship`.
- :mod:`~backend.persistence.models.evidence` — :class:`~schemas.evidence.Evidence`.
- :mod:`~backend.persistence.models.claims` — :class:`~schemas.claims.Claim`, :class:`~schemas.claims.Decision`.
- :mod:`~backend.persistence.models.tasks` — :class:`~schemas.tasks.Task`, :class:`~schemas.tasks.TaskRun`.
- :mod:`~backend.persistence.models.goals` — :class:`~schemas.goals.Goal`, :class:`~schemas.goals.AgentResult`.

Usage::

    from backend.persistence.models import Event, Entity, Goal, Task
"""

from .base import Base, Jsonb, RootRecord, TimedRecord, UUIDv4, Vector
from .claims import Claim, Decision
from .entities import Entity
from .events import Event
from .evidence import Evidence
from .goals import AgentResult, Goal
from .planned_changes import PlannedChange
from .relationships import Relationship
from .tasks import Task, TaskRun

__all__ = [
    "Base",
    "Vector",
    "TimedRecord",
    "RootRecord",
    "Jsonb",
    "UUIDv4",
    "Event",
    "Entity",
    "Relationship",
    "Evidence",
    "Claim",
    "Decision",
    "Task",
    "TaskRun",
    "Goal",
    "AgentResult",
    "PlannedChange",
]
