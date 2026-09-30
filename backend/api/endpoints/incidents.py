"""Incident API adapters."""

from backend.api.endpoints._helpers import make_read_router, make_write_endpoint

router = make_read_router(
    prefix="/api/incidents",
    tag="incidents",
    service_name="orchestration",
    method_names=("list_incidents", "list"),
)

# §47 `nerve incident investigate <name>` → POST /api/incidents/investigate
# Request body: {"entity": "..."} ({"name": "..."} is accepted as an alias).
make_write_endpoint(
    router,
    "/investigate",
    tag="incidents",
    service_name="orchestration",
    method_names=("investigate",),
    arg_keys=("entity", "name"),
    summary="Investigate an incident for an entity (§47 `nerve incident investigate`)",
)
