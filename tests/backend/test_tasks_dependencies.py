"""Tests for the ``tasks.dependencies`` schema-drift fix (audit-gaps U-5).

The ``Task`` ORM model declares ``dependencies`` as a non-nullable JSONB column
(``backend/persistence/models/tasks.py``), but ``001_initial`` created the
``tasks`` table *without* that column. Any ``SELECT`` that reads the whole row
(e.g. ``GET /api/tasks`` -> ``TaskService.list_tasks``) therefore raised
``sqlalchemy.exc.ProgrammingError: column tasks.dependencies does not exist``.

The fix is a new alembic revision, ``003_tasks_dependencies``
(``backend/persistence/alembic/versions/003_tasks_dependencies.py``), on the
existing ``001_initial -> 002_auth`` chain, applied by
``python -m backend.persistence.migrate upgrade head`` (the migrate-job).

These tests prove, on a real SQLite scratch DB (``sqlite+aiosqlite``):
  1. the model declares ``dependencies`` (correct type, NOT NULL);
  2. the migration actually adds the column to a DB left at the prior head
     (002_auth) by the real ``alembic command.upgrade`` path;
  3. ``GET /api/tasks`` returns 200 with the ``dependencies`` field present;
  4. ``TaskService.list_tasks`` returns a schema carrying ``dependencies``.
"""

from __future__ import annotations

import pathlib

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from backend.api.endpoints import tasks as tasks_endpoints
from backend.persistence.models.tasks import Task
from backend.tasks.service import TaskService

_ALEMBIC_DIR = pathlib.Path(__file__).resolve().parents[2] / "backend" / "persistence" / "alembic"


def _alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _seed_drift_db(db_path: pathlib.Path) -> None:
    """Create a ``tasks`` table exactly as ``001_initial`` left it: NO
    ``dependencies`` column, and stamp alembic at the prior head ``002_auth``
    so a subsequent ``upgrade head`` applies *only* revision 003.
    """

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        # tasks table as 001_initial created it (minus dependencies).
        conn.execute(
            text(
                """
                CREATE TABLE tasks (
                    id VARCHAR NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    schema_version VARCHAR(16) NOT NULL,
                    hash VARCHAR(64),
                    title VARCHAR NOT NULL,
                    description VARCHAR,
                    status VARCHAR(32) NOT NULL,
                    priority BIGINT NOT NULL,
                    goal_id VARCHAR,
                    decision_id VARCHAR,
                    assignee_agent_id VARCHAR,
                    due_at TIMESTAMP WITH TIME ZONE,
                    scheduled_at TIMESTAMP WITH TIME ZONE,
                    inputs JSONB NOT NULL,
                    parent_task_id VARCHAR,
                    PRIMARY KEY (id)
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, "
                "CONSTRAINT pk_alembic_version PRIMARY KEY (version_num))"
            )
        )
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('002_auth')"))
    engine.dispose()


# ---------------------------------------------------------------------------
# 1. The model declares dependencies
# ---------------------------------------------------------------------------


def test_model_declares_dependencies_column():
    col = Task.__table__.c.get("dependencies")
    assert col is not None, "Task model must declare a `dependencies` column"
    assert col.type.__class__ is JSONB, f"expected JSONB, got {col.type!r}"
    assert col.nullable is False, "`dependencies` must be NOT NULL on the model"


# ---------------------------------------------------------------------------
# 2. The migration adds the column
# ---------------------------------------------------------------------------


def test_migration_adds_dependencies_column(tmp_path):
    db_path = tmp_path / "tasks_drift.db"
    _seed_drift_db(db_path)

    # Before the migration: the column is absent.
    pre = create_engine(f"sqlite:///{db_path}")
    with pre.connect() as c:
        pre_cols = {r[1] for r in c.execute(text("PRAGMA table_info(tasks)"))}
    pre.dispose()
    assert "dependencies" not in pre_cols

    # Run the real alembic upgrade (applies only 003 — pinned to that
    # revision so later migrations, e.g. 004, don't shift the head).
    command.upgrade(
        _alembic_config(f"sqlite:///{db_path}"), "003_tasks_dependencies"
    )

    post = create_engine(f"sqlite:///{db_path}")
    with post.connect() as c:
        post_cols = {r[1] for r in c.execute(text("PRAGMA table_info(tasks)"))}
        version = c.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    post.dispose()
    assert "dependencies" in post_cols, "migration 003 must add tasks.dependencies"
    assert version == "003_tasks_dependencies"


# ---------------------------------------------------------------------------
# 3. GET /api/tasks returns 200 with dependencies present
# ---------------------------------------------------------------------------


@pytest.fixture
async def migrated_engine(tmp_path):
    """An async engine over a scratch DB migrated to head (003)."""
    db_path = tmp_path / "drift.db"
    _seed_drift_db(db_path)
    command.upgrade(_alembic_config(f"sqlite:///{db_path}"), "head")
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=StaticPool)
    yield eng
    await eng.dispose()


async def test_get_tasks_returns_200_with_dependencies(migrated_engine):
    service = TaskService(migrated_engine)
    # Seed through the real write path (generates id/created_at).
    await service.create(
        {"title": "provision node", "dependencies": ["task-a", "task-b"], "inputs": {"k": 1}}
    )

    app = FastAPI()
    app.include_router(tasks_endpoints.router)
    app.state.services = {"tasks": service}

    with TestClient(app) as client:
        resp = client.get("/api/tasks")

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    # Count lives under meta.pagination (ApiResponseMeta), not meta.total.
    assert body["meta"]["pagination"]["total"] == 1
    row = body["data"][0]
    assert "dependencies" in row, "`dependencies` must be present in GET /api/tasks rows"
    assert row["dependencies"] == ["task-a", "task-b"]


# ---------------------------------------------------------------------------
# 4. Service list path returns the field
# ---------------------------------------------------------------------------


async def test_service_list_returns_dependencies(migrated_engine):
    service = TaskService(migrated_engine)
    await service.create({"title": "unit", "dependencies": ["x"]})

    rows = await service.list_tasks()
    assert len(rows) == 1
    assert rows[0].dependencies == ["x"]
