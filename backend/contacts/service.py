"""In-memory Contacts service (prompt2 Phase P4 — cross-channel person resolution).

This is the NerveCenter-side *person-resolution* record: a contact is **one
resolved person** (prompt2 §79) aggregated from the normalized contact
records the source-side Personal Relay posts to ``POST /api/contacts/ingest``.
NerveCenter never owns the real address book — the macOS Personal Relay is
the ingestion mechanism (it reads the user's local contact storage with
explicit, user-granted permissions, per the §46/§47-style source-side
contract) and it is *out of scope for this deliverable*. This service only
ever sees normalized contact records.

Design notes
------------
- **No persistence yet.** The store is process memory, deliberately: the API,
  the Contacts screen, and the tests all work without ``NERVE_DB_URL`` — same
  convention as the P0/P1/P2 email/messages/voicemail planes. Public method
  signatures are designed to survive a later swap to a real table.
- **Idempotent upsert by ``person_id``.** A contact record is *one resolved
  person*, not one address. Re-ingesting the same ``person_id`` with an extra
  email or phone *updates* the existing record — merging the email/phone sets
  (dedup, order preserved) — instead of creating a duplicate person. This
  mirrors the "one thread per counterpart" reconstruction the other planes do
  per channel, but here the key is the resolved *person* (stable ``person_id``
  slug) so the same human seen across channels/email/voicemail resolves to a
  single record (§79 unified person model).
- **VIP is a stored flag only.** ``is_vip`` is stored and returned by this
  service (prompt2 §12 — the VIP contacts list). The attention engine weighs
  VIP contacts more heavily (§22 / §45 Contact Priority); that weighting is a
  separate concern — the contacts service deliberately does not score or
  create AttentionItems, only stores/returns the flag.
- **Deterministic ordering.** ``list_contacts`` orders by ``display_name``
  (case-insensitive) with ``person_id`` as the stable tiebreaker, so the
  Contacts screen and any tests get an identical order for identical state.
- **Provenance.** Every record carries a ``source`` (the
  ``ContactSource`` enum) naming the ingestion path, so the record is
  attributable (§49-style per-source provenance convention).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.api.models import Contact, ContactSource


def _now() -> datetime:
    return datetime.now(UTC)


def _merge(base: list[str], extra: list[str]) -> list[str]:
    """Union of two address/phone lists: keep the existing order, append the
    new values not already present (deduped). ``extra`` may be empty — an
    ingest that omits a list must never *clear* an existing one."""
    seen = set(base)
    merged = list(base)
    for value in extra:
        if value not in seen:
            seen.add(value)
            merged.append(value)
    return merged


class ContactsService:
    """In-memory cross-channel person resolution + VIP bookkeeping (P4)."""

    def __init__(self) -> None:
        self._contacts: dict[str, Contact] = {}

    # -- ingestion -----------------------------------------------------------
    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Ingest one normalized person record (as posted by the Personal
        Relay, §79).

        Returns ``{"contact": Contact, "created": bool}``. A new
        ``person_id`` creates the record (``created=True``); a known
        ``person_id`` merges the emails/phones sets and keeps the more
        up-to-date ``display_name``/``notes``/``source`` (``created=False``).
        """
        person_id = str(payload["person_id"]).strip()
        display_name = str(payload.get("display_name") or "").strip()
        emails = [str(e).strip() for e in (payload.get("emails") or []) if str(e).strip()]
        phones = [str(p).strip() for p in (payload.get("phones") or []) if str(p).strip()]
        notes = payload.get("notes")
        source = ContactSource(payload.get("source") or ContactSource.RELAY.value)
        timestamp = payload.get("timestamp") or _now()
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        existing = self._contacts.get(person_id)
        if existing is None:
            created_at = _now()
            contact = Contact(
                person_id=person_id,
                display_name=display_name,
                emails=emails,
                phones=phones,
                notes=notes,
                is_vip=bool(payload.get("is_vip", False)),
                source=source,
                created_at=created_at,
                last_updated_at=created_at,
            )
        else:
            contact = existing
            contact.display_name = display_name or contact.display_name
            contact.emails = _merge(contact.emails, emails)
            contact.phones = _merge(contact.phones, phones)
            if notes is not None:
                contact.notes = notes
            contact.source = source
            contact.last_updated_at = _now()
        self._contacts[person_id] = contact
        return {"contact": contact, "created": existing is None}

    # -- queries -------------------------------------------------------------
    def list_contacts(self, vip_only: bool = False) -> list[Contact]:
        """People, ordered by ``display_name`` (case-insensitive, stable) with
        the optional ``vip_only`` filter (prompt2 §12 VIP list)."""
        contacts = self._contacts.values()
        if vip_only:
            contacts = (c for c in contacts if c.is_vip)
        return sorted(
            contacts,
            key=lambda c: (c.display_name.lower(), c.person_id),
        )

    def get_person(self, person_id: str) -> Contact | None:
        """One resolved person by ``person_id``, or ``None`` when unknown."""
        return self._contacts.get(person_id)

    # -- VIP flag (§12) ------------------------------------------------------
    def set_vip(self, person_id: str, vip: bool) -> Contact | None:
        """Toggle the VIP flag on a known person; ``None`` when unknown."""
        contact = self._contacts.get(person_id)
        if contact is None:
            return None
        contact.is_vip = bool(vip)
        contact.last_updated_at = _now()
        return contact

    # -- seeding / tests -----------------------------------------------------
    def seed_demo(self) -> None:
        """Dev-mode seeder (``NERVE_SEED_CONTACTS=1``): a small, realistic
        set of resolved people (at least one VIP) so the Contacts screen has
        content before the relay posts real traffic."""
        base = _now()
        self.ingest({
            "person_id": "alice-nguyen",
            "display_name": "Alice Nguyen",
            "emails": ["alice.n@example.com"],
            "phones": ["+1 415-555-0134"],
            "notes": "Design partner — prefers email.",
            "is_vip": False,
            "source": ContactSource.RELAY.value,
            "timestamp": base,
        })
        self.ingest({
            "person_id": "bob-cho",
            "display_name": "Bob Cho",
            "emails": ["bob.cho@example.com"],
            "phones": ["+1 202-555-0199"],
            "notes": None,
            "is_vip": False,
            "source": ContactSource.RELAY.value,
            "timestamp": base,
        })
        self.ingest({
            "person_id": "dr-smith",
            "display_name": "Dr. Smith",
            "emails": ["frontdesk@smithclinic.example.com"],
            "phones": ["+1 415-555-0100"],
            "notes": "Call before 5 PM — clinic closes early.",
            "is_vip": True,
            "source": ContactSource.MANUAL.value,
            "timestamp": base,
        })


# -- process-wide singleton (mirrors the P0 email service) --------------------
_service: ContactsService | None = None


def get_contacts_service() -> ContactsService:
    global _service
    if _service is None:
        _service = ContactsService()
    return _service


def reset_contacts_service() -> None:
    """Test hook — replace the singleton with a fresh, empty service."""
    global _service
    _service = ContactsService()
