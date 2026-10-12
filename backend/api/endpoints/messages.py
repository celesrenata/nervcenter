"""Messages endpoints (prompt2 Phase P1 — Personal Operations Plane).

Contract:
- ``GET  /api/messages``                          → reconstructed threads
                                                       (optionally filtered by channel)
- ``POST /api/messages/ingest``                    → ingest one normalized
                                                       message from the Personal
                                                       Relay (201 new / 200 dup)
- ``POST /api/messages/persons``                  → cross-channel person
                                                       resolution (§76)
- ``GET  /api/messages/{conversation_id}``        → one thread (conversation
                                                       + its messages,
                                                       chronological)
- ``POST /api/messages/{conversation_id}/acknowledge`` → mark read + resolve
                                                       its AttentionItem
- ``POST /api/messages/{conversation_id}/draft``  → suggested reply
                                                       (§13: AI drafts, human sends)

The store lives in the process-wide :func:`backend.messages.get_messages_service`
singleton (bound onto ``app.state.messages_service`` at startup). It is
*always* available — an empty inbox returns an empty list. Ingestion produces
AttentionItems through the shared P0 :class:`AttentionService` scorer, so the
Messages→Attention link is deterministic and explainable (§21/§22/§76).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from backend.api.models import (
    ApiResponseMeta,
    AttentionItem,
    Conversation,
    ListResponse,
    Message,
    MessageDirection,
)
from backend.messages.service import MessagesService, get_messages_service

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _meta(**pagination: int | None) -> ApiResponseMeta:
    return ApiResponseMeta(
        version="1.0.0",
        request_id=f"req-{uuid4().hex[:12]}",
        timestamp=datetime.now(UTC),
        pagination={k: v for k, v in pagination.items() if v is not None} or None,
    )


def _service(request: Request) -> MessagesService:
    svc = getattr(request.app.state, "messages_service", None)
    if svc is None:
        # Defensive: the singleton is always resolvable even if startup wiring
        # has not run yet (e.g. unit tests hitting the router directly).
        svc = get_messages_service()
        request.app.state.messages_service = svc
    return svc


def _conv_not_found(conversation_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found.")


# -- request models ----------------------------------------------------------
class IngestRequest(BaseModel):
    """One normalized message as posted by the macOS Personal Relay (§46/§47)."""

    message_id: str
    direction: MessageDirection = MessageDirection.INBOUND
    peer_identifier: str
    peer_name: str | None = None
    body: str = ""
    channel: str = "imessage"
    timestamp: datetime | None = None
    source: str = "personal-relay"


class PersonRequest(BaseModel):
    identifier: str
    name: str
    channels: list[str] = []


# -- response models ---------------------------------------------------------
class IngestResponse(BaseModel):
    message: Message
    conversation: Conversation
    new_attention: AttentionItem | None = None
    duplicate: bool = False


class ThreadResponse(BaseModel):
    conversation: Conversation
    messages: list[Message]


class AcknowledgeResponse(BaseModel):
    conversation: Conversation
    attention_id: str | None = None
    resolved: bool = False


class DraftResponse(BaseModel):
    conversation_id: str
    to: str | None = None
    draft: str | None = None
    basis: str


class PersonResponse(BaseModel):
    identifier: str
    name: str
    updated_conversations: list[str] = []


# -- routes -----------------------------------------------------------------
@router.get("", response_model=ListResponse)
@router.get("/", response_model=ListResponse)
async def list_conversations(
    request: Request,
    channel: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1),
    offset: int = Query(default=0, ge=0),
) -> ListResponse:
    """List reconstructed threads, most recently active first (§76)."""
    svc = _service(request)
    convs = svc.list_conversations(channel=channel)
    total = len(convs)
    page = convs[offset : offset + limit]
    return ListResponse(
        data=[c.model_dump(mode="json") for c in page],
        meta=_meta(total=total, page=offset // max(limit, 1) + 1, per_page=limit),
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_message(
    request: Request, payload: IngestRequest, response: Response
) -> IngestResponse:
    """Ingest one normalized message. 201 on a new message, 200 on a replayed
    duplicate id (the relay replays queued events on reconnect — §48)."""
    svc = _service(request)
    result = svc.ingest(payload.model_dump())
    response.status_code = 200 if result["duplicate"] else 201
    return IngestResponse(
        message=result["message"],
        conversation=result["conversation"],
        new_attention=result["new_attention"],
        duplicate=result["duplicate"],
    )


@router.post("/persons", response_model=PersonResponse)
async def register_person(request: Request, payload: PersonRequest) -> PersonResponse:
    """Cross-channel person resolution (§76): bind a name to a raw identifier."""
    svc = _service(request)
    updated = svc.register_person(payload.identifier, payload.name, payload.channels)
    return PersonResponse(
        identifier=payload.identifier,
        name=payload.name,
        updated_conversations=updated,
    )


@router.get("/{conversation_id}", response_model=ThreadResponse)
async def get_conversation(request: Request, conversation_id: str) -> ThreadResponse:
    """One thread: the conversation summary plus its messages, chronological."""
    svc = _service(request)
    conv = svc.get_conversation(conversation_id)
    if conv is None:
        raise _conv_not_found(conversation_id)
    return ThreadResponse(conversation=conv, messages=svc.get_messages(conversation_id))


@router.post("/{conversation_id}/acknowledge", response_model=AcknowledgeResponse)
async def acknowledge_conversation(request: Request, conversation_id: str) -> AcknowledgeResponse:
    """Mark the thread read; resolves its AttentionItem if one is live."""
    svc = _service(request)
    conv = svc.acknowledge(conversation_id)
    if conv is None:
        raise _conv_not_found(conversation_id)
    return AcknowledgeResponse(
        conversation=conv,
        attention_id=conv.attention_id,
        resolved=conv.attention_id is not None,
    )


@router.post("/{conversation_id}/draft", response_model=DraftResponse)
async def draft_reply(request: Request, conversation_id: str) -> DraftResponse:
    """Suggested reply for the thread's latest inbound (§13: AI drafts, human
    sends). Nothing is sent from here."""
    svc = _service(request)
    if svc.get_conversation(conversation_id) is None:
        raise _conv_not_found(conversation_id)
    result: dict[str, Any] = svc.draft_reply(conversation_id)
    return DraftResponse(**result)
