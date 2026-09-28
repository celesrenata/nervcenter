from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.endpoints import agents, goals, tasks, evidence, knowledge
from backend.api.observability import router as observability_router
from backend.api.auth import router as auth_router
from backend.api.docs import custom_openapi, get_version_info

app = FastAPI(
    title="NerveCenter API",
    description="HTTP/gRPC interface for the NerveCenter core",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agents.router)
app.include_router(goals.router)
app.include_router(tasks.router)
app.include_router(evidence.router)
app.include_router(knowledge.router)
app.include_router(observability_router)
app.include_router(auth_router)

# Version endpoint
@app.get("/version")
async def version():
    """Get API version information"""
    return get_version_info()


@app.on_event("startup")
async def setup_openapi():
    """Setup OpenAPI schema on startup"""
    app.openapi_schema = custom_openapi(app)
