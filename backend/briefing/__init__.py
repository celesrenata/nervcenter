"""Briefing plane (prompt2 §30 — Briefings) — package exports.

A read-only, deterministic aggregation across the personal-operations planes
(attention, waiting-on, calendar, email, messages, voicemail). See
:mod:`backend.briefing.service` for the design notes.
"""

from backend.briefing.service import (
    BriefingService,
    get_briefing_service,
    reset_briefing_service,
)

__all__ = ["BriefingService", "get_briefing_service", "reset_briefing_service"]
