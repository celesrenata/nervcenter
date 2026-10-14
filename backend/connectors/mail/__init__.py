"""Mail connector plane (prompt2 §46) — package exports."""

from backend.connectors.mail.imap_client import (
    ImapClient,
    ImapImapClient,
    ImapProbeResult,
    ProbeResult,
    StubImapClient,
)
from backend.connectors.mail.oauth import (
    OauthCallback,
    OauthProvider,
    PROVIDERS,
    build_authorization_url,
    exchange_request,
    make_token_ref,
    parse_callback,
    provider,
    validate_token_ref,
)
from backend.connectors.mail.service import (
    MailConnectorNotFoundError,
    MailConnectorService,
    get_mail_connector_service,
    reset_mail_connector_service,
)

__all__ = [
    "ImapClient",
    "ImapImapClient",
    "ImapProbeResult",
    "ProbeResult",
    "StubImapClient",
    "OauthCallback",
    "OauthProvider",
    "PROVIDERS",
    "build_authorization_url",
    "exchange_request",
    "make_token_ref",
    "parse_callback",
    "provider",
    "validate_token_ref",
    "MailConnectorNotFoundError",
    "MailConnectorService",
    "get_mail_connector_service",
    "reset_mail_connector_service",
]
