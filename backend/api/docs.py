"""API documentation utilities."""
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def custom_openapi(app: FastAPI):
    """Generate custom OpenAPI schema."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="NerveCenter API",
        version="0.1.0",
        description="HTTP/gRPC interface for the NerveCenter core",
        routes=app.routes,
    )

    # Add authentication security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    }

    # Add global security requirement
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return openapi_schema


def get_version_info() -> dict:
    """Get API version information."""
    return {
        "version": "0.1.0",
        "release_date": "2026-09-28",
        "compatible_versions": ["0.1.x"],
        "endpoints": {
            "base": "/api/v1",
            "auth": "/auth",
            "observability": "/observability",
        },
    }