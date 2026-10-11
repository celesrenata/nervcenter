"""Focused tests for the C2 registry service (backend/registry/service.py).

Covers the C2 requirements against the C1 frozen contracts/ORM:

- Canonical ``nc://`` URI handling via the frozen grammar (no re-implementation).
- Deterministic, pattern-valid platform resource ids (``res_`` + Crockford).
- Idempotent at-least-once reconciliation (no duplicate rows / snapshots).
- Explicit-deletion-only tombstones; rows and aliases are never deleted.
- Outage semantics: health degradation + ``stale`` aging, never deletion.
- Aliases and relations with idempotent create and directional listing.
- Sync health / staleness reporting.

Uses in-memory SQLite (StaticPool) so the suite is hermetic; only the five
registry tables are created (the broader metadata set is out of scope here).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from backend.persistence.models.base import Base
from backend.persistence.models.nc_platform import (
    NCConnectorInstanceRow,
    NCResourceAliasRow,
    NCResourceRelationRow,
    NCResourceRow,
    NCResourceSnapshotRow,
)
from backend.registry.service import (
    RegistryConnectorNotFound,
    RegistryError,
    RegistryResourceNotFound,
    RegistryService,
    RegistryUriError,
    Sighting,
    mint_resource_id,
)
from schemas.nc_platform import RESOURCE_ID_PATTERN, validate_nc_uri

CONN = "conn_AAAAAAAAAAAAAAAAAAAAAAAAAA"
LAMP = "nc://personal/homeassistant/home/devices/bedroom-lamp"
PLUG = "nc://personal/homeassistant/home/devices/kitchen-plug"
FLOW = "nc://personal/homeassistant/home/automations/morning"
NOW = datetime(2026, 10, 11, 12, 0, 0, tzinfo=UTC)


def _sighting(uri: str, prid: str, **kw) -> Sighting:
    base = dict(
        uri=uri,
        provider_resource_id=prid,
        display_name=kw.pop("display_name", "D"),
        observed_state=kw.pop("observed_state", {"on": True}),
        source_evidence=kw.pop("source_evidence", ("ev1",)),
    )
    base.update(kw)
    return Sighting(**base)


@pytest.fixture
async def db():
    """Fresh in-memory registry store with the default instance registered;
    yields (session_factory, service)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        NCConnectorInstanceRow.__table__,
        NCResourceRow.__table__,
        NCResourceAliasRow.__table__,
        NCResourceRelationRow.__table__,
        NCResourceSnapshotRow.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    svc = RegistryService(
        stale_after_seconds=3600,
        clock=lambda: NOW,
    )
    async with sessions() as s:
        await svc.upsert_instance(s, instance_id=CONN, provider="homeassistant")
    yield sessions, svc
    await engine.dispose()


# ---------------------------------------------------------------------------
# Resource id minting
# ---------------------------------------------------------------------------


def test_mint_resource_id_is_deterministic_and_pattern_valid():
    a = mint_resource_id(LAMP)
    b = mint_resource_id(LAMP)
    assert a == b
    assert a != mint_resource_id(PLUG)
    assert re.fullmatch(RESOURCE_ID_PATTERN, a), a


def test_mint_resource_id_rejects_bad_uri():
    with pytest.raises(RegistryUriError):
        mint_resource_id("http://not/nc")


def test_mint_resource_id_derives_from_uri_identity_segments():
    # Same identity segments (any of them) → same id; a different segment → different id.
    a = mint_resource_id("nc://personal/homeassistant/home/devices/bedroom-lamp")
    b = mint_resource_id("nc://personal/homeassistant/home/automations/bedroom-lamp")
    c = mint_resource_id("nc://shared/homeassistant/home/devices/bedroom-lamp")
    assert a != b  # kind differs
    assert a != c  # namespace differs
    # The minted id embeds Crockford-only characters in the body.
    body = a.removeprefix("res_")
    assert all(ch in "0123456789ABCDEFGHJKMNPQRSTVWXYZ" for ch in body)


def test_uri_parts_rebuild_round_trips():
    # The frozen grammar rebuilds the exact same URI from parsed parts (lossless),
    # which is the property mint_resource_id relies on for determinism.
    from schemas.nc_platform import NcUriValidator

    parts = validate_nc_uri(LAMP)
    rebuilt = NcUriValidator().build(
        parts.namespace, parts.provider, parts.scope, parts.kind, parts.resource_id
    )
    assert rebuilt == LAMP


# ---------------------------------------------------------------------------
# Instance registration
# ---------------------------------------------------------------------------


async def test_upsert_instance_is_idempotent(db):
    sessions, svc = db
    async with sessions() as s:
        v1 = await svc.upsert_instance(
            s, instance_id=CONN, provider="homeassistant", credentials_ref="vault://nc"
        )
        v2 = await svc.upsert_instance(s, instance_id=CONN, provider="homeassistant")
        assert v1.instance_id == v2.instance_id == CONN
        assert v2.health == "healthy"
        rows = (await s.execute(select(NCConnectorInstanceRow))).scalars().all()
        assert len(rows) == 1


async def test_get_instance_missing_raises(db):
    sessions, svc = db
    async with sessions() as s:
        with pytest.raises(RegistryConnectorNotFound):
            await svc.get_instance(s, instance_id="conn_BBBBBBBBBBBBBBBBBBBBBBBB")


# ---------------------------------------------------------------------------
# Reconciliation: idempotence, updates, snapshots
# ---------------------------------------------------------------------------


async def test_reconcile_creates_rows_and_is_idempotent_on_rerun(db):
    sessions, svc = db
    async with sessions() as s:
        batch = [_sighting(u, u.rsplit("/", 1)[1]) for u in (LAMP, PLUG, FLOW)]
        out1 = await svc.reconcile(s, instance_id=CONN, sightings=batch)
        assert all(o.created for o in out1)
        assert {o.resource_id for o in out1} == {
            mint_resource_id(u) for u in (LAMP, PLUG, FLOW)
        }
        out2 = await svc.reconcile(s, instance_id=CONN, sightings=batch)
        assert not any(o.created for o in out2)
        assert not any(o.changed for o in out2)
        rows = (await s.execute(select(NCResourceRow))).scalars().all()
        assert len(rows) == 3
        snaps = (await s.execute(select(NCResourceSnapshotRow))).scalars().all()
        assert len(snaps) == 3


async def test_reconcile_update_writes_single_new_snapshot(db):
    sessions, svc = db
    async with sessions() as s:
        await svc.reconcile(s, instance_id=CONN, sightings=[_sighting(LAMP, "bedroom-lamp")])
        await svc.reconcile(
            s,
            instance_id=CONN,
            sightings=[
                _sighting(LAMP, "bedroom-lamp", display_name="Lamp v2", observed_state={"on": False})
            ],
        )
        snaps = (await s.execute(select(NCResourceSnapshotRow))).scalars().all()
        assert len(snaps) == 2, [sn.state for sn in snaps]
        view = await svc.get_resource(s, uri=LAMP)
        assert view["display_name"] == "Lamp v2"
        assert view["observed_state"] == {"on": False}
        assert view["sync_status"] == "current"


async def test_reconcile_accepts_dict_sightings_and_preserves_provider_id(db):
    sessions, svc = db
    async with sessions() as s:
        # Provider-native ids may contain '/' (path-escaped in the URI); the
        # stored provider_resource_id is preserved verbatim, never re-minted.
        uri = "nc://personal/gmail/inbox/threads/abc%2Fdef"
        parts = validate_nc_uri(uri)
        assert parts.resource_id == "abc%2Fdef"
        await svc.reconcile(
            s,
            instance_id=CONN,
            sightings=[
                {"uri": uri, "provider_resource_id": parts.resource_id, "display_name": "T"}
            ],
        )
        row = (
            await s.execute(select(NCResourceRow).where(NCResourceRow.uri == uri))
        ).scalar_one()
        assert row.provider_resource_id == parts.resource_id
        assert row.provider == "gmail"
        assert row.kind == "threads"
        assert row.namespace == "personal"


async def test_reconcile_without_registered_instance_raises(db):
    sessions, svc = db
    async with sessions() as s:
        with pytest.raises(RegistryConnectorNotFound):
            await svc.reconcile(s, instance_id="conn_BBBBBBBBBBBBBBBBBBBBBBBB", sightings=[])


async def test_reconcile_rejects_non_canonical_uri(db):
    sessions, svc = db
    async with sessions() as s:
        for bad in (
            "http://personal/x/y/z/1",  # wrong scheme
            "NC://personal/x/y/z/1",  # case-sensitive scheme
            "nc://personal/x/y/1",  # too few segments
            "nc://__system/x/y/z/1",  # reserved segment
            "nc://personal/x/y/z/1?x=1",  # query forbidden
        ):
            with pytest.raises(RegistryUriError):
                await svc.reconcile(
                    s, instance_id=CONN, sightings=[_sighting(bad, "1")]
                )


# ---------------------------------------------------------------------------
# Tombstones: explicit deletion only
# ---------------------------------------------------------------------------


async def test_delete_resource_tombstones_and_retains_row(db):
    sessions, svc = db
    async with sessions() as s:
        await svc.reconcile(s, instance_id=CONN, sightings=[_sighting(PLUG, "kitchen-plug")])
        out = await svc.delete_resource(s, instance_id=CONN, uri=PLUG)
        assert out.tombstoned is True
        assert out.created is False
        # Invisible to live reads...
        with pytest.raises(RegistryResourceNotFound):
            await svc.get_resource(s, uri=PLUG)
        # ...but the row is physically retained (tombstoned, never deleted).
        rows = (await s.execute(select(NCResourceRow))).scalars().all()
        assert len(rows) == 1
        assert rows[0].sync_status == "tombstoned"
        # Re-tombstone is a no-op with changed=False (idempotent).
        out2 = await svc.delete_resource(s, instance_id=CONN, uri=PLUG)
        assert out2.changed is False


async def test_deleted_sighting_in_batch_tombstones(db):
    sessions, svc = db
    async with sessions() as s:
        await svc.reconcile(s, instance_id=CONN, sightings=[_sighting(PLUG, "kitchen-plug")])
        out = await svc.reconcile(
            s,
            instance_id=CONN,
            sightings=[_sighting(PLUG, "kitchen-plug", deleted=True)],
        )
        assert out[0].tombstoned is True
        with pytest.raises(RegistryResourceNotFound):
            await svc.get_resource(s, uri=PLUG)
        row = (await s.execute(select(NCResourceRow).where(NCResourceRow.uri == PLUG))).scalar_one()
        assert row.sync_status == "tombstoned"


async def test_absence_from_batch_is_not_deletion(db):
    """A sighting simply missing from a later batch must NOT be tombstoned."""
    sessions, svc = db
    async with sessions() as s:
        await svc.reconcile(
            s,
            instance_id=CONN,
            sightings=[_sighting(LAMP, "bedroom-lamp"), _sighting(PLUG, "kitchen-plug")],
        )
        # Next batch only sees the lamp; the plug is left untouched.
        await svc.reconcile(s, instance_id=CONN, sightings=[_sighting(LAMP, "bedroom-lamp")])
        plug = (await s.execute(select(NCResourceRow).where(NCResourceRow.uri == PLUG))).scalar_one()
        assert plug.sync_status == "current"
        assert await svc.get_resource(s, uri=PLUG) is not None


# ---------------------------------------------------------------------------
# Outage / health semantics
# ---------------------------------------------------------------------------


async def test_outage_ages_to_stale_never_tombstones(db):
    sessions, svc = db
    async with sessions() as s:
        await svc.reconcile(
            s,
            instance_id=CONN,
            sightings=[_sighting(LAMP, "bedroom-lamp"), _sighting(PLUG, "kitchen-plug")],
        )
        n = await svc.record_outage(s, instance_id=CONN, error="502")
        assert n == 2
        inst = await svc.get_instance(s, instance_id=CONN)
        assert inst.health == "unreachable"
        live = await svc.list_resources(s, include_tombstoned=True)
        assert {r["sync_status"] for r in live} == {"stale"}
        # Live reads still work; nothing was deleted.
        assert (await svc.get_resource(s, uri=LAMP))["sync_status"] == "stale"
        # Recovery: healthy again; staleness cleared by the next reconcile.
        await svc.record_healthy(s, instance_id=CONN)
        assert (await svc.get_instance(s, instance_id=CONN)).health == "healthy"
        await svc.reconcile(s, instance_id=CONN, sightings=[_sighting(LAMP, "bedroom-lamp")])
        assert (await svc.get_resource(s, uri=LAMP))["sync_status"] == "current"


async def test_outage_requires_known_instance(db):
    sessions, svc = db
    async with sessions() as s:
        with pytest.raises(RegistryConnectorNotFound):
            await svc.record_outage(s, instance_id="conn_BBBBBBBBBBBBBBBBBBBBBBBB")


async def test_sync_health_reports_staleness(db):
    sessions, svc = db
    async with sessions() as s:
        # One fresh sighting, one old sighting (observed an hour ago).
        await svc.reconcile(s, instance_id=CONN, sightings=[_sighting(LAMP, "bedroom-lamp")])
        await svc.reconcile(
            s,
            instance_id=CONN,
            sightings=[
                _sighting(PLUG, "kitchen-plug", observed_at=NOW.replace(hour=10))
            ],
        )
        health = await svc.sync_health(s)
        by_id = {i["instance_id"]: i for i in health["instances"]}
        inst = by_id[CONN]
        assert inst["resources"] == 2
        assert sorted(health["stale_resources"]) == [PLUG], health["stale_resources"]
        assert health["stale_after_seconds"] == 3600


# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------


async def test_alias_lifecycle(db):
    sessions, svc = db
    async with sessions() as s:
        await svc.reconcile(s, instance_id=CONN, sightings=[_sighting(LAMP, "bedroom-lamp")])
        alias_uri = "nc://personal/homeassistant/home/devices/lamp"
        a1 = await svc.add_alias(s, uri=LAMP, alias_uri=alias_uri)
        assert a1["created"] is True
        a2 = await svc.add_alias(s, uri=LAMP, alias_uri=alias_uri)
        assert a2["created"] is False
        resolved = await svc.resolve_alias(s, alias_uri=alias_uri)
        assert resolved is not None and resolved["uri"] == LAMP
        assert await svc.resolve_alias(s, alias_uri="nc://personal/homeassistant/home/devices/nope") is None
        listed = await svc.list_aliases(s, uri=LAMP)
        assert [a["alias_uri"] for a in listed] == [alias_uri]


async def test_alias_of_tombstoned_resource_does_not_resolve(db):
    sessions, svc = db
    async with sessions() as s:
        await svc.reconcile(s, instance_id=CONN, sightings=[_sighting(PLUG, "kitchen-plug")])
        alias_uri = "nc://personal/homeassistant/home/devices/plug"
        await svc.add_alias(s, uri=PLUG, alias_uri=alias_uri)
        await svc.delete_resource(s, instance_id=CONN, uri=PLUG)
        assert await svc.resolve_alias(s, alias_uri=alias_uri) is None
        # The alias row itself is retained (historical resolution), not deleted.
        alias_rows = (await s.execute(select(NCResourceAliasRow))).scalars().all()
        assert len(alias_rows) == 1


async def test_add_alias_to_unknown_resource_raises(db):
    sessions, svc = db
    async with sessions() as s:
        with pytest.raises(RegistryResourceNotFound):
            await svc.add_alias(s, uri=LAMP, alias_uri="nc://personal/homeassistant/home/devices/lamp")


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------


async def test_relations_idempotent_and_directional(db):
    sessions, svc = db
    async with sessions() as s:
        await svc.reconcile(
            s,
            instance_id=CONN,
            sightings=[_sighting(LAMP, "bedroom-lamp"), _sighting(FLOW, "morning")],
        )
        r1 = await svc.create_relation(
            s, source_uri=FLOW, target_uri=LAMP, relation_type="triggers", evidence=("ev1",)
        )
        assert r1["created"] is True
        r2 = await svc.create_relation(
            s, source_uri=FLOW, target_uri=LAMP, relation_type="triggers"
        )
        assert r2["created"] is False
        incoming = await svc.list_relations(s, uri=LAMP, direction="incoming")
        outgoing = await svc.list_relations(s, uri=LAMP, direction="outgoing")
        assert len(incoming) == 1 and len(outgoing) == 0
        assert incoming[0]["relation_type"] == "triggers"
        with pytest.raises(RegistryError):
            await svc.list_relations(s, uri=LAMP, direction="sideways")


async def test_relation_requires_live_endpoints(db):
    sessions, svc = db
    async with sessions() as s:
        await svc.reconcile(s, instance_id=CONN, sightings=[_sighting(LAMP, "bedroom-lamp")])
        with pytest.raises(RegistryResourceNotFound):
            await svc.create_relation(s, source_uri=LAMP, target_uri=PLUG, relation_type="near")


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def test_get_and_list_resources(db):
    sessions, svc = db
    async with sessions() as s:
        await svc.reconcile(
            s,
            instance_id=CONN,
            sightings=[_sighting(LAMP, "bedroom-lamp"), _sighting(PLUG, "kitchen-plug")],
        )
        view = await svc.get_resource(s, uri=LAMP)
        assert view["resource_id"] == mint_resource_id(LAMP)
        assert view["provider"] == "homeassistant"
        assert view["kind"] == "devices"
        by_key = await svc.get_resource_by_provider_id(s, instance_id=CONN, provider_resource_id="bedroom-lamp")
        assert by_key is not None and by_key["uri"] == LAMP
        assert await svc.get_resource_by_provider_id(s, instance_id=CONN, provider_resource_id="nope") is None
        listed = await svc.list_resources(s, instance_id=CONN)
        assert len(listed) == 2
