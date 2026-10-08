"""Event records (NerveCenter spec Section 10).

Events are the atomic units of the NerveCenter event bus. Everything the system
does is expressed as an event, making the core event-driven and replayable.

Assumptions (spec Section 10 not present in the repository):
    - Events carry a human/machine ``event_type`` plus a coarse ``category``
      literal that maps onto the README subsystem layout (events, knowledge,
      evidence, goals, tasks, context, orchestration, inference, policy,
      connectors, observability).
    - ``trace_id`` / ``correlation_id`` / ``parent_event_id`` support
      distributed tracing and event-sourcing lineage.
    - ``sequence`` / ``stream`` support durable replay (WAL offset per stream).
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field

from .base import Record

#: Coarse event classification aligned with the NerveCenter subsystem layout.
EventCategory = Literal[
    "system",
    "knowledge",
    "evidence",
    "goal",
    "task",
    "inference",
    "policy",
    "orchestration",
    "connector",
]

#: Severity levels for operational/signal events.
EventSeverity = Literal["debug", "info", "warning", "error", "critical"]


class Event(Record):
    """A single immutable event on the NerveCenter event bus.

    Events are append-only; corrections are emitted as new events referencing the
    original via ``parent_event_id``. The ``payload`` is an opaque, type-specific
    document whose shape is described by the matching ``event_type`` contract.

    Spec §10 freezes this shape: the record is immutable, so any field mutation
    (including the integrity ``hash``) raises :class:`pydantic.ValidationError`.
    Derivations (e.g. correlation propagation) must go through
    ``model_copy(update=...)``.
    """

    model_config = ConfigDict(frozen=True)

    event_type: str = Field(
        ...,
        description="Machine-readable event type, e.g. 'entity.created' or 'task.completed'.",
    )
    category: EventCategory = Field(
        ...,
        description="Coarse subsystem the event belongs to.",
    )
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the underlying phenomenon occurred (UTC), as opposed to creation time.",
    )
    source: str = Field(
        ...,
        description="Origin of the event, e.g. a connector id, agent id, or 'internal'.",
    )
    subject: str | None = Field(
        default=None,
        description="Optional primary subject id (entity, task, goal, ...) the event is about.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific event body; validated by the matching event_type contract.",
    )
    severity: EventSeverity = Field(
        default="info",
        description="Operational severity of the event.",
    )

    # --- lineage / tracing ---
    trace_id: str | None = Field(
        default=None,
        description="Distributed trace id linking related events across subsystems.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation id grouping a logical unit of work.",
    )
    parent_event_id: str | None = Field(
        default=None,
        description="Id of the event that caused or is corrected by this event.",
    )

    # --- durable replay ---
    stream: str | None = Field(
        default=None,
        description="Logical stream name this event belongs to.",
    )
    sequence: int | None = Field(
        default=None,
        ge=0,
        description="Monotonic offset of this event within its stream (WAL position).",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Key used to deduplicate retried or replayed events.",
    )
