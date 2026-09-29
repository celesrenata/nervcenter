"""Read-only claims API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/claims",
    tag="claims",
    service_name="claims",
    method_names=("list_claims", "list"),
)
