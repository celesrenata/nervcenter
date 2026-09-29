"""Compute registry API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/compute",
    tag="compute",
    service_name="connectors",
    method_names=("list_compute", "health_all"),
)
