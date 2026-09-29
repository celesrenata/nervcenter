"""Core ORM base classes and pgvector vector type wrapper.

This module provides the foundation for all NerveCenter ORM models:

- :class:`Base` — the declarative base with metadata and naming conventions.
- :class:`Vector` — a PGVector wrapper for embedding storage.
- :class:`TimedRecord` — mixin for creation/updated timestamps.
- :class:`RootRecord` — base class for all persisted records, inheriting
  Pydantic ``Record`` and adding ``id``/``created_at`` ORM columns.

The naming strategy is intentionally strict:

- Table names are plural snake_case (``events``, ``entities``, ``claims``).
- Column names match the Pydantic field names exactly.
- Indexes are named ``ix_<table>_<column>``.
- Constraints are named ``<table>_<constraint_type>_<columns>``.

This makes it trivial to cross-reference ORM tables with the v0 schema contracts
in ``schemas/``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from pydantic import ConfigDict
from sqlalchemy import DateTime, Index, MetaData, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry
from sqlalchemy.types import TypeDecorator

#: PostgreSQL dialect-specific JSONB type for attributes, payload, etc.
#:
#: Plain :class:`~sqlalchemy.dialects.postgresql.JSONB` alias, passed
#: positionally to ``mapped_column(Jsonb, ...)``. (The earlier
#: ``Annotated[..., mapped_column(...)]`` composite was invalid as a
#: SchemaItem argument and broke model import.)
Jsonb = JSONB

#: PostgreSQL UUID type; we generate v4 IDs on the ORM side for consistency
#: with the Pydantic Record contract.
UUIDv4 = Annotated[
    str,
    mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    ),
]

#: Timestamp columns for record provenance.
CreatedTimestamp = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
]

#: A "modified at" column updated via trigger (see Alembic migrations).
UpdatedTimestamp = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
]


class Base(DeclarativeBase):
    """Declarative base for all NerveCenter ORM models.

    The :attr:`metadata` is configured with a consistent naming strategy that
    works well with Alembic autogenerate.
    """

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "%(table_name)s_uq_%(column_0_name)s",
            "ck": "%(table_name)s_ck_%(constraint_name)s",
            "fk": "%(table_name)s_fk_%(column_0_name)s_%(referred_table_name)s",
            "pk": "%(table_name)s_pk",
        }
    )


mapper_registry = registry()


class Vector(TypeDecorator):
    """SQLAlchemy type for PostgreSQL ``vector`` (pgvector extension).

    The vector type is parameterized with the embedding dimension, e.g.
    ``Vector(1536)`` for OpenAI ``text-embedding-3-small``. This wrapper
    ensures the dimension is emitted on the column definition and validates
    that vectors passed to the column match the expected dimension.

    Usage::

        class Event(Base):
            __tablename__ = "events"
            embedding: Mapped[Vector | None] = mapped_column(Vector(1536), nullable=True)

    Parameters
    ----------
    dimensions:
        The number of dimensions the vector must have. ``None`` means any
        dimension (not recommended for production — it relaxes type safety).
    """

    impl = String
    cache_ok = True

    def __init__(self, dimensions: int | None = None) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect) -> Any:
        from sqlalchemy.dialects.postgresql import VECTOR

        return VECTOR(dimensions=self.dimensions)

    def bind_expression(self, bindparam) -> Any:
        # pgvector expects a float4[] literal; cast the string to vector.
        # SQLAlchemy will quote and escape the string properly.
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import VECTOR

        return cast(bindparam, VECTOR(dimensions=self.dimensions))

    def process_bind_param(self, value: Any, dialect) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            # Already a valid pgvector array literal
            return value
        # Convert list/np.ndarray to pgvector array literal
        if hasattr(value, "__iter__"):
            vec_list = list(value)
            if self.dimensions is not None and len(vec_list) != self.dimensions:
                raise ValueError(
                    f"Expected {self.dimensions} dimensions, got {len(vec_list)}"
                )
            return "[" + ",".join(str(float(v)) for v in vec_list) + "]"
        raise TypeError(f"Cannot persist {type(value).__name__} as Vector")

    def process_result_value(self, value: Any, dialect) -> list[float] | None:
        if value is None:
            return None
        # pgvector returns a string like "[1.0,2.0,3.0]" or None
        if isinstance(value, str):
            inner = value.strip("[]")
            if not inner:
                return []
            return [float(x.strip()) for x in inner.split(",")]
        # Sometimes SQLAlchemy gives us the list directly
        return value


class TimedRecord:
    """Mixin that provides ``created_at`` and ``updated_at`` timestamp columns.

    This is intended for models that need auditing of when they were last
    changed (e.g., entities, claims, goals). Use :class:`RootRecord` for
    entities that match the v0 schema contract and get automatic UUID and
    content hash handling.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class RootRecord:
    """Base for all persisted records, mapping v0 ``schemas.Record``.

    This class extends :class:`Base` (ORM) while preserving the v0 contract:

    - ``id`` (UUID string) — stable unique identifier.
    - ``created_at`` (timestamp) — creation time.
    - ``schema_version`` ("v0") — contract version.
    - ``hash`` (SHA-256) — optional integrity digest.

    Subclasses should set ``__pydantic_config__ = {"extra": "forbid"}`` to
    mirror the Pydantic model behavior and should not define additional
    fields beyond those present in the schema contract.
    """

    model_config = ConfigDict(extra="forbid")

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __abstract__ = True

    def fingerprint(self) -> str:
        """Match the v0 :class:`~schemas.base.Record.fingerprint` behavior."""
        from schemas.base import content_hash

        data = {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "schema_version": self.schema_version,
        }
        return content_hash(data)


def create_table_with_vector_index(
    table_name: str,
    columns: list[Any],
    vector_column: str,
    vector_dimensions: int,
) -> tuple[Any, Index]:
    """Convenience builder for a table plus a GiST vector index.

    This mirrors the typical pattern in NerveCenter where every table with
    embeddings needs an index for approximate nearest-neighbor queries.

    Returns
    -------
    table, index
        The ORM table and the index object (which can be used by Alembic
        operations).
    """

    table = mapper_registry.map_imperatively(
        type(f"{table_name.title()}Model", (object,), {}),
        type(
            table_name,
            (Base,),
            {
                "__tablename__": table_name,
                "__table_args__": (),
                **{col.key: col for col in columns},
            },
        ),
    )
    index = Index(
        f"ix_{table_name}_{vector_column}_vec",
        getattr(table, vector_column),
        postgresql_using="gist",
    )
    return table, index
