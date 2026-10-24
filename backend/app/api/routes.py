"""Versioned API routes."""

from fastapi import APIRouter

from app.db.connection import check_database

router = APIRouter(prefix="/api/v1")


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Report that the API process is responding."""
    return {"status": "ok", "service": "fdr-guardian-api"}


@router.get("/health/database", tags=["health"])
def database_health() -> dict[str, str]:
    """Check configured PostgreSQL connectivity without exposing credentials."""
    return check_database()
