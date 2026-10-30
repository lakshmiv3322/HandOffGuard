"""
Dependency injection module for FastAPI routers.

Injects database sessions, repositories, and domain services based on
configured DATABASE_ENGINE ('sqlite', 'postgres', or 'exasol').
"""

from __future__ import annotations

from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.services.attribution_service import AttributionService
from app.core.services.exposure_service import ExposureService
from app.core.services.prevention_service import PreventionService
from app.core.services.timeline_service import TimelineService
from app.infrastructure.db.base import DatabaseBackend
from app.infrastructure.db.dev_db import DevDatabaseBackend
from app.infrastructure.repositories.base import (
    AbstractAttributionRepository,
    AbstractExcursionRepository,
    AbstractHandoffRepository,
    AbstractLoggerRepository,
    AbstractProductRepository,
    AbstractReadingRepository,
    AbstractShipmentRepository,
)
from app.infrastructure.repositories.dev.attribution_repo import DevAttributionRepository
from app.infrastructure.repositories.dev.excursion_repo import DevExcursionRepository
from app.infrastructure.repositories.dev.handoff_repo import DevHandoffRepository
from app.infrastructure.repositories.dev.logger_repo import DevLoggerRepository
from app.infrastructure.repositories.dev.product_repo import DevProductRepository
from app.infrastructure.repositories.dev.reading_repo import DevReadingRepository
from app.infrastructure.repositories.dev.shipment_repo import DevShipmentRepository

# Singleton database backend
_db_backend: DatabaseBackend | None = None


def get_db_backend() -> DatabaseBackend:
    """Return the initialized database backend instance."""
    global _db_backend
    if _db_backend is None:
        engine = settings.database_engine.lower()
        if engine == "sqlite":
            _db_backend = DevDatabaseBackend(settings.sqlite_url)
        elif engine == "postgres":
            if not settings.postgres_url:
                raise ValueError("POSTGRES_URL environment variable must be set when using postgres")
            _db_backend = DevDatabaseBackend(settings.postgres_url)
        elif engine == "exasol":
            from app.infrastructure.db.exasol_db import ExasolDatabaseBackend
            if not settings.exasol_host:
                raise ValueError(
                    "EXASOL_HOST must be set when DATABASE_ENGINE=exasol. "
                    "Copy .env.example to .env and fill in Exasol credentials."
                )
            _db_backend = ExasolDatabaseBackend(
                host=settings.exasol_host,
                port=settings.exasol_port,
                user=settings.exasol_user,
                password=settings.exasol_password,
                schema=settings.exasol_schema,
                encryption=settings.exasol_encryption,
            )
        else:
            raise ValueError(f"Unsupported DATABASE_ENGINE: {engine}")
    return _db_backend


def is_exasol() -> bool:
    """Return True if Exasol backend is active."""
    return settings.database_engine.lower() == "exasol"


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an active async database session (SQLite/Postgres only)."""
    backend = get_db_backend()
    if isinstance(backend, DevDatabaseBackend):
        async with backend.get_session() as session:
            yield session
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Active database engine does not provide SQLAlchemy sessions.",
        )


# ------------------------------------------------------------------
# Repository factories — return correct implementation based on engine
# ------------------------------------------------------------------

def _exasol_repos():
    """Lazily import Exasol repos (only when engine=exasol)."""
    from app.infrastructure.repositories.exasol import (
        ExasolAttributionRepository,
        ExasolExcursionRepository,
        ExasolHandoffRepository,
        ExasolLoggerRepository,
        ExasolProductRepository,
        ExasolReadingRepository,
        ExasolShipmentRepository,
    )
    return (
        ExasolProductRepository,
        ExasolShipmentRepository,
        ExasolHandoffRepository,
        ExasolLoggerRepository,
        ExasolReadingRepository,
        ExasolExcursionRepository,
        ExasolAttributionRepository,
    )


def get_product_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractProductRepository:
    if is_exasol():
        return _exasol_repos()[0]()
    return DevProductRepository(session)


def get_shipment_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractShipmentRepository:
    if is_exasol():
        return _exasol_repos()[1]()
    return DevShipmentRepository(session)


def get_handoff_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractHandoffRepository:
    if is_exasol():
        return _exasol_repos()[2]()
    return DevHandoffRepository(session)


def get_logger_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractLoggerRepository:
    if is_exasol():
        return _exasol_repos()[3]()
    return DevLoggerRepository(session)


def get_reading_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractReadingRepository:
    if is_exasol():
        return _exasol_repos()[4]()
    return DevReadingRepository(session)


def get_excursion_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractExcursionRepository:
    if is_exasol():
        return _exasol_repos()[5]()
    return DevExcursionRepository(session)


def get_attribution_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractAttributionRepository:
    if is_exasol():
        return _exasol_repos()[6]()
    return DevAttributionRepository(session)


# Services
def get_exposure_service() -> ExposureService:
    return ExposureService()


def get_attribution_service(
    exposure_service: ExposureService = Depends(get_exposure_service),
) -> AttributionService:
    return AttributionService(exposure_service)


def get_timeline_service(
    exposure_service: ExposureService = Depends(get_exposure_service),
) -> TimelineService:
    return TimelineService(exposure_service)


def get_prevention_service() -> PreventionService:
    return PreventionService()
