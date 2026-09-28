"""API surface: HTTP/gRPC interface for the NerveCenter core.

This package provides the HTTP API surface for all backend services,
including:
- Core service endpoints (agents, goals, tasks, evidence, knowledge)
- Observability endpoints (health, metrics, tracing)
- Authentication and authorization
- API versioning
- OpenAPI documentation
"""
from backend.api.app import app
from backend.api.endpoints import agents, goals, tasks, evidence, knowledge
from backend.api.observability import router as observability_router
from backend.api.auth import router as auth_router
from backend.api.models import *
from backend.api.versioning import router as versioning_router, API_VERSIONS, CURRENT_VERSION

__all__ = [
    "app",
    "agents",
    "goals",
    "tasks",
    "evidence",
    "knowledge",
    "observability_router",
    "auth_router",
    "versioning_router",
    "API_VERSIONS",
    "CURRENT_VERSION",
]
