"""Client registration API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/clients",
    tag="clients",
    service_name="clients",
    method_names=("list_clients", "list"),
)
