"""Agent and task run API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/runs",
    tag="runs",
    service_name="agents",
    method_names=("list_runs", "list_all"),
)
