"""Tests for startup wiring of the DB engine and NATS client onto ``app.state``.

No live database or NATS server is used: the DB probe is replaced with a
monkeypatched ``backend.persistence.connection.check_health``, and the NATS
environment is left unset so no connection is ever attempted.  The
``TestClient`` context manager triggers the ``@app.on_event("startup")`` /
``("shutdown")`` handlers, exercising the wiring and teardown paths.

Environment contract under test: ``NERVE_DB_URL`` (deploy contract) takes
precedence, with fallback to the legacy ``NERVECENTER_DATABASE_URL``.

Gap-closure addition: ``_build_and_connect_nats`` must now also call
``NatsClient.ensure_stream()`` during API startup so the JetStream stream
``NERVECENTER_EVENTS`` exists in the API deploy path (previously it was only
created by the standalone ``backend.events`` entrypoint, leaving
``GET /api/events`` / ``WS /api/events/ws`` in a permanent honest-503 state).
The fake NATS below records calls and proves the success and the
degradation (stream creation fails → startup still succeeds, honest 503
reads are preserved) without touching a real server.
"""

import asyncio
import warnings
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from backend.api.app import app as module_app
from backend.api.app import create_app
from backend.evidence.service import EvidenceService
from backend.goals.service import GoalService
from backend.knowledge.entity import EntityService
from backend.knowledge.relationship import RelationshipService
from backend.tasks.service import TaskService

ENV_NAMES = (
    "NERVE_DB_URL",
    "NERVECENTER_DATABASE_URL",
    "NERVE_NATS_URL",
    "NERVECENTER_NATS_URL",
)

FAKE_DB_URL = "postgresql+asyncpg://x:x@127.0.0.1:59999/x"


def _clear_dependency_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every DB/NATS URL env var so tests start from a clean slate."""
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


class _FakeOkReport:
    """Stand-in for :class:`backend.persistence.connection.HealthReport`."""

    ok = True

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "healthy",
            "ok": True,
            "latency_ms": 1.0,
            "server_version": "fake",
            "database": "x",
            "pgvector_available": True,
            "pool": {"in_use": 0, "overflow": 0, "checkedout": 0},
            "error": None,
        }


@pytest.fixture
def fake_ok_health(monkeypatch: pytest.MonkeyPatch):
    """Monkeypatch ``check_health`` to return a fake ok report for any engine."""
    import backend.persistence.connection as connection

    async def _fake_check_health(engine):
        return _FakeOkReport()

    monkeypatch.setattr(connection, "check_health", _fake_check_health)


@pytest.fixture
def raising_health(monkeypatch: pytest.MonkeyPatch):
    """Monkeypatch ``check_health`` to raise, simulating a real probe failure."""
    import backend.persistence.connection as connection

    async def _raising_check_health(engine):
        raise RuntimeError("probe failed on purpose")

    monkeypatch.setattr(connection, "check_health", _raising_check_health)


class TestHealthWiring:
    """``GET /api/health`` against the module-level ``app``."""

    def test_db_ok_when_env_set_and_probe_ok(self, monkeypatch, fake_ok_health):
        """Env DB URL set + healthy probe → ``checks.db.status == 'ok'``."""
        _clear_dependency_env(monkeypatch)
        monkeypatch.setenv("NERVE_DB_URL", FAKE_DB_URL)

        with TestClient(module_app) as client:
            response = client.get("/api/health")

        assert response.status_code == 200
        body = response.json()
        assert body["checks"]["db"]["status"] == "ok"

    def test_db_unreachable_when_probe_raises(self, monkeypatch, raising_health):
        """Env DB URL set + probe raises → 200 with ``unreachable``, no crash."""
        _clear_dependency_env(monkeypatch)
        monkeypatch.setenv("NERVE_DB_URL", FAKE_DB_URL)

        with TestClient(module_app) as client:
            response = client.get("/api/health")

        assert response.status_code == 200
        body = response.json()
        assert body["checks"]["db"]["status"] == "unreachable"
        assert body["checks"]["db"]["message"] == "probe failed on purpose"

    def test_degraded_not_configured_when_no_env(self, monkeypatch):
        """No DB/NATS URL env → 200, degraded, 'not configured' messages."""
        _clear_dependency_env(monkeypatch)

        with TestClient(module_app) as client:
            response = client.get("/api/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["checks"]["db"]["status"] == "unreachable"
        assert body["checks"]["db"]["message"] == "database is not configured"
        assert body["checks"]["nats"]["status"] == "unreachable"
        assert body["checks"]["nats"]["message"] == "NATS is not configured"

    def test_legacy_nervcenter_env_fallback(self, monkeypatch, fake_ok_health):
        """``NERVECENTER_DATABASE_URL`` alone still wires the engine (fallback)."""
        _clear_dependency_env(monkeypatch)
        monkeypatch.setenv("NERVECENTER_DATABASE_URL", FAKE_DB_URL)

        with TestClient(module_app) as client:
            response = client.get("/api/health")

        assert response.status_code == 200
        body = response.json()
        assert body["checks"]["db"]["status"] == "ok"


class TestCreateAppWiring:
    """``create_app()`` instances receive the same startup wiring."""

    def test_create_app_wires_db_engine(self, monkeypatch, fake_ok_health):
        """``create_app()`` + env DB URL → wired engine, health reports ok."""
        _clear_dependency_env(monkeypatch)
        monkeypatch.setenv("NERVE_DB_URL", FAKE_DB_URL)

        new_app = create_app()
        with TestClient(new_app) as client:
            response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["checks"]["db"]["status"] == "ok"

    def test_create_app_no_env_stays_unwired(self, monkeypatch):
        """``create_app()`` with no env → state stays None, probes say not configured."""
        _clear_dependency_env(monkeypatch)

        new_app = create_app()
        with TestClient(new_app) as client:
            assert client.app.state.db_engine is None
            assert client.app.state.nats_client is None
            response = client.get("/api/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["checks"]["db"]["message"] == "database is not configured"
        assert body["checks"]["nats"]["message"] == "NATS is not configured"


class TestServicesWiring:
    """``build_services`` is awaited so the write-path services land on state.

    Regression guard for the un-awaited coroutine at the ``wire_dependencies``
    call site: without the ``await`` the coroutine is passed to
    ``dict.update`` (TypeError, swallowed by the startup-tolerance handler)
    and is later GC'd with a "coroutine was never awaited" ``RuntimeWarning``
    — and none of the four service keys ever reach ``app.state.services``.
    """

    def test_db_engine_wires_all_service_backends(self, monkeypatch):
        """Engine present → all four write-path services are constructed."""
        import backend.api.wiring as wiring

        _clear_dependency_env(monkeypatch)
        engine = create_async_engine("sqlite+aiosqlite://")
        monkeypatch.setattr(wiring, "build_db_engine", lambda: engine)

        # Note: the ``with TestClient`` shutdown handler runs
        # ``teardown_dependencies`` which clears ``state.services`` in place, so
        # the assertions must run while the app is still in the startup phase.
        try:
            app = create_app()
            with warnings.catch_warnings():
                # The never-awaited coroutine would raise here if the bug
                # regressed; the isinstance checks below fail independently.
                warnings.simplefilter("error", RuntimeWarning)
                with TestClient(app) as client:
                    services = client.app.state.services or {}
                    assert isinstance(services.get("goals"), GoalService)
                    assert isinstance(services.get("tasks"), TaskService)
                    assert isinstance(services.get("entities"), EntityService)
                    assert isinstance(services.get("relationships"), RelationshipService)
                    assert isinstance(services.get("evidence"), EvidenceService)
        finally:
            asyncio.run(engine.dispose())


# ===========================================================================
# Gap-closure: API startup ensures the JetStream event stream exists
# ===========================================================================
class _FakeStreamNatsClient:
    """Stub NATS client that records lifecycle calls (no real socket).

    ``jetstream`` raises like a disconnected client so the events endpoints
    keep their honest 503 degradation; ``ensure_stream`` records the call and
    optionally raises to exercise the startup-failure path.
    """

    def __init__(self, stream_error: Exception | None = None) -> None:
        self.stream_error = stream_error
        self.connect_calls = 0
        self.ensure_stream_calls = 0

    @property
    def config(self):
        return SimpleNamespace(stream_name="NERVECENTER_EVENTS")

    @property
    def is_connected(self) -> bool:
        return True

    @property
    def jetstream(self):
        raise RuntimeError("NatsClient is not connected. Call connect() first.")

    async def connect(self) -> None:
        self.connect_calls += 1

    async def ensure_stream(self) -> None:
        self.ensure_stream_calls += 1
        if self.stream_error is not None:
            raise self.stream_error

    async def disconnect(self) -> None:
        pass


class TestStartupEnsuresEventStream:
    """``_build_and_connect_nats`` must ensure the stream on API startup.

    Deploy root cause: the standalone ``backend.events`` entrypoint called
    ``ensure_stream()`` but the API startup wiring never did, so the
    ``NERVECENTER_EVENTS`` stream was absent in the deploy path and
    ``GET /api/events`` / ``WS /api/events/ws`` degraded to a permanent
    honest 503 ``event_bus_unavailable``.
    """

    def test_startup_ensures_stream_on_connected_nats(self, monkeypatch):
        _clear_dependency_env(monkeypatch)
        monkeypatch.setenv("NERVE_NATS_URL", "nats://nats:4222")

        fake = _FakeStreamNatsClient()
        import backend.api.wiring as wiring

        monkeypatch.setattr(wiring, "build_nats_client", lambda: fake)

        app = create_app()
        with TestClient(app):
            pass

        assert fake.connect_calls == 1
        assert fake.ensure_stream_calls == 1, (
            "API startup must call ensure_stream() so NERVECENTER_EVENTS "
            "exists in the deploy path"
        )

    def test_startup_succeeds_when_ensure_stream_fails(self, monkeypatch):
        """Stream-creation failure is logged, never raised: startup + honest
        503 degradation survive (no fake empty 200, no fake error 200)."""
        _clear_dependency_env(monkeypatch)
        monkeypatch.setenv("NERVE_NATS_URL", "nats://nats:4222")

        fake = _FakeStreamNatsClient(
            stream_error=RuntimeError("jetstream admin: no authorization")
        )
        import backend.api.wiring as wiring

        monkeypatch.setattr(wiring, "build_nats_client", lambda: fake)

        app = create_app()
        with TestClient(app) as client:
            # Startup survived: liveness probe contract (200) intact.
            assert client.get("/api/health").status_code == 200
            # Honest degradation preserved: configured-but-unreadable bus → 503.
            response = client.get("/api/events/")
            assert response.status_code == 503
            assert response.json()["error"] == "event_bus_unavailable"

        assert fake.ensure_stream_calls == 1
