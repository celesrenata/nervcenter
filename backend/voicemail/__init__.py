"""Voicemail plane (prompt2 Phase P3) — package exports."""

from backend.voicemail.service import (
    VoicemailService,
    get_voicemail_service,
    reset_voicemail_service,
)

__all__ = ["VoicemailService", "get_voicemail_service", "reset_voicemail_service"]
