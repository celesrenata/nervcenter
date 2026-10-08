"""T-H31: Section 15 evidence service — capture, provenance, citation, integrity.

Covers the async :class:`backend.evidence.service.EvidenceService` and the
``/api/evidence`` endpoints against the real ORM (``evidence`` table), so the
assertions are about behaviour, not stubs:

- **capture**: ``create()`` persists a row with the captured ``content``, a
  matching ``content_hash`` (SHA-256 of the content), ``captured_at``,
  ``trust``, capture metadata, and the redaction flag;
- **provenance**: ``get()`` returns the full record for a stable id and
  ``None`` for unknown or malformed ids;
- **citation index**: ``list_by_source()`` filters by
  ``(source_type, source_ref)`` and orders newest capture first;
- **integrity**: ``verify_content()`` recomputes the content digest and
  detects mismatches (wrong ``expected_hash``, missing record, missing
  stored digest);
- **lifecycle**: ``delete()`` removes the row; deleting an unknown id is a
  no-op (``False``);
- **API**: ``POST /api/evidence`` captures (202), ``GET`` listing is honest
  (empty 200 when unconfigured, real rows when wired), ``GET/{id}`` is 200/404,
  ``DELETE`` is 204/404, the verify endpoint reports match/mismatch, and an
  invalid ``source_type`` literal is rejected with 422.

No live PostgreSQL is used: persistence runs on in-memory SQLite
(``StaticPool`` + aiosqlite), exercising the full ORM + service path
end-to-end except the Postgres dialect itself.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

import backend.api.wiring as api_wiring
from backend.api.app import create_app
from backend.api.endpoints import evidence as evidence_endpoints
from backend.evidence.service import EvidenceService
from backend.persistence.models.evidence import Evidence

#: DB/NATS URL env vars the wiring reads (see ``backend.api.wiring``).
ENV_NAMES = (
    "NERVE_DB_URL",
    "NERVECENTER_DATABASE_URL",
    "NERVE_NATS_URL",
    "NERVECENTER_NATS_URL",
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
async def engine():
    """In-memory SQLite async engine with the evidence table created."""
    eng = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with eng.begin() as conn:
        await conn.run_sync(Evidence.__table__.create)
    yield eng
    await eng.dispose()


@pytest.fixture
def svc(engine) -> EvidenceService:
    return EvidenceService(engine)


@pytest.fixture
def api_client(engine) -> TestClient:
    """Isolated FastAPI app with the evidence router wired to a real service."""
    app = FastAPI()
    app.include_router(evidence_endpoints.router)
    app.state.services = {"evidence": EvidenceService(engine)}
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------


class TestCapture:
    async def test_create_persists_content_and_hash(self, svc):
        captured_at = datetime(2026, 10, 5, 12, 0, 0, tzinfo=UTC)
        rec = await svc.create(
            "web_page",
            "https://example.com/page",
            content="the captured body",
            captured_at=captured_at,
            trust=0.9,
            metadata={"tool": "curl", "status": 200},
        )
        assert rec.content_hash == _sha256("the captured body")
        assert rec.captured_at == captured_at
        assert rec.trust == 0.9
        assert rec.metadata == {"tool": "curl", "status": 200}
        assert rec.redacted is False
        assert rec.schema_version == "v0"
        assert rec.id  # stable UUID id assigned at capture
        # persisted: provenance lookup in a fresh session round-trips the row
        again = await svc.get(rec.id)
        assert again is not None
        assert again.source_type == "web_page"
        assert again.source_ref == "https://example.com/page"
        assert again.content == "the captured body"
        assert again.content_hash == rec.content_hash

    async def test_create_derives_hash_only_from_content(self, svc):
        rec = await svc.create("file", "/tmp/artifact.bin", content="abc")
        assert rec.content_hash == _sha256("abc")

    async def test_create_reference_only_capture(self, svc):
        """No stored content: caller-supplied digest is honoured."""
        rec = await svc.create(
            "tool_result",
            "task:run-1:step",
            content=None,
            content_hash="ab" * 32,
        )
        assert rec.content is None
        assert rec.content_hash == "ab" * 32

    async def test_create_redacted_flag(self, svc):
        rec = await svc.create(
            "transcript",
            "meeting:2026-10-01",
            content=None,
            content_hash="cd" * 32,
            redacted=True,
        )
        assert rec.redacted is True
        assert rec.content is None

    async def test_create_invalid_source_type_rejected(self, svc):
        with pytest.raises(ValidationError):
            await svc.create("not-a-literal", "https://x")

    async def test_create_trust_out_of_range_rejected(self, svc):
        with pytest.raises(ValidationError):
            await svc.create("file", "/tmp/x", content="x", trust=1.5)

    async def test_create_defaults(self, svc):
        before = datetime.now(UTC)
        rec = await svc.create("manual_note", "note:42")
        after = datetime.now(UTC)
        assert rec.content is None
        assert rec.content_hash is None
        assert rec.trust == 0.5
        assert rec.metadata == {}
        assert before <= rec.captured_at <= after


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------


class TestProvenance:
    async def test_get_returns_full_provenance(self, svc):
        rec = await svc.create(
            "web_page",
            "https://example.com/other",
            content="body",
            trust=0.2,
            metadata={"offset": 3},
        )
        got = await svc.get(rec.id)
        assert got is not None
        assert got.id == rec.id
        assert got.content == "body"
        assert got.content_hash == _sha256("body")
        assert got.trust == 0.2
        assert got.metadata == {"offset": 3}
        assert got.created_at is not None

    async def test_get_unknown_id_returns_none(self, svc):
        assert (
            await svc.get("11111111-1111-4111-8111-111111111111") is None
        )

    async def test_get_malformed_id_returns_none(self, svc):
        await svc.create("file", "/tmp/x", content="x")
        assert await svc.get("not-a-uuid") is None


# ---------------------------------------------------------------------------
# citation index
# ---------------------------------------------------------------------------


class TestCitationIndex:
    async def test_list_by_source_filters_exact_source(self, svc):
        a1 = await svc.create("web_page", "https://s.com/a", content="a1")
        a2 = await svc.create("web_page", "https://s.com/a", content="a2")
        await svc.create("web_page", "https://s.com/b", content="b1")
        await svc.create("document", "https://s.com/a", content="d1")

        cited = await svc.list_by_source("web_page", "https://s.com/a")
        assert {r.id for r in cited} == {a1.id, a2.id}
        assert {r.content for r in cited} == {"a1", "a2"}

        other = await svc.list_by_source("web_page", "https://s.com/b")
        assert [r.content for r in other] == ["b1"]

        none = await svc.list_by_source("web_page", "https://s.com/missing")
        assert none == []

    async def test_list_by_source_orders_newest_capture_first(self, svc):
        old = await svc.create(
            "log", "svc:api", content="old",
            captured_at=datetime(2026, 10, 1, tzinfo=UTC),
        )
        new = await svc.create(
            "log", "svc:api", content="new",
            captured_at=datetime(2026, 10, 3, tzinfo=UTC),
        )
        cited = await svc.list_by_source("log", "svc:api")
        assert [r.id for r in cited] == [new.id, old.id]


# ---------------------------------------------------------------------------
# integrity / verify_content
# ---------------------------------------------------------------------------


class TestVerifyContent:
    async def test_verify_ok(self, svc):
        rec = await svc.create("file", "/tmp/a", content="hello")
        assert await svc.verify_content(rec.id, _sha256("hello")) is True
        # stored digest also serves as the expected value
        assert await svc.verify_content(rec.id, rec.content_hash or "") is True

    async def test_verify_detects_mismatch(self, svc):
        rec = await svc.create("file", "/tmp/b", content="hello")
        assert await svc.verify_content(rec.id, "ff" * 32) is False

    async def test_verify_missing_record_returns_false(self, svc):
        assert (
            await svc.verify_content(
                "22222222-2222-4222-8222-222222222222", "ab" * 32
            )
            is False
        )

    async def test_verify_malformed_id_returns_false(self, svc):
        assert await svc.verify_content("garbage", "ab" * 32) is False

    async def test_verify_reference_only_capture(self, svc):
        """No stored content: stored digest compared against expected only."""
        rec = await svc.create(
            "snapshot", "artefact:obj-1", content=None, content_hash="ab" * 32
        )
        assert await svc.verify_content(rec.id, "ab" * 32) is True
        assert await svc.verify_content(rec.id, "cd" * 32) is False

    async def test_verify_no_digest_stored_returns_false(self, svc):
        rec = await svc.create("manual_note", "note:1")  # no content, no hash
        assert await svc.verify_content(rec.id, "ab" * 32) is False


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------


class TestDelete:
    async def test_delete_removes_record(self, svc):
        rec = await svc.create("file", "/tmp/d", content="x")
        assert await svc.delete(rec.id) is True
        assert await svc.get(rec.id) is None

    async def test_delete_unknown_is_noop(self, svc):
        assert (
            await svc.delete("33333333-3333-4333-8333-333333333333") is False
        )

    async def test_delete_malformed_id_is_noop(self, svc):
        await svc.create("file", "/tmp/m", content="x")
        assert await svc.delete("not-a-uuid") is False


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class TestEvidenceAPI:
    def test_capture_and_get_roundtrip(self, api_client):
        payload = {
            "source_type": "web_page",
            "source_ref": "https://example.com/api",
            "content": "captured body",
            "trust": 0.7,
            "metadata": {"status": 200},
        }
        res = api_client.post("/api/evidence/", json=payload)
        assert res.status_code == 202
        body = res.json()
        assert body["source_ref"] == "https://example.com/api"
        assert body["content_hash"] == _sha256("captured body")
        assert body["trust"] == 0.7
        eid = body["id"]

        got = api_client.get(f"/api/evidence/{eid}")
        assert got.status_code == 200
        assert got.json()["id"] == eid
        assert got.json()["content"] == "captured body"

    def test_list_shows_captured_record(self, api_client):
        api_client.post(
            "/api/evidence/",
            json={"source_type": "file", "source_ref": "/tmp/l", "content": "l"},
        )
        res = api_client.get("/api/evidence/")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["source_ref"] == "/tmp/l"
        assert res.json()["meta"]["pagination"]["total"] == 1

    def test_get_unknown_404(self, api_client):
        res = api_client.get("/api/evidence/11111111-1111-4111-8111-111111111111")
        assert res.status_code == 404

    def test_delete_flow(self, api_client):
        created = api_client.post(
            "/api/evidence/",
            json={"source_type": "file", "source_ref": "/tmp/del", "content": "x"},
        )
        eid = created.json()["id"]
        assert api_client.delete(f"/api/evidence/{eid}").status_code == 204
        assert api_client.get(f"/api/evidence/{eid}").status_code == 404
        assert api_client.delete(f"/api/evidence/{eid}").status_code == 404

    def test_verify_endpoint_match_and_mismatch(self, api_client):
        created = api_client.post(
            "/api/evidence/",
            json={"source_type": "file", "source_ref": "/tmp/v", "content": "v"},
        )
        eid = created.json()["id"]
        ok = api_client.get(f"/api/evidence/{eid}/verify")
        assert ok.status_code == 200
        assert ok.json()["match"] is True

        bad = api_client.get(
            f"/api/evidence/{eid}/verify", params={"expected_hash": "ff" * 32}
        )
        assert bad.status_code == 200
        assert bad.json()["match"] is False

        missing = api_client.get(
            "/api/evidence/22222222-2222-4222-8222-222222222222/verify"
        )
        assert missing.status_code == 404

    def test_invalid_source_type_rejected_422(self, api_client):
        res = api_client.post(
            "/api/evidence/",
            json={"source_type": "bogus-kind", "source_ref": "https://x"},
        )
        assert res.status_code == 422


class TestEvidenceAPIDegradation:
    """Endpoints degrade honestly when no evidence service is configured."""

    def _unwired_client(self) -> TestClient:
        app = FastAPI()
        app.include_router(evidence_endpoints.router)
        # no app.state.services entry -> service absent
        return TestClient(app)

    def test_list_empty_when_unconfigured(self):
        client = self._unwired_client()
        res = client.get("/api/evidence/")
        assert res.status_code == 200
        assert res.json()["data"] == []

    def test_mutation_503_when_unconfigured(self):
        client = self._unwired_client()
        res = client.post(
            "/api/evidence/",
            json={"source_type": "file", "source_ref": "/tmp/x", "content": "x"},
        )
        assert res.status_code == 503
        assert client.get(
            "/api/evidence/11111111-1111-4111-8111-111111111111"
        ).status_code == 503


class TestStartupWiring:
    """``wire_dependencies`` populates ``app.state.services["evidence"]``.

    The router is covered above with a hand-built ``FastAPI`` that injects
    ``app.state.services`` directly; this class covers the startup *wiring*
    contract the production server depends on (T-H31):

    - no DB URL env  → the ``evidence`` key is absent (endpoints degrade);
    - DB URL present → the evidence service is built from the same durable
      engine and reachable through ``create_app()``.

    No live PostgreSQL: ``build_db_engine`` is monkeypatched to an in-memory
    SQLite engine, so only the wiring logic (env → engine → service) is
    exercised, never a network connection.
    """

    @staticmethod
    def _clear_dependency_env(monkeypatch: pytest.MonkeyPatch) -> None:
        for name in ENV_NAMES:
            monkeypatch.delenv(name, raising=False)

    def test_no_db_env_evidence_service_absent(self, monkeypatch):
        """No DB URL env → no ``evidence`` service; app still boots cleanly."""
        self._clear_dependency_env(monkeypatch)
        monkeypatch.setattr(api_wiring, "build_db_engine", lambda: None)
        monkeypatch.setattr(api_wiring, "build_nats_client", lambda: None)

        app = create_app()
        with TestClient(app) as client:
            assert app.state.db_engine is None
            assert "evidence" not in (app.state.services or {})
            res = client.get("/api/evidence/")
            # Honest degradation: empty 200, not fabricated rows.
            assert res.status_code == 200
            assert res.json()["data"] == []
            res = client.post(
                "/api/evidence/",
                json={"source_type": "file", "source_ref": "/tmp/x", "content": "x"},
            )
            assert res.status_code == 503

    def test_db_env_evidence_service_wired(self, monkeypatch, engine):
        """DB env + engine → evidence service wired onto the real app."""
        self._clear_dependency_env(monkeypatch)
        monkeypatch.setattr(api_wiring, "build_db_engine", lambda: engine)
        monkeypatch.setattr(api_wiring, "build_nats_client", lambda: None)
        monkeypatch.setenv("NERVE_DB_URL", "postgresql+asyncpg://x:x@127.0.0.1:1/x")

        app = create_app()
        with TestClient(app) as client:
            svc = (app.state.services or {}).get("evidence")
            assert isinstance(svc, EvidenceService)
            # Same durable engine the service is bound to.
            assert app.state.db_engine is engine

            res = client.post(
                "/api/evidence/",
                json={
                    "source_type": "manual_note",
                    "source_ref": "wiring://proof",
                    "content": "wiring proof",
                    "trust": 0.9,
                },
            )
            assert res.status_code == 202
            eid = res.json()["id"]

            res = client.get("/api/evidence/")
            assert res.status_code == 200
            rows = res.json()["data"]
            assert any(r["id"] == eid for r in rows)

            res = client.get(f"/api/evidence/{eid}")
            assert res.status_code == 200
            assert res.json()["id"] == eid
