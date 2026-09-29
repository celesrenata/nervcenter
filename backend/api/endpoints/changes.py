"""Planned and observed change API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/changes",
    tag="changes",
    service_name="orchestration",
    method_names=("get_all_changes", "list_changes"),
)
