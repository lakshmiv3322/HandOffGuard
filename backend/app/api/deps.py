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
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Exasol engine selected but requires pyexasol driver and repository implementation. See docs at /docs/exasol.",
            )
        else:
            raise ValueError(f"Unsupported DATABASE_ENGINE: {engine}")
    return _db_backend


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an active async database session for the current request."""
    backend = get_db_backend()
    if isinstance(backend, DevDatabaseBackend):
        async with backend.get_session() as session:
            yield session
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Active database engine does not provide SQLAlchemy sessions.",
        )


# Repositories
def get_product_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractProductRepository:
    return DevProductRepository(session)


def get_shipment_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractShipmentRepository:
    return DevShipmentRepository(session)


def get_handoff_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractHandoffRepository:
    return DevHandoffRepository(session)


def get_logger_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractLoggerRepository:
    return DevLoggerRepository(session)


def get_reading_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractReadingRepository:
    return DevReadingRepository(session)


def get_excursion_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractExcursionRepository:
    return DevExcursionRepository(session)


def get_attribution_repo(session: AsyncSession = Depends(get_db_session)) -> AbstractAttributionRepository:
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
