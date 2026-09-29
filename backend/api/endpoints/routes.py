"""Inference route API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/routes",
    tag="routes",
    service_name="inference",
    method_names=("list_routes", "get_all_metrics"),
)
