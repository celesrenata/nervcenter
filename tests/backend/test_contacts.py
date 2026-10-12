"""Prompt2 Phase P4 — Contacts plane tests (person-resolution, VIP).

Covers:
- ``Contact`` / ``ContactSource`` schema (prompt2 §79 — one resolved person;
  §45/§12 — VIP flag).
- Idempotent upsert by ``person_id``: re-ingesting the same person with an
  extra email/phone *updates* the record (merges the sets, order preserved,
  deduped) instead of creating a duplicate.
- ``/api/contacts`` router: list (case-insensitive, stable ordering +
  ``vip_only`` filter), ingest (201 new / 200 update), get person (honest
  404), VIP toggle on/off (§12), the 422s the router emits for an invalid
  ``source`` value and an empty ``display_name``/``person_id``.
- ``seed_demo`` (NERVE_SEED_CONTACTS=1 behavior) and the reset hook.

The contacts service is an in-process singleton (no engine, no DB), so tests
get a fresh app per test via :func:`backend.api.app.create_app` and fresh
singletons via the reset hooks — no database or NATS required.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.models import Contact, ContactSource
from backend.contacts import ContactsService, reset_contacts_service


@pytest.fixture
def client():
    reset_contacts_service()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_contacts_service()


def _ingest(client: TestClient, **over) -> dict:
    payload = {
        "person_id": "alice-nguyen",
        "display_name": "Alice Nguyen",
        "emails": ["alice.n@example.com"],
        "phones": ["+1 415-555-0134"],
    }
    payload.update(over)
    res = client.post("/api/contacts/ingest", json=payload)
    assert res.status_code in (200, 201), res.text
    return res.json()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_contact_defaults():
    c = Contact(person_id="p1", display_name="Alice")
    assert c.emails == []
    assert c.phones == []
    assert c.notes is None
    assert c.is_vip is False
    assert c.source is ContactSource.RELAY
    assert c.created_at is None
    assert c.last_updated_at is None


def test_source_enum_values():
    assert ContactSource.RELAY.value == "personal-relay"
    assert ContactSource.MANUAL.value == "manual"
    assert ContactSource.IMPORT.value == "import"


# ---------------------------------------------------------------------------
# Ingestion + idempotent upsert
# ---------------------------------------------------------------------------


def test_ingest_creates_person(client):
    data = _ingest(client)
    assert data["created"] is True
    contact = data["contact"]
    assert contact["person_id"] == "alice-nguyen"
    assert contact["display_name"] == "Alice Nguyen"
    assert contact["emails"] == ["alice.n@example.com"]
    assert contact["phones"] == ["+1 415-555-0134"]
    assert contact["is_vip"] is False
    assert contact["source"] == "personal-relay"
    # A fresh store: exactly one person, and the list shows it.
    listing = client.get("/api/contacts").json()["data"]
    assert len(listing) == 1


def test_reingest_updates_not_duplicates(client):
    """Same person, extra email/phone → one record, merged sets (§79)."""
    first = _ingest(client)
    assert first["created"] is True
    second = _ingest(
        client,
        emails=["alice.n@example.com", "alice@work.example.com"],
        phones=["+1 415-555-0134", "+1 415-555-0199"],
    )
    assert second["created"] is False
    assert second["contact"]["emails"] == ["alice.n@example.com", "alice@work.example.com"]
    assert second["contact"]["phones"] == ["+1 415-555-0134", "+1 415-555-0199"]
    # Still exactly ONE person — the extra addresses updated the record.
    listing = client.get("/api/contacts").json()["data"]
    assert len(listing) == 1
    assert listing[0]["emails"] == ["alice.n@example.com", "alice@work.example.com"]


def test_reingest_is_idempotent_for_repeat_addresses(client):
    """Re-posting the same addresses is a no-op on the sets (deduped, order
    preserved) — replay-safe like the relay's queued-event replay (§48)."""
    _ingest(client)
    again = _ingest(client, emails=["alice.n@example.com"], phones=["+1 415-555-0134"])
    assert again["created"] is False
    assert again["contact"]["emails"] == ["alice.n@example.com"]
    assert again["contact"]["phones"] == ["+1 415-555-0134"]
    listing = client.get("/api/contacts").json()["data"]
    assert len(listing) == 1


def test_ingest_returns_201_then_200(client):
    first = client.post("/api/contacts/ingest", json={
        "person_id": "bob-cho",
        "display_name": "Bob Cho",
        "emails": ["bob@example.com"],
    })
    assert first.status_code == 201
    update = client.post("/api/contacts/ingest", json={
        "person_id": "bob-cho",
        "display_name": "Bob Cho",
        "emails": ["bob@example.com", "bob@work.example.com"],
    })
    assert update.status_code == 200
    assert update.json()["created"] is False
    assert update.json()["contact"]["emails"] == ["bob@example.com", "bob@work.example.com"]


def test_reingest_upgrades_display_name_and_notes(client):
    """A later ingest carries the more-updated name/notes; an omitted notes
    must not clear the existing ones."""
    _ingest(client, notes="old note")
    update = _ingest(client, display_name="Alice N.", notes=None)
    assert update["created"] is False
    # display_name was supplied → it wins.
    assert update["contact"]["display_name"] == "Alice N."
    # notes omitted → the stored value is kept.
    assert update["contact"]["notes"] == "old note"


def test_service_keeps_existing_name_on_blank_reingest():
    """At the service level a blank re-ingest keeps the stored display_name
    (the API boundary rejects a blank display_name with a 422 — that is
    covered by ``test_ingest_empty_display_name_422``)."""
    svc = ContactsService()
    svc.ingest({"person_id": "p1", "display_name": "Alice Nguyen", "emails": ["a@example.com"]})
    svc.ingest({"person_id": "p1", "display_name": "   ", "emails": ["a@example.com"]})
    assert svc.get_person("p1").display_name == "Alice Nguyen"
    assert len(svc.list_contacts()) == 1


# ---------------------------------------------------------------------------
# Listing / ordering / VIP filter
# ---------------------------------------------------------------------------


def test_list_is_case_insensitive_and_stable(client):
    _ingest(client, person_id="zoe", display_name="zoe Adams")
    _ingest(client, person_id="bob", display_name="Bob")
    _ingest(client, person_id="alice", display_name="alice")
    _ingest(client, person_id="carol", display_name="Carol")
    listing = client.get("/api/contacts").json()["data"]
    names = [c["display_name"] for c in listing]
    # Lowercased compare: alice < bob < carol < zoe, regardless of case.
    assert names == ["alice", "Bob", "Carol", "zoe Adams"]


def test_vip_only_filter(client):
    _ingest(client, person_id="alice", display_name="Alice")
    _ingest(client, person_id="bob", display_name="Bob")
    _ingest(client, person_id="carol", display_name="Carol")
    client.post("/api/contacts/bob/vip", json={"vip": True})
    all_list = client.get("/api/contacts").json()["data"]
    vip_list = client.get("/api/contacts", params={"vip_only": "true"}).json()["data"]
    assert len(all_list) == 3
    assert [c["person_id"] for c in vip_list] == ["bob"]
    # vip_only=false is the explicit no-op.
    none_list = client.get("/api/contacts", params={"vip_only": "false"}).json()["data"]
    assert len(none_list) == 3


def test_meta_reports_total(client):
    _ingest(client)
    _ingest(client, person_id="bob", display_name="Bob")
    body = client.get("/api/contacts").json()
    assert body["meta"]["pagination"]["total"] == 2
    assert body["meta"]["pagination"]["page"] == 1


# ---------------------------------------------------------------------------
# get person / VIP toggle
# ---------------------------------------------------------------------------


def test_get_person(client):
    _ingest(client)
    person = client.get("/api/contacts/alice-nguyen")
    assert person.status_code == 200
    assert person.json()["person_id"] == "alice-nguyen"
    assert person.json()["display_name"] == "Alice Nguyen"


def test_get_unknown_person_404(client):
    assert client.get("/api/contacts/nobody-here").status_code == 404
    assert client.post("/api/contacts/nobody-here/vip", json={"vip": True}).status_code == 404


def test_set_vip_on_then_off(client):
    _ingest(client)
    on = client.post("/api/contacts/alice-nguyen/vip", json={"vip": True})
    assert on.status_code == 200
    assert on.json()["contact"]["is_vip"] is True
    off = client.post("/api/contacts/alice-nguyen/vip", json={"vip": False})
    assert off.status_code == 200
    assert off.json()["contact"]["is_vip"] is False
    # The flag round-trips through the list too.
    assert client.get("/api/contacts/alice-nguyen").json()["is_vip"] is False
    vip_only = client.get("/api/contacts", params={"vip_only": "true"}).json()["data"]
    assert vip_only == []


def test_set_vip_requires_a_boolean(client):
    _ingest(client)
    res = client.post("/api/contacts/alice-nguyen/vip", json={"vip": "maybe"})
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Honest failures (422)
# ---------------------------------------------------------------------------


def test_ingest_empty_display_name_422(client):
    res = client.post("/api/contacts/ingest", json={
        "person_id": "alice-nguyen",
        "display_name": "",
        "emails": ["a@example.com"],
    })
    assert res.status_code == 422


def test_ingest_empty_person_id_422(client):
    res = client.post("/api/contacts/ingest", json={
        "person_id": "   ",
        "display_name": "Alice",
    })
    assert res.status_code == 422


def test_unknown_source_is_rejected_with_422(client):
    res = client.post("/api/contacts/ingest", json={
        "person_id": "alice-nguyen",
        "display_name": "Alice Nguyen",
        "emails": ["a@example.com"],
        "source": "telepathy",
    })
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Seeding / reset
# ---------------------------------------------------------------------------


def test_seed_demo_populates_people_including_a_vip(client):
    # NERVE_SEED_CONTACTS=1 behavior, exercised directly on the singleton the
    # app bound at startup.
    from backend.contacts import get_contacts_service

    get_contacts_service().seed_demo()
    listing = client.get("/api/contacts").json()["data"]
    assert len(listing) == 3
    names = {c["display_name"] for c in listing}
    assert names == {"Alice Nguyen", "Bob Cho", "Dr. Smith"}
    vip = client.get("/api/contacts", params={"vip_only": "true"}).json()["data"]
    assert len(vip) == 1
    assert vip[0]["person_id"] == "dr-smith"


def test_service_reset_hook():
    svc = ContactsService()
    svc.ingest({
        "person_id": "m-reset",
        "display_name": "M Reset",
        "emails": ["a@example.com"],
    })
    assert len(svc.list_contacts()) == 1
    reset_contacts_service()
    fresh = ContactsService()
    assert fresh is not svc
