"""API versioning utilities."""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from backend.api.models import VersionInfo

router = APIRouter()


# Available API versions
API_VERSIONS = {
    "v1": {
        "version": "1.0.0",
        "released": "2026-09-28",
        "status": "stable",
        "endpoints": {
            "base": "/api/v1",
        },
    }
}

CURRENT_VERSION = "v1"


@router.get("/versions", response_model=dict)
async def list_versions():
    """List all available API versions."""
    return {"versions": API_VERSIONS}


@router.get("/current", response_model=VersionInfo)
async def get_current_version():
    """Get current API version information."""
    current = API_VERSIONS.get(CURRENT_VERSION, {})
    return VersionInfo(
        version=current.get("version", "unknown"),
        release_date=current.get("released"),
        compatible_versions=[CURRENT_VERSION],
    )


def version_header_middleware(app):
    """Add version header to responses."""
    from starlette.middleware.base import BaseHTTPMiddleware

    class VersionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            response = await call_next(request)
            response.headers["X-API-Version"] = CURRENT_VERSION
            return response

    app.add_middleware(VersionMiddleware)


def validate_version(version: str):
    """Validate API version."""
    if version not in API_VERSIONS:
        raise HTTPException(
            status_code=404,
            detail=f"API version '{version}' not found",
        )
    return version