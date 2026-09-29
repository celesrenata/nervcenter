"""Read-only relationship API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/relationships",
    tag="relationships",
    service_name="knowledge",
    method_names=("list_relationships", "active_snapshot"),
)
