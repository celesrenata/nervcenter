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

from .base import Base, Vector, TimedRecord, RootRecord, Jsonb, UUIDv4
from .events import Event
from .entities import Entity
from .relationships import Relationship
from .evidence import Evidence
from .claims import Claim, Decision
from .tasks import Task, TaskRun
from .goals import Goal, AgentResult

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
]
