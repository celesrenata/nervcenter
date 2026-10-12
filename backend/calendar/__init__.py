"""Calendar plane (prompt2 Phase P2 — Calendar Integration & Conflict Reasoning)."""

from backend.calendar.service import (
    CalendarService,
    get_calendar_service,
    reset_calendar_service,
)

__all__ = ["CalendarService", "get_calendar_service", "reset_calendar_service"]
