"""Planned and observed change API adapters."""

from backend.api.endpoints._helpers import make_read_router, make_write_endpoint

router = make_read_router(
    prefix="/api/changes",
    tag="changes",
    service_name="orchestration",
    method_names=("get_all_changes", "list_changes"),
)

make_write_endpoint(
    router,
    "/stop-mutations",
    tag="changes",
    service_name="orchestration",
    method_names=("stop_mutations", "stop_mutation"),
    summary="Stop in-flight mutations (§47 `nerve stop-mutations`)",
)
