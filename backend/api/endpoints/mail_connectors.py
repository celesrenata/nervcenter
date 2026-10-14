"""Mail connector endpoints (prompt2 §46 — connector registry + liveness).

Contract:
- ``GET    /api/mail-connectors``            → list registered connectors
- ``POST   /api/mail-connectors``            → register a connector (201)
- ``GET    /api/mail-connectors/{id}``       → one connector
- ``PATCH  /api/mail-connectors/{id}``       → partial update (200)
- ``DELETE /api/mail-connectors/{id}``       → remove (204)
- ``POST   /api/mail-connectors/{id}/verify``→ run a liveness probe (200)

The registry lives in the process-wide
:func:`backend.connectors.get_mail_connector_service` singleton (bound onto
``app.state.mail_connector_service`` at startup). It is *always* available — an
unconfigured system returns an empty list, never a fabricated connector.

Liveness is probed, not held (§47): the ``verify`` endpoint accepts the
credential the user just entered, runs one IMAP login probe, and records the
outcome. The secret is never stored — only the opaque ``token_ref`` is.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.api.models import (
    ApiResponseMeta,
    ListResponse,
    MailAuthMethod,
    MailConnector,
    MailConnectorStatus,
)
from backend.connectors.mail import (
    MailConnectorNotFoundError,
    get_mail_connector_service,
)
from backend.connectors.mail.service import MailConnectorService

router = APIRouter(prefix="/api/mail-connectors", tags=["mail-connectors"])


def _meta(**pagination: int | None) -> ApiResponseMeta:
    return ApiResponseMeta(
        version="1.0.0",
        request_id=f"req-{uuid4().hex[:12]}",
        timestamp=datetime.now(UTC),
        pagination={k: v for k, v in pagination.items() if v is not None} or None,
    )


def _service(request: Request) -> MailConnectorService:
    svc = getattr(request.app.state, "mail_connector_service", None)
    if svc is None:
        # Defensive: the singleton is always resolvable even if startup wiring
        # has not run yet (e.g. unit tests hitting the router directly).
        svc = get_mail_connector_service()
        request.app.state.mail_connector_service = svc
    return svc


def _not_found(connector_id: str) -> HTTPException:
    return HTTPException(
        status_code=404, detail=f"Mail connector {connector_id!r} not found."
    )


# -- request models -----------------------------------------------------------
class MailConnectorCreateRequest(BaseModel):
    """Register a mail connector. The credential is never part of the payload —
    only the opaque ``token_ref`` naming where it is kept (§47 secret-free)."""

    connector_id: str | None = None
    account: str = Field(default="Default", description="Human label")
    mailbox: str = Field(default="", description="Account / mailbox id (user@domain)")
    host: str = Field(default="", description="IMAP host")
    port: int = Field(default=993, ge=1, le=65535)
    ssl: bool = True
    auth_method: MailAuthMethod = MailAuthMethod.OAUTH2
    token_ref: str | None = None
    scope: str | None = None


class MailConnectorUpdateRequest(BaseModel):
    """Partial update. Any omitted field is left unchanged."""

    account: str | None = None
    mailbox: str | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    ssl: bool | None = None
    auth_method: MailAuthMethod | None = None
    token_ref: str | None = None
    scope: str | None = None


class MailConnectorVerifyRequest(BaseModel):
    """Run a liveness probe. The credential is supplied per-call and never
    stored — only the probe result is recorded on the connector."""

    username: str
    password: str = Field(default="", description="App password / OAuth access token")


# -- endpoints ----------------------------------------------------------------
@router.get("", response_model=ListResponse)
@router.get("/", response_model=ListResponse)
async def list_mail_connectors(request: Request) -> ListResponse:
    """All registered mail connectors, most recently updated first."""
    service = _service(request)
    rows = service.list()
    data = [row.model_dump(mode="json") for row in rows]
    return ListResponse(
        data=data,
        meta=_meta(total=len(data)),
    )


@router.post("", status_code=201, response_model=MailConnector)
async def create_mail_connector(
    request: Request, payload: MailConnectorCreateRequest
) -> MailConnector:
    """Register a new connector (status starts as PENDING)."""
    service = _service(request)
    schema = payload.model_dump(exclude_unset=True)
    try:
        return service.create(schema)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{connector_id}", response_model=MailConnector)
async def get_mail_connector(request: Request, connector_id: str) -> MailConnector:
    """One connector by id."""
    service = _service(request)
    try:
        return service.get(connector_id)
    except MailConnectorNotFoundError as exc:
        raise _not_found(connector_id) from exc


@router.patch("/{connector_id}", response_model=MailConnector)
async def update_mail_connector(
    request: Request, connector_id: str, payload: MailConnectorUpdateRequest
) -> MailConnector:
    """Partially update registry fields. Re-probes are a separate ``verify``
    call; the credential is never updatable here."""
    service = _service(request)
    changes = payload.model_dump(exclude_unset=True)
    try:
        return service.update(connector_id, changes)
    except MailConnectorNotFoundError as exc:
        raise _not_found(connector_id) from exc


@router.delete("/{connector_id}", status_code=204)
async def delete_mail_connector(request: Request, connector_id: str) -> None:
    """Remove a connector from the registry."""
    service = _service(request)
    try:
        service.delete(connector_id)
    except MailConnectorNotFoundError as exc:
        raise _not_found(connector_id) from exc
    return None


@router.post("/{connector_id}/verify", response_model=MailConnector)
async def verify_mail_connector(
    request: Request, connector_id: str, payload: MailConnectorVerifyRequest
) -> MailConnector:
    """Run one IMAP liveness probe and record the outcome (CONNECTED /
    AUTH_EXPIRED / ERROR). The credential is accepted only to run the probe —
    it is never persisted (only the opaque ``token_ref`` is)."""
    service = _service(request)
    try:
        return service.verify(
            connector_id, username=payload.username, password=payload.password
        )
    except MailConnectorNotFoundError as exc:
        raise _not_found(connector_id) from exc


@router.post("/{connector_id}/disable", response_model=MailConnector)
async def disable_mail_connector(request: Request, connector_id: str) -> MailConnector:
    """Turn a connector off without a probe."""
    service = _service(request)
    try:
        return service.set_status(connector_id, MailConnectorStatus.DISABLED)
    except MailConnectorNotFoundError as exc:
        raise _not_found(connector_id) from exc


@router.post("/{connector_id}/enable", response_model=MailConnector)
async def enable_mail_connector(request: Request, connector_id: str) -> MailConnector:
    """Re-enable a disabled connector (back to PENDING — re-verify to probe)."""
    service = _service(request)
    try:
        return service.set_status(connector_id, MailConnectorStatus.PENDING)
    except MailConnectorNotFoundError as exc:
        raise _not_found(connector_id) from exc


