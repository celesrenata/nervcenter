"""Contacts plane (prompt2 Phase P4 — cross-channel person resolution) — package exports."""

from backend.contacts.service import (
    ContactsService,
    get_contacts_service,
    reset_contacts_service,
)

__all__ = ["ContactsService", "get_contacts_service", "reset_contacts_service"]
