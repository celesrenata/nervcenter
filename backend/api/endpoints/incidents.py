"""Incident API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/incidents",
    tag="incidents",
    service_name="orchestration",
    method_names=("list_incidents", "list"),
)
