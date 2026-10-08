"""Round-3 write-route coverage (gap-closure integration).

Covers the routes added in round 3 (IN-1 / AG-3):

- ``POST /api/incidents``                 — create (201); invalid severity → 422
- ``POST /api/incidents/{id}/resolve``    — active|in-progress → resolved (200)
- ``POST /api/incidents/{id}/close``      — active|in-progress|resolved → closed (200, terminal)
- illegal transitions (e.g. resolve/close a closed incident) → **409**
- ``POST /api/agents``                    — create (201); duplicate name → **409**
- honest degradation with no DB engine configured → 503 (no fake 201/202)

Pattern follows :mod:`tests.backend.test_write_api` (in-memory SQLite +
StaticPool, ``app.state.db_engine``).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from backend.api.endpoints import agents as agents_ep
from backend.api.endpoints import incidents as incidents_ep
from backend.persistence.models import Agent as AgentORM
from backend.persistence.models import Incident as IncidentORM


@pytest.fixture
async def async_engine():
    """In-memory SQLite async engine; creates the round-3 tables."""
    eng = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with eng.begin() as conn:
        await conn.run_sync(IncidentORM.__table__.create)
        await conn.run_sync(AgentORM.__table__.create)
    yield eng
    await eng.dispose()


@pytest.fixture
async def app_with_db(async_engine):
    """App with the incidents + agents routers, DB engine wired."""
    app = FastAPI()
    app.include_router(incidents_ep.router)
    app.include_router(agents_ep.router)
    app.state.db_engine = async_engine
    return app


def _create_incident(client: TestClient, **overrides) -> dict:
    payload = {
        "title": "Disk full on core node",
        "severity": "high",
        "description": "opration log rotation failed",
        "impact": "audit trail at risk",
        "tags": ["storage", "ops"],
    }
    payload.update(overrides)
    resp = client.post("/api/incidents", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestIncidentWriteRoutes:
    async def test_create_persists_and_lists(self, app_with_db):
        with TestClient(app_with_db) as client:
            row = _create_incident(client)
            assert row["id"]
            assert row["status"] == "active"
            assert row["severity"] == "high"
            assert row["title"] == "Disk full on core node"
            assert row["tags"] == ["storage", "ops"]

            listing = client.get("/api/incidents")
            assert listing.status_code == 200
            ids = [i["id"] for i in listing.json()["data"]]
            assert row["id"] in ids

    async def test_invalid_severity_is_422(self, app_with_db):
        with TestClient(app_with_db) as client:
            resp = client.post("/api/incidents", json={"title": "x", "severity": "bogus"})
            assert resp.status_code == 422

    async def test_resolve_from_active(self, app_with_db):
        with TestClient(app_with_db) as client:
            iid = _create_incident(client)["id"]
            resp = client.post(f"/api/incidents/{iid}/resolve")
            assert resp.status_code == 200
            assert resp.json()["status"] == "resolved"

    async def test_close_from_active_and_resolved(self, app_with_db):
        with TestClient(app_with_db) as client:
            # active -> close (direct)
            iid = _create_incident(client)["id"]
            resp = client.post(f"/api/incidents/{iid}/close")
            assert resp.status_code == 200
            assert resp.json()["status"] == "closed"

            # active -> resolve -> close
            iid2 = _create_incident(client, title="second")["id"]
            assert client.post(f"/api/incidents/{iid2}/resolve").status_code == 200
            resp = client.post(f"/api/incidents/{iid2}/close")
            assert resp.status_code == 200
            assert resp.json()["status"] == "closed"

    async def test_closed_is_terminal_409(self, app_with_db):
        with TestClient(app_with_db) as client:
            iid = _create_incident(client)["id"]
            assert client.post(f"/api/incidents/{iid}/close").status_code == 200

            # Reopening a closed incident is illegal -> 409 (not a silent accept)
            for path in (f"/api/incidents/{iid}/resolve", f"/api/incidents/{iid}/close"):
                resp = client.post(path)
                assert resp.status_code == 409, f"{path} expected 409, got {resp.status_code}"

    async def test_resolve_twice_is_409(self, app_with_db):
        with TestClient(app_with_db) as client:
            iid = _create_incident(client)["id"]
            assert client.post(f"/api/incidents/{iid}/resolve").status_code == 200
            resp = client.post(f"/api/incidents/{iid}/resolve")
            assert resp.status_code == 409

    async def test_transitions_unknown_incident_404(self, app_with_db):
        with TestClient(app_with_db) as client:
            assert client.post("/api/incidents/does-not-exist/resolve").status_code == 404
            assert client.post("/api/incidents/does-not-exist/close").status_code == 404


class TestAgentWriteRoutes:
    async def test_create_persists(self, app_with_db):
        with TestClient(app_with_db) as client:
            resp = client.post(
                "/api/agents",
                json={
                    "name": "sentinel",
                    "type": "guard",
                    "description": "watches the event bus",
                    "tools": ["scan", "alert"],
                },
            )
            assert resp.status_code == 201, resp.text
            row = resp.json()
            assert row["id"]
            assert row["name"] == "sentinel"
            assert row["type"] == "guard"
            assert row["status"] == "active"
            assert row["tools"] == ["scan", "alert"]

    async def test_duplicate_name_is_409(self, app_with_db):
        with TestClient(app_with_db) as client:
            assert client.post("/api/agents", json={"name": "sentinel", "type": "guard"}).status_code == 201
            resp = client.post("/api/agents", json={"name": "sentinel", "type": "watcher"})
            assert resp.status_code == 409, resp.text


class TestHonestDegradationUnconfigured:
    """No db_engine wired -> 503, never a fake 201."""

    async def test_incident_create_503(self):
        app = FastAPI()
        app.include_router(incidents_ep.router)
        with TestClient(app) as client:
            resp = client.post("/api/incidents", json={"title": "no db"})
            assert resp.status_code == 503

    async def test_incident_transition_503(self):
        app = FastAPI()
        app.include_router(incidents_ep.router)
        with TestClient(app) as client:
            assert client.post("/api/incidents/xyz/resolve").status_code == 503

    async def test_agent_create_503(self):
        app = FastAPI()
        app.include_router(agents_ep.router)
        with TestClient(app) as client:
            resp = client.post("/api/agents", json={"name": "nope", "type": "guard"})
            assert resp.status_code == 503
