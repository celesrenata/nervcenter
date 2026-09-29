"""Search API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/search",
    tag="search",
    service_name="knowledge",
    method_names=("search", "list_entities"),
)
