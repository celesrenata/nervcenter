"""Prompt2 Phase P0 — Attention Engine tests (schema, scoring, /api/attention).

Covers:
- ``AttentionItem`` schema + ``AttentionState`` enum (prompt2 §20/§25).
- Deterministic, explainable scoring: identical inputs → identical
  priority/why; near-deadlines outrank far-deadlines (§21/§22).
- The ``/api/attention`` router: list / now / get / create / resolve /
  suppress / acknowledge / snooze, including honest 404s and the 422 the
  router emits for an invalid state value.

The attention service is an in-process singleton that is *not* engine-backed,
so tests get a fresh app per test via :func:`backend.api.app.create_app` and
a fresh service via :func:`backend.attention.reset_attention_service` — no
database or NATS required.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.models import AttentionItem, AttentionState
from backend.attention import AttentionService, reset_attention_service


@pytest.fixture
def client():
    reset_attention_service()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_attention_service()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_attention_item_minimal_defaults():
    item = AttentionItem(attention_id="att-1", reason="call mom")
    assert item.status is AttentionState.NOW
    assert item.priority == 0.0
    assert item.entities == []
    assert item.sources == []
    assert item.suggested_action is None
    assert item.why == []
    assert item.due is None


def test_attention_item_rejects_out_of_range_priority():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AttentionItem(attention_id="att-2", reason="x", priority=1.5)
    with pytest.raises(ValidationError):
        AttentionItem(attention_id="att-3", reason="x", urgency=-0.1)


def test_attention_state_enum_matches_prompt2_states():
    assert {s.value for s in AttentionState} == {
        "NOW",
        "TODAY",
        "SOON",
        "WAITING_ON",
        "FYI",
        "SUPPRESSED",
        "RESOLVED",
    }


# ---------------------------------------------------------------------------
# Deterministic scoring (prompt2 §21/§22)
# ---------------------------------------------------------------------------


def test_scoring_is_deterministic():
    svc = AttentionService()
    a = svc.create({"reason": "r", "urgency": 0.6, "importance": 0.8})
    b = svc.create({"reason": "r", "urgency": 0.6, "importance": 0.8})
    assert a.priority == b.priority
    assert a.why == b.why


def test_near_deadline_outranks_far_deadline():
    svc = AttentionService()
    now = datetime.now(UTC)
    near = svc.create(
        {"reason": "near", "urgency": 0.5, "importance": 0.5, "due": now + timedelta(hours=2)}
    )
    far = svc.create(
        {"reason": "far", "urgency": 0.5, "importance": 0.5, "due": now + timedelta(days=14)}
    )
    assert near.priority > far.priority


def test_overdue_deadline_gets_max_proximity_bonus():
    svc = AttentionService()
    now = datetime.now(UTC)
    overdue = svc.create(
        {"reason": "late", "urgency": 0.2, "importance": 0.2, "due": now - timedelta(hours=1)}
    )
    assert any("overdue" in w for w in overdue.why)


def test_suggested_action_adds_direct_request_factor():
    svc = AttentionService()
    with_action = svc.create({"reason": "x", "urgency": 0.5, "importance": 0.5,
                              "suggested_action": "sign it"})
    without = svc.create({"reason": "x", "urgency": 0.5, "importance": 0.5})
    assert with_action.priority > without.priority
    assert any("direct request" in w for w in with_action.why)


def test_priority_clamped_to_unit_interval():
    svc = AttentionService()
    now = datetime.now(UTC)
    hot = svc.create(
        {
            "reason": "max",
            "urgency": 1.0,
            "importance": 1.0,
            "due": now - timedelta(hours=1),
            "suggested_action": "do it",
        }
    )
    assert hot.priority <= 1.0
    assert hot.priority >= 0.0


# ---------------------------------------------------------------------------
# Router: reads
# ---------------------------------------------------------------------------


def test_list_empty_queue_returns_empty_data(client):
    res = client.get("/api/attention")
    assert res.status_code == 200
    body = res.json()
    assert body["data"] == []
    assert body["meta"]["pagination"]["total"] == 0


def test_now_feed_returns_only_now_bucket(client):
    res = client.post(
        "/api/attention",
        json={"reason": "urgent thing", "urgency": 0.9, "importance": 0.9},
    )
    assert res.status_code == 201
    item_id = res.json()["attention_id"]

    # Snooze moves it out of the NOW bucket (→ TODAY)
    assert client.post(f"/api/attention/{item_id}/snooze", json={}).status_code == 200

    now = client.get("/api/attention/now").json()
    assert all(i["status"] == "NOW" for i in now["data"])
    assert all(i["attention_id"] != item_id for i in now["data"])

    full = client.get("/api/attention").json()
    assert any(i["attention_id"] == item_id for i in full["data"])


def test_list_filter_by_status(client):
    a = client.post(
        "/api/attention", json={"reason": "a", "urgency": 0.5, "importance": 0.5}
    ).json()
    b = client.post(
        "/api/attention", json={"reason": "b", "urgency": 0.5, "importance": 0.5}
    ).json()
    client.post(f"/api/attention/{b['attention_id']}/resolve")

    now_only = client.get("/api/attention", params={"status": "NOW"}).json()
    ids = {i["attention_id"] for i in now_only["data"]}
    assert a["attention_id"] in ids
    assert b["attention_id"] not in ids

    resolved = client.get("/api/attention", params={"status": "RESOLVED"}).json()
    assert {i["attention_id"] for i in resolved["data"]} == {b["attention_id"]}


def test_list_invalid_status_422(client):
    assert client.get("/api/attention", params={"status": "BOGUS"}).status_code == 422


# ---------------------------------------------------------------------------
# Router: lifecycle
# ---------------------------------------------------------------------------


def test_create_returns_201_with_scored_item(client):
    res = client.post(
        "/api/attention",
        json={
            "reason": "Call pharmacy before 5pm",
            "urgency": 0.8,
            "importance": 0.7,
            "suggested_action": "Call pharmacy",
            "entities": ["Pharmacy"],
            "sources": ["calendar"],
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["attention_id"].startswith("att-")
    assert body["reason"] == "Call pharmacy before 5pm"
    assert 0.0 < body["priority"] <= 1.0
    assert body["status"] == "NOW"
    assert body["entities"] == ["Pharmacy"]
    assert body["why"], "scorer must always explain the priority"


def test_create_requires_reason(client):
    assert client.post("/api/attention", json={}).status_code == 422


def test_get_by_id_and_404(client):
    created = client.post("/api/attention", json={"reason": "x", "urgency": 0.3, "importance": 0.3})
    item_id = created.json()["attention_id"]
    assert client.get(f"/api/attention/{item_id}").status_code == 200
    assert client.get("/api/attention/att-missing").status_code == 404


def test_resolve_and_acknowledge_transitions(client):
    item = client.post("/api/attention", json={"reason": "x", "urgency": 0.5, "importance": 0.5})
    item_id = item.json()["attention_id"]

    r = client.post(f"/api/attention/{item_id}/resolve")
    assert r.status_code == 200
    assert r.json()["status"] == "RESOLVED"

    item2 = client.post("/api/attention", json={"reason": "y", "urgency": 0.5, "importance": 0.5})
    item2_id = item2.json()["attention_id"]
    r2 = client.post(f"/api/attention/{item2_id}/acknowledge")
    assert r2.status_code == 200
    assert r2.json()["status"] == "RESOLVED"


def test_suppress_transition(client):
    item = client.post("/api/attention", json={"reason": "x", "urgency": 0.5, "importance": 0.5})
    item_id = item.json()["attention_id"]
    r = client.post(f"/api/attention/{item_id}/suppress")
    assert r.status_code == 200
    assert r.json()["status"] == "SUPPRESSED"


def test_snooze_sets_due_and_defers_out_of_now(client):
    item = client.post("/api/attention", json={"reason": "x", "urgency": 0.5, "importance": 0.5})
    item_id = item.json()["attention_id"]

    until = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    r = client.post(f"/api/attention/{item_id}/snooze", json={"until": until})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "TODAY"
    assert body["due"] is not None

    # default snooze (no until) → 1 day out
    item2 = client.post("/api/attention", json={"reason": "z", "urgency": 0.5, "importance": 0.5})
    r2 = client.post(f"/api/attention/{item2.json()['attention_id']}/snooze", json={})
    assert r2.status_code == 200
    assert r2.json()["status"] == "TODAY"


def test_mutations_404_for_unknown_id(client):
    for path in ("resolve", "suppress", "acknowledge", "snooze"):
        res = client.post(f"/api/attention/att-nope/{path}", json={})
        assert res.status_code == 404, path


def test_seed_demo_populates_now_feed(client):
    svc = client.app.state.attention_service
    svc.seed_demo()
    now = client.get("/api/attention/now").json()
    assert now["meta"]["pagination"]["total"] == 4
    # ranked: priorities non-increasing
    priorities = [i["priority"] for i in now["data"]]
    assert priorities == sorted(priorities, reverse=True)
