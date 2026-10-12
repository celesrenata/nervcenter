"""Prompt2 Phase P1 — Messages plane tests (schema, threading, attention link).

Covers:
- ``Message`` / ``Conversation`` / ``MessageDirection`` schema (prompt2 §76).
- Message ingestion: thread reconstruction (one thread per peer+channel),
  chronological ordering, unread bookkeeping.
- Idempotent ingest: replaying a message id is a no-op (§48 replay safety).
- AttentionItem generation: a new Mac Messages conversation produces an
  AttentionItem (§76 acceptance); the item is refreshed in place (not
  duplicated) on further inbounds; acknowledging resolves it.
- Cross-channel person resolution: binding an identifier to a name updates
  existing threads and resolves future messages.
- Draft replies: deterministic, based on the latest inbound (§13 AI drafts,
  human sends).
- The ``/api/messages`` router: list / ingest / get / acknowledge / draft /
  persons, including honest 404s and the 422 the router emits for an invalid
  direction value.

The messages service is an in-process singleton (no engine, no DB), so tests
get a fresh app per test via :func:`backend.api.app.create_app` and fresh
singletons via the reset hooks — no database or NATS required.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.models import Message, MessageDirection
from backend.attention import reset_attention_service
from backend.messages import MessagesService, reset_messages_service


@pytest.fixture
def client():
    reset_attention_service()
    reset_messages_service()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_attention_service()
    reset_messages_service()


def _now() -> datetime:
    return datetime.now(UTC)


def _ingest(client: TestClient, **over) -> dict:
    payload = {
        "message_id": f"msg-{over.get('n', 1)}",
        "direction": "INBOUND",
        "peer_identifier": "+14155550134",
        "peer_name": "Alice Nguyen",
        "body": "Are you free Friday?",
        "channel": "imessage",
        "timestamp": _now().isoformat(),
    }
    payload.update(over)
    res = client.post("/api/messages/ingest", json=payload)
    assert res.status_code in (200, 201), res.text
    return res.json()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_message_defaults():
    msg = Message(
        message_id="m1",
        conversation_id="conv-x",
        direction=MessageDirection.INBOUND,
        peer_identifier="+1555",
        body="hi",
        timestamp=_now(),
    )
    assert msg.peer_name is None
    assert msg.channel == "imessage"
    assert msg.source == "personal-relay"


def test_direction_enum_values():
    assert MessageDirection.INBOUND.value == "INBOUND"
    assert MessageDirection.OUTBOUND.value == "OUTBOUND"


# ---------------------------------------------------------------------------
# Ingestion + thread reconstruction
# ---------------------------------------------------------------------------


def test_ingest_creates_thread(client):
    data = _ingest(client)
    conv = data["conversation"]
    assert conv["message_count"] == 1
    assert conv["unread"] == 1
    assert conv["last_body"] == "Are you free Friday?"
    assert conv["peer_name"] == "Alice Nguyen"
    assert data["message"]["conversation_id"] == conv["conversation_id"]


def test_ingest_returns_201_then_200_on_replay(client):
    first = client.post("/api/messages/ingest", json={
        "message_id": "msg-replay",
        "peer_identifier": "+14155550134",
        "peer_name": "Alice Nguyen",
        "body": "hello",
        "timestamp": _now().isoformat(),
    })
    assert first.status_code == 201
    replay = client.post("/api/messages/ingest", json={
        "message_id": "msg-replay",
        "peer_identifier": "+14155550134",
        "peer_name": "Alice Nguyen",
        "body": "hello",
        "timestamp": _now().isoformat(),
    })
    assert replay.status_code == 200
    assert replay.json()["duplicate"] is True
    # Replay changed nothing: the thread still has exactly one message.
    listing = client.get("/api/messages").json()["data"]
    assert listing[0]["message_count"] == 1


def test_one_thread_per_peer_per_channel(client):
    _ingest(client, n=1, channel="imessage")
    _ingest(client, n=2, channel="sms")
    listing = client.get("/api/messages").json()["data"]
    assert len(listing) == 2
    channels = {c["channel"] for c in listing}
    assert channels == {"imessage", "sms"}


def test_thread_messages_chronological(client):
    base = _now() - timedelta(hours=2)
    _ingest(client, n=1, timestamp=(base + timedelta(hours=1)).isoformat(), body="later msg")
    _ingest(client, n=2, timestamp=base.isoformat(), body="earlier msg")
    _ingest(client, n=3, timestamp=(base + timedelta(hours=2)).isoformat(), body="latest msg")
    convs = client.get("/api/messages").json()["data"]
    conv_id = convs[0]["conversation_id"]
    thread = client.get(f"/api/messages/{conv_id}").json()
    bodies = [m["body"] for m in thread["messages"]]
    assert bodies == ["earlier msg", "later msg", "latest msg"]
    # List view is also most-recently-active first.
    assert convs[0]["conversation_id"] == conv_id


def test_outbound_message_clears_unread(client):
    data = _ingest(client)
    conv_id = data["conversation"]["conversation_id"]
    outbound = client.post("/api/messages/ingest", json={
        "message_id": "msg-out-1",
        "direction": "OUTBOUND",
        "peer_identifier": "+14155550134",
        "peer_name": "Alice Nguyen",
        "body": "Yes, Friday works.",
        "timestamp": _now().isoformat(),
    }).json()
    assert outbound["conversation"]["unread"] == 0
    assert outbound["conversation"]["message_count"] == 2
    # Outbound does not itself create attention.
    assert outbound["new_attention"] is None
    _assert_thread_exists(client, conv_id)


def _assert_thread_exists(client, conv_id):
    assert client.get(f"/api/messages/{conv_id}").status_code == 200


def test_unknown_conversation_404(client):
    assert client.get("/api/messages/conv-nope|imessage").status_code == 404
    assert client.post("/api/messages/conv-nope|imessage/draft").status_code == 404
    assert client.post("/api/messages/conv-nope|imessage/acknowledge").status_code == 404


def test_invalid_direction_422(client):
    res = client.post("/api/messages/ingest", json={
        "message_id": "msg-bad",
        "direction": "DIAGONAL",
        "peer_identifier": "+1",
        "body": "x",
    })
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# AttentionItem generation (§76 acceptance)
# ---------------------------------------------------------------------------


def test_new_conversation_produces_attention_item(client):
    data = _ingest(client)
    assert data["new_attention"] is not None
    att = data["new_attention"]
    assert att["attention_id"] == data["conversation"]["attention_id"]
    # The item lands on the Now screen and names the conversation.
    now = client.get("/api/attention/now").json()["data"]
    ids = [a["attention_id"] for a in now]
    assert att["attention_id"] in ids
    item = next(a for a in now if a["attention_id"] == att["attention_id"])
    assert "Alice" in item["reason"]
    assert "messages:imessage" in item["sources"]
    assert item["why"], "attention item must be explainable (§22)"


def test_second_inbound_refreshes_rather_than_duplicates(client):
    first = _ingest(client)
    conv_id = first["conversation"]["conversation_id"]
    second = _ingest(client, n=2, body="Also — can you bring the slides?")
    assert second["conversation"]["unread"] == 2
    # Same live item, refreshed — still exactly one NOW item for this thread.
    now = client.get("/api/attention/now").json()["data"]
    thread_items = [
        a for a in now if any("messages:" in s for s in a.get("sources", []))
    ]
    assert len(thread_items) == 1
    assert thread_items[0]["attention_id"] == first["conversation"]["attention_id"]


def test_acknowledge_resolves_attention(client):
    data = _ingest(client)
    conv_id = data["conversation"]["conversation_id"]
    att_id = data["conversation"]["attention_id"]
    res = client.post(f"/api/messages/{conv_id}/acknowledge")
    assert res.status_code == 200
    body = res.json()
    assert body["resolved"] is True
    assert body["conversation"]["unread"] == 0
    # The item is off the Now screen now.
    now_ids = [a["attention_id"] for a in client.get("/api/attention/now").json()["data"]]
    assert att_id not in now_ids
    assert client.get(f"/api/attention/{att_id}").json()["status"] == "RESOLVED"


# ---------------------------------------------------------------------------
# Person resolution (§76 cross-channel)
# ---------------------------------------------------------------------------


def test_register_person_resolves_existing_and_future(client):
    data = _ingest(client, peer_name=None, peer_identifier="alice@me.com")
    conv_id = data["conversation"]["conversation_id"]
    # The thread exists but is unresolved (raw identifier only).
    assert client.get(f"/api/messages/{conv_id}").json()["conversation"]["peer_name"] is None

    res = client.post("/api/messages/persons", json={
        "identifier": "alice@me.com",
        "name": "Alice Nguyen",
    })
    assert res.status_code == 200
    assert res.json()["updated_conversations"] == [conv_id]
    # Existing thread picked the name up…
    assert client.get(f"/api/messages/{conv_id}").json()["conversation"]["peer_name"] == "Alice Nguyen"
    # …and future messages from the same identifier resolve without a name.
    future = _ingest(client, n=99, peer_name=None, peer_identifier="alice@me.com", body="ping")
    assert future["message"]["peer_name"] == "Alice Nguyen"


def test_unnamed_message_has_null_peer_name(client):
    data = _ingest(client, peer_name=None, peer_identifier="+15550004321")
    assert data["message"]["peer_name"] is None
    # Attention still works — falls back to the raw identifier in the reason.
    att = data["new_attention"]
    assert att is not None
    assert "+15550004321" in att["reason"]


# ---------------------------------------------------------------------------
# Draft replies (§13)
# ---------------------------------------------------------------------------


def test_draft_reply_for_question(client):
    data = _ingest(client, body="Can you review the contract today?")
    conv_id = data["conversation"]["conversation_id"]
    res = client.post(f"/api/messages/{conv_id}/draft")
    assert res.status_code == 200
    body = res.json()
    assert body["to"] == "Alice Nguyen"
    assert body["draft"], "draft must be non-empty"
    assert body["basis"]


def test_draft_reply_without_inbound(client):
    svc = MessagesService()
    # A thread with only an OUTBOUND message: nothing to reply to.
    svc.ingest({
        "message_id": "m-only-out",
        "direction": "OUTBOUND",
        "peer_identifier": "+1555",
        "peer_name": "Bob",
        "body": "hi",
        "timestamp": _now().isoformat(),
    })
    out = svc.draft_reply("conv-+1555|imessage")
    assert out["draft"] is None
    assert "no inbound" in out["basis"]
    assert out["to"] == "Bob"
    # Unknown conversation: the service reports it honestly; the router 404s.
    missing = svc.draft_reply("conv-unknown|imessage")
    assert missing["draft"] is None


def test_list_filters_by_channel(client):
    _ingest(client, n=1, channel="imessage")
    _ingest(client, n=2, channel="sms")
    only_sms = client.get("/api/messages", params={"channel": "sms"}).json()["data"]
    assert len(only_sms) == 1
    assert only_sms[0]["channel"] == "sms"


def test_service_reset_hook():
    svc = MessagesService()
    svc.ingest({
        "message_id": "m-reset",
        "peer_identifier": "+1",
        "body": "x",
        "timestamp": _now().isoformat(),
    })
    assert len(svc.list_conversations()) == 1
    reset_messages_service()
    fresh = MessagesService()
    assert fresh is not svc
