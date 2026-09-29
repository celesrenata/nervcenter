"""Logical model registry API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/models",
    tag="models",
    service_name="inference",
    method_names=("list_models", "get_all_metrics"),
)
