"""Health and status endpoint."""

from fastapi import APIRouter
from app.config import settings
from app.api.deps import get_db_backend

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """
    Returns application health status, database connectivity, engine name,
    and schema version.
    """
    backend = get_db_backend()
    db_health = await backend.health_check()

    return {
        "status": "healthy" if db_health.get("db_status") == "ok" else "degraded",
        "database_connection_status": db_health.get("db_status", "unknown"),
        "database_engine_name": db_health.get("db_engine", settings.database_engine),
        "schema_version": settings.schema_version,
        "detail": db_health.get("detail", ""),
    }
