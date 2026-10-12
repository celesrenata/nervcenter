"""Contacts endpoints (prompt2 Phase P4 — cross-channel person resolution).

Contract:
- ``GET  /api/contacts``                       → resolved people (optional
                                                  ``?vip_only=true|false``)
- ``POST /api/contacts/ingest``                → upsert one normalized person
                                                  record from the Personal
                                                  Relay (201 new / 200 update)
- ``GET  /api/contacts/{person_id}``           → one resolved person
- ``POST /api/contacts/{person_id}/vip``       → toggle the VIP flag (§12),
                                                  body ``{"vip": bool}``

The store lives in the process-wide :func:`backend.contacts.get_contacts_service`
singleton (bound onto ``app.state.contacts_service`` at startup). It is
*always* available — an empty store returns an empty list. This is the
NerveCenter-side person-resolution record only (§79): the source-side relay
normalizes and posts the record here (out of scope, §46/§47) and the
attention engine weighs the stored VIP flag heavier (§22/§45) — neither is
done in-process here. Ingestion is an idempotent upsert by ``person_id``: the
same person re-ingested with an extra email/phone *updates* the record, it is
never a duplicate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from backend.api.models import (
    ApiResponseMeta,
    Contact,
    ContactSource,
    ListResponse,
)
from backend.contacts.service import ContactsService, get_contacts_service

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def _meta(**pagination: int | None) -> ApiResponseMeta:
    return ApiResponseMeta(
        version="1.0.0",
        request_id=f"req-{uuid4().hex[:12]}",
        timestamp=datetime.now(UTC),
        pagination={k: v for k, v in pagination.items() if v is not None} or None,
    )


def _service(request: Request) -> ContactsService:
    svc = getattr(request.app.state, "contacts_service", None)
    if svc is None:
        # Defensive: the singleton is always resolvable even if startup wiring
        # has not run yet (e.g. unit tests hitting the router directly).
        svc = get_contacts_service()
        request.app.state.contacts_service = svc
    return svc


def _person_not_found(person_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Contact {person_id} not found.")


# -- request models ----------------------------------------------------------
class IngestContactRequest(BaseModel):
    """One normalized *resolved person* record as posted by the Personal Relay (§79).

    The source-side relay has already resolved the person (one ``person_id``
    per human) and normalized the emails/phones; this is the NerveCenter-side
    contract only (§46/§47 out of scope). ``source`` is typed as the
    ``ContactSource`` enum so an unknown provenance is a Pydantic 422, not a
    stored error.
    """

    person_id: str
    display_name: str
    emails: list[str] = []
    phones: list[str] = []
    notes: str | None = None
    is_vip: bool = False
    source: ContactSource = ContactSource.RELAY
    timestamp: datetime | None = None

    @field_validator("person_id", "display_name")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must be a non-empty string")
        return value

    @field_validator("emails", "phones")
    @classmethod
    def _clean_list(cls, value: list[str]) -> list[str]:
        return [v.strip() for v in value if v and v.strip()]


# -- response models ---------------------------------------------------------
class IngestContactResponse(BaseModel):
    contact: Contact
    created: bool


class VipContactResponse(BaseModel):
    contact: Contact


class VipRequest(BaseModel):
    """VIP toggle body (§12)."""

    vip: bool


# -- routes -----------------------------------------------------------------
@router.get("", response_model=ListResponse)
@router.get("/", response_model=ListResponse)
async def list_contacts(
    request: Request, vip_only: bool = False
) -> ListResponse:
    """List resolved people, ordered by display name (case-insensitive,
    stable); ``vip_only=true`` returns the VIP list only (§12)."""
    svc = _service(request)
    contacts = svc.list_contacts(vip_only=vip_only)
    total = len(contacts)
    return ListResponse(
        data=[c.model_dump(mode="json") for c in contacts],
        meta=_meta(total=total, page=1, per_page=total or 0),
    )


@router.post("/ingest", response_model=IngestContactResponse)
async def ingest_contact(
    request: Request, payload: IngestContactRequest, response: Response
) -> IngestContactResponse:
    """Upsert one normalized person record. 201 on a new ``person_id`` (created),
    200 when the record already existed and was updated (idempotent upsert —
    the relay replays/updates the same person as it learns new addresses)."""
    svc = _service(request)
    result = svc.ingest(payload.model_dump())
    response.status_code = 200 if not result["created"] else 201
    return IngestContactResponse(contact=result["contact"], created=result["created"])


@router.get("/{person_id}", response_model=Contact)
async def get_person(request: Request, person_id: str) -> Contact:
    """One resolved person by ``person_id`` (honest 404 when unknown)."""
    svc = _service(request)
    contact = svc.get_person(person_id)
    if contact is None:
        raise _person_not_found(person_id)
    return contact


@router.post("/{person_id}/vip", response_model=VipContactResponse)
async def set_vip(
    request: Request, person_id: str, payload: VipRequest
) -> VipContactResponse:
    """Toggle the VIP flag on a known person (§12). The attention engine reads
    the flag; this service only stores/returns it (honest 404 when unknown)."""
    svc = _service(request)
    contact = svc.set_vip(person_id, payload.vip)
    if contact is None:
        raise _person_not_found(person_id)
    return VipContactResponse(contact=contact)
