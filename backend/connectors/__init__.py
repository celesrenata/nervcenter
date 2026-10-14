"""External connector plane (prompt2 §46 — the Personal Relay owns source-side
capture; this plane only *registers* connectors and reports their liveness).

NerveCenter never touches a mailbox itself — the macOS Personal Relay captures
and ingests (§47). What NerveCenter does own here is the user-facing *registry*
of mail connectors: where the relay should read from, which auth method is in
use, and whether that connector currently answers. The connector is a
description + a live probe, not a live socket held by the backend.
"""

from backend.connectors.mail import (
    MailConnector,
    MailConnectorService,
    get_mail_connector_service,
    reset_mail_connector_service,
)

__all__ = [
    "MailConnector",
    "MailConnectorService",
    "get_mail_connector_service",
    "reset_mail_connector_service",
]
