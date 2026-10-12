"""Email plane (prompt2 Phase P0) — package exports."""

from backend.email.service import (
    EmailService,
    get_email_service,
    reset_email_service,
)

__all__ = ["EmailService", "get_email_service", "reset_email_service"]
