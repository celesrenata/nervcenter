"""Resource registry service (NC-SPEC-2026-010 Phase 2, C2).

Service layer over the C1 canonical-platform ORM rows
(``backend/persistence/models/nc_platform.py``) and the frozen contract pack
(``schemas/nc_platform.py``). The knowledge foundation (``backend/knowledge``)
and the connector ABC (``backend/connectors/base.py``) are *consumed* here
only via the frozen contracts — this module owns ``backend/registry/**``.

Design notes
------------
- **URI is the identity.** Every write/lookup goes through
  ``schemas.nc_platform.validate_nc_uri`` (the frozen ``nc-grammar v1``
  parser); nothing in this module re-implements the grammar. The canonical
  URI is stored verbatim (``NCResourceRow.uri``, unique) and the stable
  platform resource id is *derived* from it (``res_`` + Crockford body of
  the URI's resource-id segment, ADR-0001 "stable registry id").
- **Reconciliation key.** Upserts are keyed by
  ``(connector_instance_id, provider_resource_id)`` and the unique URI, so
  at-least-once discovery is idempotent: re-reporting the same sighting
  updates one row, never creates a second (NC-REQ-008).
- **Tombstones are explicit.** A resource is marked
  ``sync_status='tombstoned'`` only on an explicit provider-deletion signal
  (``delete_resource`` / a sighting carrying ``deleted=True``). Connector
  outages (``record_outage``) flip the *instance* health to
  ``unreachable`` and age the instance's live resources to ``stale`` —
  they never tombstone or delete anything. Rows are never physically
  deleted (NC-REQ-008, ADR-0001 §Tombstones).
- **Snapshots.** Every state change captures an immutable
  ``NCResourceSnapshotRow``; the ``dedup_key`` makes repeated identical
  sightings skip the snapshot write (idempotent reconciliation).
- **Session injection.** Methods take a caller-supplied
  ``AsyncSession`` and commit internally (one transaction per call),
  matching ``backend/knowledge/entity.py`` conventions. The service opens
  no connections of its own.

Integration handoff (for the parent): a later router (outside this worker's
owned scope) maps the public async methods 1:1 onto ``/api/registry/*``:
``reconcile`` ← connector discovery webhook/poll, ``delete_resource`` ←
explicit provider deletion event, ``record_outage``/``record_healthy`` ←
connector health channel, ``create_relation``/``add_alias`` ← mutation
requests (policy-checked upstream, NC-CAP-007).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.persistence.models.nc_platform import (
    NCConnectorInstanceRow,
    NCResourceAliasRow,
    NCResourceRelationRow,
    NCResourceRow,
    NCResourceSnapshotRow,
)
from schemas.nc_platform import (
    DataClassification,
    NcUriParts,
    validate_nc_uri,
)

log = structlog.get_logger(__name__)

#: Crockford base32 alphabet (ULID body), per the frozen id patterns in
#: ``schemas.nc_platform`` (``[0-9A-HJKMNP-TV-Z]``). Defined here because the
#: frozen module exports only patterns, not the alphabet.
CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

#: Default horizon after which an un-seen resource is reported as stale.
DEFAULT_STALE_AFTER_SECONDS: int = 60 * 60


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RegistryError(Exception):
    """Base error for registry operations."""


class RegistryUriError(RegistryError, ValueError):
    """A canonical ``nc://`` URI failed the frozen grammar.

    Wraps the frozen :class:`~schemas.nc_platform.NcUriError` so API callers
    can catch a registry-specific exception. ``code`` is the grammar error
    code (uri-grammar.md §8) when available.
    """

    def __init__(self, uri: str, *, code: str | None = None, detail: str = "") -> None:
        self.uri = uri
        self.code = code
        super().__init__(f"invalid nc:// URI {uri!r}" + (f" [{code}]: {detail}" if code else f": {detail}"))


class RegistryResourceNotFound(RegistryError, LookupError):
    """No live (non-tombstoned) resource matches the identifier."""


class RegistryConnectorNotFound(RegistryError, LookupError):
    """No connector instance is registered under the given id."""


#: Values allowed for :meth:`RegistryService.record_outage` / health states
#: (frozen ``NcConnectorHealth`` literals).
_HEALTH_VALUES = ("healthy", "degraded", "unreachable", "lost")


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Sighting:
    """One provider observation of a resource, fed to
    :meth:`RegistryService.reconcile`.

    ``uri`` is the canonical ``nc://`` URI (frozen-grammar validated);
    ``provider_resource_id`` is the provider-native id, stored verbatim
    (preserved, never re-minted). ``deleted=True`` is the *explicit
    provider-deletion* signal; a sighting merely missing from a batch is
    **not** a deletion signal.
    """

    uri: str
    provider_resource_id: str
    display_name: str = ""
    observed_state: dict[str, Any] = field(default_factory=dict)
    source_evidence: tuple[str, ...] = ()
    data_classification: DataClassification = "PUBLIC"
    capabilities: tuple[str, ...] = ()
    deleted: bool = False
    observed_at: datetime | None = None


@dataclass(frozen=True)
class ReconcileOutcome:
    """Per-sighting outcome of a :meth:`RegistryService.reconcile` call."""

    uri: str
    resource_id: str
    created: bool
    changed: bool
    tombstoned: bool


@dataclass(frozen=True)
class RegistryInstanceView:
    """Registry's view of a registered connector instance (row projection)."""

    instance_id: str
    provider: str
    health: str
    read_only: bool
    updated_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    """Return *dt* as UTC-aware.

    SQLite round-trips ``DateTime(timezone=True)`` as naive values, so rows
    read back from a SQLite backend lose their tzinfo. Comparing a naive
    stored value against an aware "now" is always unequal (and
    ``naive.timestamp()`` interprets local time), which would make every
    re-sighting look changed and break staleness math. Normalizing at the
    read boundary keeps the service correct on both SQLite and PostgreSQL.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _crockford(body: bytes, length: int) -> str:
    """Deterministically map *body* to Crockford-base32 chars (frozen alphabet)."""
    return "".join(CROCKFORD_ALPHABET[b % len(CROCKFORD_ALPHABET)] for b in body[:length])


def mint_resource_id(uri: str) -> str:
    """Mint the stable platform resource id for a canonical URI.

    Deterministic in the URI's identity segments (namespace/provider/scope/
    kind/resource-id), so the same URI always yields the same id — the
    ADR-0001 "stable registry id". The body is drawn from the frozen
    Crockford alphabet so it always satisfies the ``res_[0-9A-HJKMNP-TV-Z]``
    id pattern; it is kept short so it fits ``String(32)``.
    """
    try:
        parts = validate_nc_uri(uri)
    except Exception as exc:
        raise RegistryUriError(
            uri, code=getattr(exc, "code", None), detail=str(exc)
        ) from exc
    identity = "/".join(
        [parts.namespace, parts.provider, parts.scope, parts.kind, parts.resource_id]
    )
    body = hashlib.sha256(identity.encode("utf-8")).digest()
    return "res_" + _crockford(body, 26)


def _parts(uri: str) -> NcUriParts:
    """Validate *uri* with the frozen grammar and return its parts."""
    try:
        return validate_nc_uri(uri)
    except Exception as exc:  # normalize to registry-level error
        code = getattr(exc, "code", None)
        raise RegistryUriError(uri, code=code, detail=str(exc)) from exc


async def _fetch_instance(
    session: AsyncSession, instance_id: str
) -> NCConnectorInstanceRow | None:
    result = await session.execute(
        select(NCConnectorInstanceRow).where(
            NCConnectorInstanceRow.instance_id == instance_id
        )
    )
    return result.scalar_one_or_none()


async def _fetch_by_uri(session: AsyncSession, uri: str) -> NCResourceRow | None:
    result = await session.execute(select(NCResourceRow).where(NCResourceRow.uri == uri))
    return result.scalar_one_or_none()


async def _fetch_live_by_uri(session: AsyncSession, uri: str) -> NCResourceRow | None:
    """Row for *uri*, if it is live (non-tombstoned)."""
    row = await _fetch_by_uri(session, uri)
    if row is None or row.sync_status == "tombstoned":
        return None
    return row


async def _fetch_by_key(
    session: AsyncSession,
    connector_instance_id: str,
    provider_resource_id: str,
) -> NCResourceRow | None:
    result = await session.execute(
        select(NCResourceRow).where(
            NCResourceRow.connector_instance_id == connector_instance_id,
            NCResourceRow.provider_resource_id == provider_resource_id,
        )
    )
    return result.scalar_one_or_none()


def _snapshot_state(row: NCResourceRow) -> dict[str, Any]:
    """Serializable state captured by a snapshot row."""
    return {
        "uri": row.uri,
        "resource_id": row.resource_id,
        "display_name": row.display_name,
        "kind": row.kind,
        "sync_status": row.sync_status,
        "provider_resource_id": row.provider_resource_id,
        "provider": row.provider,
        "observed_state": row.observed_state or {},
        "observed_at": row.observed_at.isoformat() if row.observed_at else None,
        "source_evidence": list(row.source_evidence or []),
    }


def _snapshot_dedup_key(row: NCResourceRow) -> str:
    """Content hash used to skip duplicate snapshot rows on re-sightings."""
    payload = repr(
        (
            row.uri,
            row.sync_status,
            row.display_name,
            row.observed_state,
            tuple(sorted(str(e) for e in (row.source_evidence or []))),
            row.provider_resource_id,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _aware(dt: datetime) -> datetime:
    """Normalize a non-null datetime column value to UTC-aware."""
    return _ensure_aware(dt) or dt


def _instance_view(row: NCConnectorInstanceRow) -> RegistryInstanceView:
    return RegistryInstanceView(
        instance_id=row.instance_id,
        provider=row.provider,
        health=row.health,
        read_only=row.read_only,
        updated_at=_aware(row.updated_at),
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RegistryService:
    """Canonical resource registry (NC-SPEC-2026-010 C2).

    Constructor arguments:

    - ``stale_after_seconds`` — horizon for :meth:`sync_health` staleness.
    - ``clock`` — override ``datetime.now(UTC)`` (tests inject a fixed one).
    """

    def __init__(
        self,
        *,
        stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
        clock: Any = None,
    ) -> None:
        self._stale_after_seconds = stale_after_seconds
        self._clock = clock or _now

    # -- clock -------------------------------------------------------------

    def _now(self) -> datetime:
        return self._clock()

    # ------------------------------------------------------------------
    # Connector instance registration
    # ------------------------------------------------------------------

    async def upsert_instance(
        self,
        session: AsyncSession,
        *,
        instance_id: str,
        provider: str,
        credentials_ref: str = "vault://nc",
        scopes: Sequence[str] = (),
        read_only: bool = False,
    ) -> RegistryInstanceView:
        """Register (or refresh) a connector instance; idempotent.

        ``instance_id`` is the caller-chosen stable id (``conn_`` + ULID per
        the platform convention; the registry stores it verbatim).
        """
        now = self._now()
        row = await _fetch_instance(session, instance_id)
        if row is None:
            row = NCConnectorInstanceRow(
                instance_id=instance_id,
                provider=provider,
                credentials_ref=credentials_ref,
                scopes=list(scopes),
                rate_limit={},
                read_only=read_only,
                health="healthy",
            )
            session.add(row)
            await session.flush()
        else:
            row.provider = provider
            row.read_only = read_only
            row.updated_at = now
        await session.commit()
        return _instance_view(row)

    async def get_instance(
        self, session: AsyncSession, *, instance_id: str
    ) -> RegistryInstanceView:
        row = await _fetch_instance(session, instance_id)
        if row is None:
            raise RegistryConnectorNotFound(instance_id)
        return _instance_view(row)

    async def record_outage(
        self,
        session: AsyncSession,
        *,
        instance_id: str,
        error: str | None = None,
    ) -> int:
        """Record a connector outage (integration loss — *not* deletion).

        Sets the instance health to ``unreachable`` and ages every live
        resource it reported to ``sync_status='stale'``. No resource is
        tombstoned or deleted: a provider may come back, and NC-REQ-008
        forbids treating loss of connectivity as loss of data.

        Returns the number of resources aged to stale.
        """
        now = self._now()
        row = await _fetch_instance(session, instance_id)
        if row is None:
            raise RegistryConnectorNotFound(instance_id)
        row.health = "unreachable"
        row.updated_at = now
        if error:
            log.info("registry.outage.error", instance_id=instance_id, error=error)

        resources = (
            await session.execute(
                select(NCResourceRow).where(
                    NCResourceRow.connector_instance_id == instance_id,
                    NCResourceRow.sync_status.notin_(("stale", "tombstoned")),
                )
            )
        ).scalars().all()
        for res in resources:
            res.sync_status = "stale"
            res.updated_at = now
        await session.commit()
        log.info(
            "registry.outage",
            instance_id=instance_id,
            aged_to_stale=len(resources),
        )
        return len(resources)

    async def record_healthy(
        self,
        session: AsyncSession,
        *,
        instance_id: str,
        health: str = "healthy",
    ) -> RegistryInstanceView:
        """Clear an outage: instance back to ``healthy``.

        (Resource staleness is resolved by the next successful
        :meth:`reconcile`, which resets rows to ``current``.)
        """
        if health not in _HEALTH_VALUES:
            raise RegistryError(f"unknown connector health {health!r}")
        row = await _fetch_instance(session, instance_id)
        if row is None:
            raise RegistryConnectorNotFound(instance_id)
        row.health = health
        row.updated_at = self._now()
        await session.commit()
        return _instance_view(row)

    # ------------------------------------------------------------------
    # Reconciliation (at-least-once discovery)
    # ------------------------------------------------------------------

    async def reconcile(
        self,
        session: AsyncSession,
        *,
        instance_id: str,
        sightings: Sequence[Sighting | dict[str, Any]],
    ) -> list[ReconcileOutcome]:
        """Reconcile a batch of sightings into the registry (idempotent).

        Each sighting is validated against the frozen URI grammar, matched
        by ``(instance_id, provider_resource_id)`` and the unique URI, and
        upserted. Re-running the same batch (at-least-once delivery) creates
        no duplicates: existing rows are updated in place, and unchanged
        sightings skip the snapshot write via ``dedup_key``.

        A sighting with ``deleted=True`` tombstones the resource (explicit
        provider deletion). Sightings *absent* from a batch are left alone —
        absence is never a deletion signal.

        Returns one :class:`ReconcileOutcome` per sighting, in order.
        """
        inst = await _fetch_instance(session, instance_id)
        if inst is None:
            raise RegistryConnectorNotFound(
                f"connector instance {instance_id!r} is not registered; "
                "call upsert_instance before reconciling"
            )
        provider = inst.provider
        outcomes: list[ReconcileOutcome] = []
        for raw in sightings:
            sighting = (
                raw if isinstance(raw, Sighting) else Sighting(**raw)
            )
            outcome = await self._upsert_sighting(session, inst, sighting)
            outcomes.append(outcome)
        await session.commit()
        log.info(
            "registry.reconciled",
            instance_id=instance_id,
            provider=provider,
            batch=len(outcomes),
        )
        return outcomes

    async def _upsert_sighting(
        self,
        session: AsyncSession,
        inst: NCConnectorInstanceRow,
        sighting: Sighting,
    ) -> ReconcileOutcome:
        parts = _parts(sighting.uri)  # frozen grammar; raises RegistryUriError
        now = sighting.observed_at or self._now()
        resource_id = mint_resource_id(sighting.uri)

        row = await _fetch_by_key(
            session, inst.instance_id, sighting.provider_resource_id
        )
        if row is None:
            row = await _fetch_by_uri(session, sighting.uri)
        created = row is None
        if row is None:
            row = NCResourceRow(resource_id=resource_id, uri=sighting.uri)
            session.add(row)

        # Identity columns (stable, derived from the canonical URI).
        row.namespace = parts.namespace
        row.provider = parts.provider
        row.kind = parts.kind
        row.connector_instance_id = inst.instance_id
        # Provider-native id preserved verbatim (never re-minted).
        row.provider_resource_id = sighting.provider_resource_id

        changed = False
        if row.display_name != (sighting.display_name or parts.resource_id):
            row.display_name = sighting.display_name or parts.resource_id
            changed = True
        if row.observed_state != (sighting.observed_state or {}):
            row.observed_state = dict(sighting.observed_state or {})
            changed = True
        if list(row.source_evidence or []) != list(sighting.source_evidence):
            row.source_evidence = list(sighting.source_evidence)
            changed = True
        if row.data_classification != sighting.data_classification:
            row.data_classification = sighting.data_classification
            changed = True
        if list(row.capabilities or []) != list(sighting.capabilities):
            row.capabilities = list(sighting.capabilities)
            changed = True

        if sighting.deleted:
            # Explicit provider deletion → tombstone (row is never deleted).
            row.sync_status = "tombstoned"
            row.observed_at = now
            changed = True
        else:
            if row.sync_status != "current":
                row.sync_status = "current"
                changed = True
            if _ensure_aware(row.observed_at) != now:
                row.observed_at = now
                changed = True
        row.updated_at = now

        await session.flush()
        # Snapshot only when state actually changed → idempotent re-sightings
        # (same content) write no second snapshot row.
        if changed or created:
            await self._snapshot(session, row, inst, captured_at=now)
        return ReconcileOutcome(
            uri=sighting.uri,
            resource_id=resource_id,
            created=created,
            changed=changed,
            tombstoned=sighting.deleted,
        )

    async def _snapshot(
        self,
        session: AsyncSession,
        row: NCResourceRow,
        inst: NCConnectorInstanceRow,
        *,
        captured_at: datetime,
    ) -> None:
        dedup_key = _snapshot_dedup_key(row)
        existing = (
            await session.execute(
                select(NCResourceSnapshotRow).where(
                    NCResourceSnapshotRow.resource_id == row.resource_id,
                    NCResourceSnapshotRow.dedup_key == dedup_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return
        session.add(
            NCResourceSnapshotRow(
                resource_id=row.resource_id,
                state=_snapshot_state(row),
                captured_at=captured_at,
                connector_instance_id=inst.instance_id,
                dedup_key=dedup_key,
            )
        )

    # ------------------------------------------------------------------
    # Deletion (explicit provider signal only)
    # ------------------------------------------------------------------

    async def delete_resource(
        self,
        session: AsyncSession,
        *,
        instance_id: str,
        uri: str,
        observed_at: datetime | None = None,
    ) -> ReconcileOutcome:
        """Tombstone a resource on an **explicit** provider-deletion signal.

        Only a positive deletion observation does this — never a connector
        outage, and never an empty discovery batch. The row and its aliases
        are retained so the canonical URI keeps resolving (NC-REQ-008).
        """
        inst = await _fetch_instance(session, instance_id)
        if inst is None:
            raise RegistryConnectorNotFound(instance_id)
        _parts(uri)
        row = await _fetch_by_uri(session, uri)
        if row is None:
            raise RegistryResourceNotFound(uri)
        now = observed_at or self._now()
        tombstoned_already = row.sync_status == "tombstoned"
        row.sync_status = "tombstoned"
        row.observed_at = now
        row.updated_at = now
        await session.flush()
        if not tombstoned_already:
            await self._snapshot(session, row, inst, captured_at=now)
        await session.commit()
        return ReconcileOutcome(
            uri=uri,
            resource_id=row.resource_id,
            created=False,
            changed=not tombstoned_already,
            tombstoned=True,
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_resource(self, session: AsyncSession, *, uri: str) -> dict[str, Any]:
        """Fetch a live resource by canonical URI (dict projection)."""
        row = await _fetch_live_by_uri(session, uri)
        if row is None:
            raise RegistryResourceNotFound(uri)
        return self._resource_view(row)

    async def get_resource_by_provider_id(
        self,
        session: AsyncSession,
        *,
        instance_id: str,
        provider_resource_id: str,
    ) -> dict[str, Any] | None:
        """Resolve the reconciliation key to its resource view (or None)."""
        row = await _fetch_by_key(session, instance_id, provider_resource_id)
        return self._resource_view(row) if row is not None else None

    async def list_resources(
        self,
        session: AsyncSession,
        *,
        instance_id: str | None = None,
        include_tombstoned: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """List resources (newest updated first)."""
        stmt = select(NCResourceRow)
        if not include_tombstoned:
            stmt = stmt.where(NCResourceRow.sync_status != "tombstoned")
        if instance_id is not None:
            stmt = stmt.where(NCResourceRow.connector_instance_id == instance_id)
        stmt = stmt.order_by(NCResourceRow.updated_at.desc()).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        return [self._resource_view(r) for r in rows]

    def _resource_view(self, row: NCResourceRow) -> dict[str, Any]:
        return {
            "resource_id": row.resource_id,
            "uri": row.uri,
            "namespace": row.namespace,
            "provider": row.provider,
            "kind": row.kind,
            "display_name": row.display_name,
            "connector_instance_id": row.connector_instance_id,
            "provider_resource_id": row.provider_resource_id,
            "data_classification": row.data_classification,
            "capabilities": list(row.capabilities or []),
            "labels": row.labels or {},
            "observed_state": row.observed_state or {},
            "observed_at": _ensure_aware(row.observed_at),
            "sync_status": row.sync_status,
            "source_evidence": list(row.source_evidence or []),
            "created_at": _ensure_aware(row.created_at),
            "updated_at": _ensure_aware(row.updated_at),
        }

    # ------------------------------------------------------------------
    # Aliases
    # ------------------------------------------------------------------

    async def add_alias(
        self,
        session: AsyncSession,
        *,
        uri: str,
        alias_uri: str,
        kind: str = "user",
        created_by_principal_id: str | None = None,
    ) -> dict[str, Any]:
        """Link a non-canonical identity to a live canonical resource.

        Idempotent: re-adding the same alias updates nothing. Alias rows are
        retained when the resource is tombstoned, so historical aliases keep
        resolving (ADR-0001).
        """
        parts = _parts(uri)
        alias_parts = _parts(alias_uri)
        row = await _fetch_live_by_uri(session, uri)
        if row is None:
            raise RegistryResourceNotFound(uri)
        existing = (
            await session.execute(
                select(NCResourceAliasRow).where(
                    NCResourceAliasRow.resource_id == row.resource_id,
                    NCResourceAliasRow.alias_uri == alias_uri,
                )
            )
        ).scalar_one_or_none()
        created = existing is None
        if created:
            session.add(
                NCResourceAliasRow(
                    alias_uri=alias_uri,
                    resource_id=row.resource_id,
                    kind=kind,
                    namespace=alias_parts.namespace,
                    created_by_principal_id=created_by_principal_id,
                )
            )
            await session.flush()
        await session.commit()
        return {
            "alias_uri": alias_uri,
            "uri": uri,
            "resource_id": row.resource_id,
            "kind": kind,
            "created": created,
        }

    async def resolve_alias(self, session: AsyncSession, *, alias_uri: str) -> dict[str, Any] | None:
        """Resolve an alias URI to its live canonical resource view (or None)."""
        _parts(alias_uri)
        alias = (
            await session.execute(
                select(NCResourceAliasRow).where(
                    NCResourceAliasRow.alias_uri == alias_uri
                )
            )
        ).scalar_one_or_none()
        if alias is None:
            return None
        target = (
            await session.execute(
                select(NCResourceRow).where(
                    NCResourceRow.resource_id == alias.resource_id
                )
            )
        ).scalar_one_or_none()
        if target is None or target.sync_status == "tombstoned":
            return None
        return self._resource_view(target)

    async def list_aliases(
        self, session: AsyncSession, *, uri: str
    ) -> list[dict[str, Any]]:
        """List alias rows registered on a resource."""
        parts = _parts(uri)
        row = await _fetch_by_uri(session, uri)
        if row is None:
            raise RegistryResourceNotFound(uri)
        aliases = (
            await session.execute(
                select(NCResourceAliasRow).where(
                    NCResourceAliasRow.resource_id == row.resource_id
                )
            )
        ).scalars().all()
        return [
            {
                "alias_uri": a.alias_uri,
                "kind": a.kind,
                "namespace": a.namespace,
                "created_at": _ensure_aware(a.created_at),
            }
            for a in aliases
        ]

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------

    async def create_relation(
        self,
        session: AsyncSession,
        *,
        source_uri: str,
        target_uri: str,
        relation_type: str,
        confidence: float = 1.0,
        evidence: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Declare a relation between two live resources (idempotent).

        The unique ``(source, target, type)`` triple means re-declaring the
        same relation updates nothing but returns ``created=False``.
        """
        source_parts = _parts(source_uri)
        target_parts = _parts(target_uri)
        source = await _fetch_live_by_uri(session, source_uri)
        target = await _fetch_live_by_uri(session, target_uri)
        if source is None:
            raise RegistryResourceNotFound(source_uri)
        if target is None:
            raise RegistryResourceNotFound(target_uri)
        existing = (
            await session.execute(
                select(NCResourceRelationRow).where(
                    NCResourceRelationRow.source_resource_id == source.resource_id,
                    NCResourceRelationRow.target_resource_id == target.resource_id,
                    NCResourceRelationRow.relation_type == relation_type,
                )
            )
        ).scalar_one_or_none()
        created = existing is None
        if created:
            session.add(
                NCResourceRelationRow(
                    source_resource_id=source.resource_id,
                    target_resource_id=target.resource_id,
                    relation_type=relation_type,
                    confidence=confidence,
                    evidence=list(evidence),
                )
            )
            await session.flush()
        await session.commit()
        return {
            "source_uri": source_uri,
            "target_uri": target_uri,
            "relation_type": relation_type,
            "confidence": confidence,
            "created": created,
        }

    async def list_relations(
        self,
        session: AsyncSession,
        *,
        uri: str,
        direction: str = "any",
    ) -> list[dict[str, Any]]:
        """List relations touching a resource.

        ``direction`` ∈ {"outgoing", "incoming", "any"}.
        """
        if direction not in ("outgoing", "incoming", "any"):
            raise RegistryError(f"unknown relation direction {direction!r}")
        _parts(uri)
        row = await _fetch_live_by_uri(session, uri)
        if row is None:
            raise RegistryResourceNotFound(uri)
        stmt = (
            select(NCResourceRelationRow)
            .where(
                (NCResourceRelationRow.source_resource_id == row.resource_id)
                | (NCResourceRelationRow.target_resource_id == row.resource_id)
            )
            .order_by(NCResourceRelationRow.created_at)
        )
        rels = (await session.execute(stmt)).scalars().all()
        out: list[dict[str, Any]] = []
        for rel in rels:
            if direction == "outgoing" and rel.source_resource_id != row.resource_id:
                continue
            if direction == "incoming" and rel.target_resource_id != row.resource_id:
                continue
            out.append(
                {
                    "relation_type": rel.relation_type,
                    "source_resource_id": rel.source_resource_id,
                    "target_resource_id": rel.target_resource_id,
                    "confidence": rel.confidence,
                    "evidence": list(rel.evidence or []),
                }
            )
        return out

    # ------------------------------------------------------------------
    # Sync health / staleness
    # ------------------------------------------------------------------

    async def sync_health(self, session: AsyncSession) -> dict[str, Any]:
        """Compute registry sync health.

        Returns instance health plus per-instance resource counts and the
        list of stale live resources (seen more than ``stale_after_seconds``
        ago, or never observed). Tombstoned resources are excluded — they
        are final, not lagging.
        """
        now = self._now()
        cutoff_ts = now.timestamp() - self._stale_after_seconds
        instances = (
            (await session.execute(select(NCConnectorInstanceRow).order_by(NCConnectorInstanceRow.instance_id))).scalars().all()
        )
        resources = (
            (
                await session.execute(
                    select(NCResourceRow).where(
                        NCResourceRow.sync_status != "tombstoned"
                    )
                )
            )
            .scalars()
            .all()
        )
        by_instance: dict[str, dict[str, Any]] = {
            inst.instance_id: {
                "instance_id": inst.instance_id,
                "provider": inst.provider,
                "health": inst.health,
                "updated_at": _ensure_aware(inst.updated_at),
                "resources": 0,
                "stale": 0,
                "tombstoned": 0,
            }
            for inst in instances
        }
        stale_uris: list[str] = []
        for res in resources:
            bucket = by_instance.get(res.connector_instance_id)
            if bucket is not None:
                bucket["resources"] += 1
            observed = _ensure_aware(res.observed_at)
            stale = res.sync_status == "stale" or (
                observed is not None and observed.timestamp() < cutoff_ts
            )
            if stale:
                stale_uris.append(res.uri)
                if bucket is not None:
                    bucket["stale"] += 1
        # Count tombstones per instance for reporting (not "lagging").
        tombstones = (
            (
                await session.execute(
                    select(NCResourceRow).where(
                        NCResourceRow.sync_status == "tombstoned"
                    )
                )
            )
            .scalars()
            .all()
        )
        for res in tombstones:
            bucket = by_instance.get(res.connector_instance_id)
            if bucket is not None:
                bucket["tombstoned"] += 1
        return {
            "now": now,
            "stale_after_seconds": self._stale_after_seconds,
            "instances": list(by_instance.values()),
            "stale_resources": sorted(stale_uris),
        }
