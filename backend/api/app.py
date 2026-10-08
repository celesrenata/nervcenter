"""NerveCenter FastAPI application wiring.

Both the module-level :data:`app` instance and :func:`create_app` expose the
full spec §46 API surface: the legacy core collections (``/agents``,
``/goals``, ``/tasks``, ``/knowledge``), the canonical ``/api/*`` aliases for
those collections, the event/entity/evidence routers, all twelve read-only
collection routers, and the dependency-tolerant health endpoints.

T208: The backend honours X-Forwarded-Proto via uvicorn's proxy_headers flag.
When uvicorn is started with ``--proxy-headers --forwarded-allow-ips``, it
modifies the request scope ``scheme`` and ``client`` based on X-Forwarded-*
headers, preventing 307 redirects to http:// behind TLS-terminating ingresses.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth import approvals_router as auth_approvals_router
from backend.api.auth import router as auth_router
from backend.api.docs import custom_openapi, get_version_info
from backend.api.endpoints import (
    agents,
    approvals,
    changes,
    claims,
    clients,
    compute,
    context,
    decisions,
    entities,
    events,
    evidence,
    goals,
    incidents,
    knowledge,
    metrics,
    models,
    models_history,
    overview,
    relationships,
    routes,
    runs,
    search,
    systems,
    tasks,
)
from backend.api.health import router as health_router
from backend.api.observability import router as observability_router
from backend.api.wiring import install_dependency_wiring


ALL_ROUTERS = (
    agents.router,
    goals.router,
    tasks.router,
    evidence.router,
    knowledge.router,
    events.router,
    entities.router,
    relationships.router,
    claims.router,
    search.router,
    context.router,
    runs.router,
    incidents.router,
    models.router,
    compute.router,
    routes.router,
    changes.router,
    approvals.router,
    clients.router,
    health_router,
    observability_router,
    auth_router,
    auth_approvals_router,
    overview.router,
    decisions.router,
    systems.router,
    models_history.router,
    metrics.router,
)


def canonical_aliases() -> APIRouter:
    """Build the canonical ``/api/agents`` read aliases.

    Goals and tasks now serve their canonical ``/api/goals`` / ``/api/tasks``
    read AND write routes directly from :mod:`backend.api.endpoints.goals`
    and :mod:`backend.api.endpoints.tasks` (see the spec §46 contract and T-H33
    write/mutation work). The alias router therefore only covers the legacy
    read routes that no endpoint module owns under the ``/api`` prefix.
    """
    alias = APIRouter(tags=["canonical-aliases"])

    @alias.get("/api/agents")
    async def api_list_agents():
        """List agents under the canonical prefix."""
        return await agents.list_agents()

    @alias.get("/api/agents/{agent_id}")
    async def api_get_agent(agent_id: str):
        """Get an agent by ID under the canonical prefix."""
        return await agents.get_agent(agent_id)

    @alias.get("/api/overview")
    async def api_get_overview():
        """Get overview data under the canonical prefix."""
        return await overview.get_overview()

    @alias.get("/api/decisions")
    async def api_list_decisions():
        """List decisions under the canonical prefix."""
        return await decisions.list_decisions()

    @alias.get("/api/decisions/{decision_id}")
    async def api_get_decision(decision_id: str):
        """Get a decision by ID under the canonical prefix."""
        return await decisions.get_decision(decision_id)

    return alias


def _configure(target: FastAPI) -> None:
    """Attach CORS middleware, every router, and the version endpoint."""
    target.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in ALL_ROUTERS:
        target.include_router(router)
    target.include_router(canonical_aliases())

    @target.get("/version")
    async def version():
        """Get API version information"""
        return get_version_info()


def create_app() -> FastAPI:
    """Factory function for creating and configuring the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    target = FastAPI(
        title="NerveCenter API",
        description="HTTP/gRPC interface for the NerveCenter core",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    _configure(target)
    install_dependency_wiring(target)

    return target


app = create_app()
