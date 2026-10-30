"""Health and status endpoints."""

from fastapi import APIRouter
from app.config import settings
from app.api.deps import get_db_backend, is_exasol

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


@router.get("/api/health/exasol", tags=["Health"])
async def exasol_health():
    """
    Exasol-specific health check.

    Returns:
    - Connection status
    - Schema name
    - Table row counts for all HandoffGuard tables
    - Latest logger reading timestamp
    - Whether logger_readings has no handoff_id (contract verification)
    """
    if not is_exasol():
        return {
            "status": "not_configured",
            "engine": settings.database_engine,
            "detail": (
                "DATABASE_ENGINE is not set to 'exasol'. "
                "Set DATABASE_ENGINE=exasol in your .env file to use this endpoint."
            ),
        }

    backend = get_db_backend()
    db_health = await backend.health_check()

    # Verify the logger_readings table has no handoff_id column (contract check)
    handoff_id_absent = True
    try:
        from app.infrastructure.db.exasol_pool import get_pool
        pool = get_pool()
        col_rows = await pool.execute(
            "SELECT COLUMN_NAME FROM SYS.EXA_ALL_COLUMNS "
            "WHERE COLUMN_SCHEMA = 'HANDOFFGUARD' "
            "  AND COLUMN_TABLE   = 'LOGGER_READINGS' "
            "  AND COLUMN_NAME    = 'HANDOFF_ID'"
        )
        handoff_id_absent = len(col_rows) == 0
    except Exception:
        handoff_id_absent = None  # type: ignore

    return {
        "status": "healthy" if db_health.get("db_status") == "ok" else "error",
        "engine": "exasol",
        "dsn": db_health.get("dsn"),
        "schema": db_health.get("schema"),
        "detail": db_health.get("detail"),
        "table_counts": db_health.get("table_counts", {}),
        "latest_reading_utc": db_health.get("latest_reading_utc"),
        "contract_check": {
            "logger_readings_has_no_handoff_id": handoff_id_absent,
            "description": (
                "logger_readings must have no handoff_id column. "
                "Handoff association is derived via interval join on reading_at_utc."
            ),
        },
    }
