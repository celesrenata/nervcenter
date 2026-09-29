"""Core service endpoints for the NerveCenter API."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["core"])


@router.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to the NerveCenter API"}
