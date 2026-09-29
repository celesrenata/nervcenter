"""Connector interface (NerveCenter spec Section 10-16).

Connectors integrate external systems (email, calendar, IM, device integrations,
...) into NerveCenter. The connector interface is a capability manifest plus an
operational state, so the core can discover what a connector can do (push /
pull / subscribe / mutate) and whether it is currently connected.

Assumptions (spec not present in the repository):
    - ``capabilities`` is a classification literal over what a connector can do
      (push, pull, subscribe, mutate, search, stream, auth_only).
    - ``transport`` classifies the delivery mechanism (http, grpc, websocket,
      webhook, local_api, other).
    - ``auth_scheme`` classifies the credential mechanism.
    - This is a *descriptor/interface contract*, not a Python runtime protocol;
      runtime adapters live in ``backend/connectors``.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .base import Record

#: What a connector can do on the NerveCenter side.
ConnectorCapability = Literal[
    "push",
    "pull",
    "subscribe",
    "mutate",
    "search",
    "stream",
    "auth_only",
]

#: Delivery mechanism.
ConnectorTransport = Literal[
    "http",
    "grpc",
    "websocket",
    "webhook",
    "local_api",
    "other",
]

#: Credential scheme.
ConnectorAuthScheme = Literal[
    "none",
    "basic",
    "bearer",
    "oauth2",
    "api_key",
    "mtls",
    "app_specific",
]

#: Operational state of a connector.
ConnectorStatus = Literal["disconnected", "connecting", "connected", "degraded", "disabled"]


class Connector(Record):
    """Descriptor/interface contract for an external-system integration."""

    connector_type: str = Field(
        ...,
        description="Connector kind identifier (e.g. 'email.imap', 'calendar.ics', 'im.slack').",
    )
    name: str = Field(
        ...,
        description="Human-readable name for this connector instance.",
    )
    status: ConnectorStatus = Field(
        default="disconnected",
        description="Current operational state.",
    )
    capabilities: list[ConnectorCapability] = Field(
        default_factory=list,
        description="Capabilities this connector offers to the core.",
    )
    transport: ConnectorTransport = Field(
        default="http",
        description="Delivery mechanism.",
    )
    auth_scheme: ConnectorAuthScheme = Field(
        default="none",
        description="Credential mechanism in use.",
    )
    endpoint: str | None = Field(
        default=None,
        description="Endpoint / URI the connector talks to.",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Non-secret configuration (secrets live in the credential store).",
    )
    credential_ref: str | None = Field(
        default=None,
        description="Reference to the stored credential, if auth is required.",
    )
    last_synced_at: datetime | None = Field(
        default=None,
        description="Last successful sync (UTC).",
    )
    error: str | None = Field(
        default=None,
        description="Most recent error, if the connector is not healthy.",
    )
    emitted_event_types: list[str] = Field(
        default_factory=list,
        description="Event types this connector can emit on the NerveCenter event bus.",
    )
