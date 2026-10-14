"""Mail connector registry (prompt2 §46 — connector registry + liveness).

The :class:`MailConnectorService` is the user-facing registry of mail
connectors: what the relay reads from and whether that mailbox answers. It is
an *in-process singleton* (no engine, no DB) — exactly the shape the P0
:class:`backend.email.EmailService` uses — so tests get a fresh app via
``create_app()`` and a fresh service via :func:`reset_mail_connector_service`.

Liveness is not held by the backend: registering a connector is a no-op with
respect to any mailbox. ``verify()`` runs one liveness probe through the
injected :class:`~backend.connectors.mail.imap_client.ImapClient` and maps the
result onto the connector's ``status`` (CONNECTED / AUTH_EXPIRED / ERROR) and
``last_checked_at``. The credential is supplied per-call (it is never stored —
only the opaque ``token_ref`` is).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.api.models import (
    MailAuthMethod,
    MailConnector,
    MailConnectorStatus,
)
from backend.connectors.mail.imap_client import (
    ImapClient,
    ImapImapClient,
    ImapProbeResult,
)

__all__ = [
    "MailConnectorService",
    "get_mail_connector_service",
    "reset_mail_connector_service",
]


def _now() -> datetime:
    return datetime.now(UTC)


def _coerce_enum(value: str | None, enum_cls: type, default: Any) -> Any:
    """Tolerate both enum members and their raw string values from JSON."""
    if value is None:
        return default
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError:
        return default


class MailConnectorNotFoundError(Exception):
    """Raised when an operation targets an unregistered connector."""

    def __init__(self, connector_id: str) -> None:
        self.connector_id = connector_id
        super().__init__(f"Mail connector {connector_id!r} not found.")


class MailConnectorService:
    """In-memory mail-connector registry + liveness probe (§46)."""

    def __init__(self, client: ImapClient | None = None) -> None:
        self._client = client or ImapImapClient()
        self._connectors: dict[str, MailConnector] = {}

    # -- registry ------------------------------------------------------------
    def create(self, payload: dict[str, Any]) -> MailConnector:
        """Register a new connector. Credentials are *not* part of the payload
        — only the opaque ``token_ref`` where they are kept (§47)."""
        connector_id = str(payload.get("connector_id") or f"mc-{uuid4().hex[:12]}")
        if connector_id in self._connectors:
            raise ValueError(f"connector {connector_id!r} already registered")

        now = _now()
        connector = MailConnector(
            connector_id=connector_id,
            account=str(payload.get("account", "Default")),
            mailbox=str(payload.get("mailbox", "")),
            host=str(payload.get("host", "")),
            port=int(payload.get("port", 993)),
            ssl=bool(payload.get("ssl", True)),
            auth_method=_coerce_enum(
                payload.get("auth_method"), MailAuthMethod, MailAuthMethod.OAUTH2
            ),
            status=MailConnectorStatus.PENDING,
            token_ref=payload.get("token_ref"),
            scope=payload.get("scope"),
            last_checked_at=None,
            last_error=None,
            created_at=now,
            updated_at=now,
        )
        self._connectors[connector_id] = connector
        return connector

    def get(self, connector_id: str) -> MailConnector:
        try:
            return self._connectors[connector_id]
        except KeyError as exc:
            raise MailConnectorNotFoundError(connector_id) from exc

    def list(self) -> list[MailConnector]:
        """All connectors, most recently updated first."""
        return sorted(
            self._connectors.values(),
            key=lambda c: c.updated_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

    def update(self, connector_id: str, changes: dict[str, Any]) -> MailConnector:
        """Partial update of registry fields. The credential is never updatable
        here — re-run :meth:`verify` with the new credential to re-probe."""
        connector = self.get(connector_id)
        allowed = {
            "account", "mailbox", "host", "port", "ssl",
            "auth_method", "token_ref", "scope",
        }
        for key, value in changes.items():
            if key not in allowed:
                continue
            if key == "auth_method":
                value = _coerce_enum(value, MailAuthMethod, connector.auth_method)
            elif key == "port":
                value = int(value)
            elif key == "ssl":
                value = bool(value)
            setattr(connector, key, value)
        connector.updated_at = _now()
        # A changed host/port/auth means the last probe no longer applies.
        connector.status = MailConnectorStatus.PENDING
        connector.last_error = None
        return connector

    def delete(self, connector_id: str) -> None:
        if connector_id not in self._connectors:
            raise MailConnectorNotFoundError(connector_id)
        del self._connectors[connector_id]

    # -- liveness ------------------------------------------------------------
    def verify(
        self, connector_id: str, *, username: str, password: str
    ) -> MailConnector:
        """Run one liveness probe against the connector's mailbox and update
        its status. The ``password`` (or OAuth access token) is supplied
        per-call and never persisted — only the probe *result* is."""
        connector = self.get(connector_id)
        result = self._client.probe(
            host=connector.host,
            port=connector.port,
            ssl=connector.ssl,
            username=username,
            password=password,
        )
        connector.last_checked_at = _now()
        connector.updated_at = connector.last_checked_at
        connector.last_error = result.error
        if result.outcome is ImapProbeResult.OK:
            connector.status = MailConnectorStatus.CONNECTED
        elif result.outcome is ImapProbeResult.AUTH_FAILED:
            connector.status = MailConnectorStatus.AUTH_EXPIRED
        else:
            connector.status = MailConnectorStatus.ERROR
        return connector

    def set_status(self, connector_id: str, status: MailConnectorStatus) -> MailConnector:
        """Flip a connector's status (e.g. disable) without a probe."""
        connector = self.get(connector_id)
        connector.status = status
        connector.updated_at = _now()
        return connector

    # -- seeding / tests -----------------------------------------------------
    def seed_demo(self) -> None:
        """Dev-mode seeder so the Connectors screen has content before the user
        registers a real connector."""
        if self._connectors:
            return
        now = _now()
        self._connectors["mc-demo-work"] = MailConnector(
            connector_id="mc-demo-work",
            account="Work",
            mailbox="you@work.example",
            host="imap.gmail.com",
            port=993,
            ssl=True,
            auth_method=MailAuthMethod.OAUTH2,
            status=MailConnectorStatus.CONNECTED,
            token_ref="keychain:work-imap-token",
            scope="imap.client.read",
            last_checked_at=now,
            last_error=None,
            created_at=now,
            updated_at=now,
        )


# -- process-wide singleton (mirrors the P0 email service) --------------------
_service: MailConnectorService | None = None


def get_mail_connector_service() -> MailConnectorService:
    global _service
    if _service is None:
        _service = MailConnectorService()
    return _service


def reset_mail_connector_service() -> None:
    """Test hook — replace the singleton with a fresh, empty service."""
    global _service
    _service = MailConnectorService()
