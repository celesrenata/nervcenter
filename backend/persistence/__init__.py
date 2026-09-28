"""Persistence package.

This module provides the persistent storage layer for NerveCenter:

- :mod:`~backend.persistence.connection` — SQLAlchemy async engine, session factory,
  pgvector health checks.
- :mod:`~backend.persistence.models` — ORM models mapping the v0 schema contracts.

Usage::

    from backend.persistence.connection import config_from_env, create_persistence
    from backend.persistence.models import Event, Entity

    config = config_from_env()
    engine, session_factory = create_persistence(config)

    async with session_scope(engine) as session:
        event = Event(id="...", event_type="entity.created", ...)
        session.add(event)
"""

from .connection import (
    config_from_env,
    create_engine,
    create_persistence,
    session_scope,
    ensure_pgvector,
    pgvector_available,
    check_health,
    dispose_engine,
    DatabaseConfig,
    HealthReport,
)

from .models import (
    Base,
    Vector,
    TimedRecord,
    RootRecord,
    Jsonb,
    UUIDv4,
    Event,
    Entity,
    Relationship,
    Evidence,
    Claim,
    Decision,
    Task,
    TaskRun,
    Goal,
    AgentResult,
)

__all__ = [
    # connection
    "config_from_env",
    "create_engine",
    "create_persistence",
    "session_scope",
    "ensure_pgvector",
    "pgvector_available",
    "check_health",
    "dispose_engine",
    "DatabaseConfig",
    "HealthReport",
    # models
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
