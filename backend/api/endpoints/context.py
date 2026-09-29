"""Context compilation API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/context",
    tag="context",
    service_name="context",
    method_names=("list", "compile"),
)
