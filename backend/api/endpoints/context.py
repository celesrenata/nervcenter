"""Context compilation API adapters."""

from backend.api.endpoints._helpers import make_read_router, make_write_endpoint

router = make_read_router(
    prefix="/api/context",
    tag="context",
    service_name="context",
    method_names=("list", "compile"),
)

# §47 `nerve ask "..."` → POST /api/context/ask
# Request body: {"question": "..."} ({"query": "..."} is accepted as an alias).
make_write_endpoint(
    router,
    "/ask",
    tag="context",
    service_name="context",
    method_names=("ask", "compile", "list"),
    arg_keys=("question", "query"),
    summary="Ask the context service a question (§47 `nerve ask`)",
)
