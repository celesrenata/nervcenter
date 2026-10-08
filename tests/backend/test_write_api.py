"""T-H33 / D-H33: Write/mutation API without fake success.

This test file verifies the fix for the fake-success bug where the generic
`make_write_endpoint` helper returned HTTP 202 ``{"accepted": true, "executed": false}``
even when no persistence/service was configured. Now:

- Supported entities (Goal, Task, Entity, Relationship) return **503** (service not
  configured) or **501** (unsupported) rather than a fake 202 acceptance.

- Real service-backed endpoints use the in-memory SQLite engine with
  `StaticPool` for full end-to-end persistence testing.

Contract (spec §46 + MCP tools):
- Supported + unconfigured (no NERVE_DB_URL):
  - Writes → 503 "service not configured", honest 200 empty for reads.
- Unsupported writes (claims, agents/pause):
  - POST → 501 "not implemented" (not a fake 202).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from backend.api.app import create_app
from backend.goals.service import GoalService
from backend.knowledge.entity import EntityService
from backend.persistence.models import Goal as GoalORM, Entity as EntityORM, Task as TaskORM, Relationship as RelationshipORM


@pytest.fixture
async def async_engine():
    """In-memory SQLite async engine with all write tables created."""
    eng = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    yield eng
    await eng.dispose()


@pytest.fixture
async def goal_service(async_engine):
    """GoalService bound to in-memory SQLite."""
    return GoalService(async_engine)


@pytest.fixture
async def task_service(async_engine):
    """TaskService bound to in-memory SQLite."""
    from backend.tasks.service import TaskService
    return TaskService(async_engine)


@pytest.fixture
async def entity_service(async_engine):
    """EntityService bound to in-memory SQLite."""
    return EntityService(async_engine)


@pytest.fixture
async def relationship_service(async_engine):
    """RelationshipService bound to in-memory SQLite."""
    from backend.knowledge.relationship import RelationshipService
    return RelationshipService(async_engine)


@pytest.fixture
async def app_with_goals(async_engine, goal_service):
    """FastAPI app with goals service wired via app.state.services."""
    app = FastAPI()
    from backend.api.endpoints import goals
    app.include_router(goals.router)
    app.state.services = {"goals": goal_service}
    return app


@pytest.fixture
async def app_with_entities(async_engine, entity_service):
    """FastAPI app with entities service wired."""
    app = FastAPI()
    from backend.api.endpoints import entities
    app.include_router(entities.router)
    app.state.services = {"entities": entity_service}
    return app


# ---------------------------------------------------------------------------
# Unconfigured state (no NERVE_DB_URL) — should return honest errors
# ---------------------------------------------------------------------------


class TestUnconfiguredWriteRoutes:
    """Confirm unconfigured write routes return honest 503/501 (no fake 202)."""

    def test_goals_create_returns_503(self):
        with TestClient(create_app()) as client:
            # No NERVE_DB_URL → goals service not in app.state.services
            resp = client.post("/api/goals", json={"title": "Test"})
            assert resp.status_code == 503
            assert "service not configured" in resp.json()["detail"]

    def test_tasks_create_returns_503(self):
        with TestClient(create_app()) as client:
            resp = client.post("/api/tasks", json={"title": "Test"})
            assert resp.status_code == 503

    def test_entities_create_returns_503(self):
        with TestClient(create_app()) as client:
            resp = client.post("/api/entities", json={"entity_type": "person", "name": "Ada"})
            assert resp.status_code == 503

    def test_relationships_create_returns_503(self):
        with TestClient(create_app()) as client:
            resp = client.post("/api/relationships", json={
                "source_entity_id": "a", "target_entity_id": "b", "relation_type": "related_to"
            })
            assert resp.status_code == 503

    def test_claims_create_returns_501(self):
        """Claims POST → honest 501 (unsupported)."""
        with TestClient(create_app()) as client:
            resp = client.post("/api/claims", json={"statement": "test"})
            assert resp.status_code == 501

    def test_agents_pause_returns_501(self):
        """Agents/pause → honest 501 (no mutation persistence)."""
        with TestClient(create_app()) as client:
            resp = client.post("/api/agents/pause", json={})
            assert resp.status_code == 501


class TestUnconfiguredReadRoutes:
    """Confirm unconfigured read routes return honest 200 empty."""

    def test_goals_list_returns_200_empty(self):
        with TestClient(create_app()) as client:
            resp = client.get("/api/goals")
            assert resp.status_code == 200
            assert resp.json()["data"] == []

    def test_tasks_list_returns_200_empty(self):
        with TestClient(create_app()) as client:
            resp = client.get("/api/tasks")
            assert resp.status_code == 200
            assert resp.json()["data"] == []

    def test_entities_list_returns_200_empty(self):
        with TestClient(create_app()) as client:
            resp = client.get("/api/entities")
            assert resp.status_code == 200
            assert resp.json()["data"] == []

    def test_relationships_list_returns_200_empty(self):
        with TestClient(create_app()) as client:
            resp = client.get("/api/relationships")
            assert resp.status_code == 200
            assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# Service-backed write routes (SQLite, full persistence)
# ---------------------------------------------------------------------------


class TestGoalServiceWrite:
    """GoalService-backed write endpoints via SQLite."""

    async def test_create_persists_goal(self, async_engine, goal_service):
        app = FastAPI()
        from backend.api.endpoints import goals
        app.include_router(goals.router)
        app.state.services = {"goals": goal_service}
        async with async_engine.begin() as conn:
            await conn.run_sync(GoalORM.__table__.create)

        with TestClient(app) as client:
            resp = client.post("/api/goals", json={"title": "Test Goal", "criteria": ["x"]})
            assert resp.status_code == 201
            data = resp.json()
            assert data["title"] == "Test Goal"
            assert data["status"] == "active"
            assert data["progress"] == 0.0

    async def test_get_returns_persisted_goal(self, async_engine, goal_service):
        app = FastAPI()
        from backend.api.endpoints import goals
        app.include_router(goals.router)
        app.state.services = {"goals": goal_service}
        async with async_engine.begin() as conn:
            await conn.run_sync(GoalORM.__table__.create)

        with TestClient(app) as client:
            # Create
            create_resp = client.post("/api/goals", json={"title": "G"})
            goal_id = create_resp.json()["id"]
            # Get
            get_resp = client.get(f"/api/goals/{goal_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["title"] == "G"

    async def test_update_applies_changes(self, async_engine, goal_service):
        app = FastAPI()
        from backend.api.endpoints import goals
        app.include_router(goals.router)
        app.state.services = {"goals": goal_service}
        async with async_engine.begin() as conn:
            await conn.run_sync(GoalORM.__table__.create)

        with TestClient(app) as client:
            create_resp = client.post("/api/goals", json={"title": "G"})
            goal_id = create_resp.json()["id"]
            update_resp = client.post(f"/api/goals/{goal_id}", json={"progress": 0.5, "status": "paused"})
            assert update_resp.status_code == 200
            data = update_resp.json()
            assert data["progress"] == 0.5
            assert data["status"] == "paused"

    async def test_delete_removes_goal(self, async_engine, goal_service):
        app = FastAPI()
        from backend.api.endpoints import goals
        app.include_router(goals.router)
        app.state.services = {"goals": goal_service}
        async with async_engine.begin() as conn:
            await conn.run_sync(GoalORM.__table__.create)

        with TestClient(app) as client:
            create_resp = client.post("/api/goals", json={"title": "G"})
            goal_id = create_resp.json()["id"]
            delete_resp = client.delete(f"/api/goals/{goal_id}")
            assert delete_resp.status_code == 204
            # Verify deletion
            get_resp = client.get(f"/api/goals/{goal_id}")
            assert get_resp.status_code == 404

    async def test_404_for_unknown_goal(self, async_engine, goal_service):
        app = FastAPI()
        from backend.api.endpoints import goals
        app.include_router(goals.router)
        app.state.services = {"goals": goal_service}
        async with async_engine.begin() as conn:
            await conn.run_sync(GoalORM.__table__.create)

        with TestClient(app) as client:
            resp = client.get("/api/goals/unknown-id")
            assert resp.status_code == 404

    async def test_404_on_delete_unknown(self, async_engine, goal_service):
        app = FastAPI()
        from backend.api.endpoints import goals
        app.include_router(goals.router)
        app.state.services = {"goals": goal_service}
        async with async_engine.begin() as conn:
            await conn.run_sync(GoalORM.__table__.create)

        with TestClient(app) as client:
            resp = client.delete("/api/goals/unknown")
            assert resp.status_code == 404


class TestEntityServiceWrite:
    """EntityService-backed write endpoints via SQLite."""

    async def test_create_persists_entity(self, async_engine, entity_service):
        app = FastAPI()
        from backend.api.endpoints import entities
        app.include_router(entities.router)
        app.state.services = {"entities": entity_service}
        async with async_engine.begin() as conn:
            await conn.run_sync(EntityORM.__table__.create)

        with TestClient(app) as client:
            resp = client.post("/api/entities", json={
                "entity_type": "person",
                "name": "Ada Lovelace",
                "description": "Mathematician",
                "attributes": {"a": 1},
            })
            assert resp.status_code == 201
            data = resp.json()
            assert data["entity_type"] == "person"
            assert data["name"] == "Ada Lovelace"
            assert data["attributes"] == {"a": 1}

    async def test_get_returns_persisted_entity(self, async_engine, entity_service):
        app = FastAPI()
        from backend.api.endpoints import entities
        app.include_router(entities.router)
        app.state.services = {"entities": entity_service}
        async with async_engine.begin() as conn:
            await conn.run_sync(EntityORM.__table__.create)

        with TestClient(app) as client:
            create_resp = client.post("/api/entities", json={"entity_type": "person", "name": "Ada"})
            entity_id = create_resp.json()["id"]
            get_resp = client.get(f"/api/entities/{entity_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["name"] == "Ada"

    async def test_409_on_name_conflict(self, async_engine, entity_service):
        app = FastAPI()
        from backend.api.endpoints import entities
        app.include_router(entities.router)
        app.state.services = {"entities": entity_service}
        async with async_engine.begin() as conn:
            await conn.run_sync(EntityORM.__table__.create)

        with TestClient(app) as client:
            client.post("/api/entities", json={"entity_type": "person", "name": "Ada"})
            resp = client.post("/api/entities", json={"entity_type": "person", "name": "Ada"})
            assert resp.status_code == 409


class TestTaskServiceWrite:
    """TaskService-backed write endpoints via SQLite."""

    async def test_create_persists_task(self, async_engine, task_service):
        from backend.persistence.models import Task as TaskORM, Goal as GoalORM
        from backend.goals.service import GoalService
        app = FastAPI()
        from backend.api.endpoints import tasks, goals
        app.include_router(tasks.router)
        app.include_router(goals.router)
        app.state.services = {
            "tasks": task_service,
            "goals": GoalService(async_engine)
        }
        async with async_engine.begin() as conn:
            await conn.run_sync(GoalORM.__table__.create)
            await conn.run_sync(TaskORM.__table__.create)

        with TestClient(app) as client:
            # Create a goal first (tasks require goal_id)
            goal_resp = client.post("/api/goals", json={"title": "G"})
            goal_id = goal_resp.json()["id"]
            resp = client.post("/api/tasks", json={
                "title": "T",
                "priority": 3,
                "goal_id": goal_id,
            })
            assert resp.status_code == 201
            data = resp.json()
            assert data["title"] == "T"
            assert data["priority"] == 3
            assert data["status"] == "pending"

    async def test_complete_task(self, async_engine, task_service):
        from backend.persistence.models import Task as TaskORM, Goal as GoalORM
        from backend.goals.service import GoalService
        app = FastAPI()
        from backend.api.endpoints import tasks, goals
        app.include_router(tasks.router)
        app.include_router(goals.router)
        app.state.services = {
            "tasks": task_service,
            "goals": GoalService(async_engine),
        }
        async with async_engine.begin() as conn:
            await conn.run_sync(GoalORM.__table__.create)
            await conn.run_sync(TaskORM.__table__.create)

        with TestClient(app) as client:
            # Create goal and task
            goal_resp = client.post("/api/goals", json={"title": "G"})
            goal_id = goal_resp.json()["id"]
            task_resp = client.post("/api/tasks", json={"title": "T", "goal_id": goal_id})
            task_id = task_resp.json()["id"]
            # Complete via update
            resp = client.post(f"/api/tasks/{task_id}", json={"status": "completed"})
            assert resp.status_code == 200
            assert resp.json()["status"] == "completed"
