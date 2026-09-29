"""Approval API adapters."""

from backend.api.endpoints._helpers import make_read_router

router = make_read_router(
    prefix="/api/approvals",
    tag="approvals",
    service_name="policy",
    method_names=("list_approvals", "list"),
)
