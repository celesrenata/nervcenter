"""NerveCenter FastAPI application wiring.

Both the module-level :data:`app` instance and :func:`create_app` expose the
full spec §46 API surface: the legacy core collections (``/agents``,
``/goals``, ``/tasks``, ``/knowledge``), the canonical ``/api/*`` aliases for
those collections, the event/entity/evidence routers, all twelve read-only
collection routers, and the dependency-tolerant health endpoints.
"""
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    entities,
    events,
    evidence,
    goals,
    incidents,
    knowledge,
    models,
    relationships,
    routes,
    runs,
    search,
    tasks,
)
from backend.api.health import router as health_router
from backend.api.observability import router as observability_router

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
)


def canonical_aliases() -> APIRouter:
    """Build the canonical ``/api/goals``/``/api/tasks``/``/api/agents`` aliases.

    The legacy routers live under ``/goals``, ``/tasks`` and ``/agents``; the
    spec §46 canonical paths must resolve without trailing-slash redirects, so
    these thin handlers delegate to the original implementations.
    """
    alias = APIRouter(tags=["canonical-aliases"])

    @alias.get("/api/goals")
    async def api_list_goals():
        """List goals under the canonical prefix."""
        return await goals.list_goals()

    @alias.get("/api/goals/{goal_id}")
    async def api_get_goal(goal_id: str):
        """Get a goal by ID under the canonical prefix."""
        return await goals.get_goal(goal_id)

    @alias.get("/api/tasks")
    async def api_list_tasks():
        """List tasks under the canonical prefix."""
        return await tasks.list_tasks()

    @alias.get("/api/tasks/{task_id}")
    async def api_get_task(task_id: str):
        """Get a task by ID under the canonical prefix."""
        return await tasks.get_task(task_id)

    @alias.get("/api/agents")
    async def api_list_agents():
        """List agents under the canonical prefix."""
        return await agents.list_agents()

    @alias.get("/api/agents/{agent_id}")
    async def api_get_agent(agent_id: str):
        """Get an agent by ID under the canonical prefix."""
        return await agents.get_agent(agent_id)

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


app = FastAPI(
    title="NerveCenter API",
    description="HTTP/gRPC interface for the NerveCenter core",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)
_configure(app)


@app.on_event("startup")
async def setup_openapi():
    """Setup OpenAPI schema on startup"""
    app.openapi_schema = custom_openapi(app)


def create_app() -> FastAPI:
    """Factory function for creating and configuring the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    new_app = FastAPI(
        title="NerveCenter API",
        description="HTTP/gRPC interface for the NerveCenter core",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    _configure(new_app)

    @new_app.on_event("startup")
    async def setup_openapi():
        """Setup OpenAPI schema on startup"""
        new_app.openapi_schema = custom_openapi(new_app)

    return new_app
