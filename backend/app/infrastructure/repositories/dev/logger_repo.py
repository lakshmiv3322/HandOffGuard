"""Dev SQLAlchemy repository for temperature loggers."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.models import Logger
from app.infrastructure.db.dev_db import LoggerORM
from app.infrastructure.repositories.base import AbstractLoggerRepository


def _orm_to_domain(row: LoggerORM) -> Logger:
    return Logger(
        logger_id=row.logger_id,
        device_type=row.device_type,
        assigned_shipment_id=row.assigned_shipment_id,
        sampling_interval_seconds=row.sampling_interval_seconds,
        clock_skew_seconds=row.clock_skew_seconds,
        data_quality_flag=row.data_quality_flag,
    )


class DevLoggerRepository(AbstractLoggerRepository):
    """SQLAlchemy-backed logger repository for dev/test environments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_shipment(self, shipment_id: int) -> list[Logger]:
        result = await self._session.execute(
            select(LoggerORM).where(LoggerORM.assigned_shipment_id == shipment_id)
        )
        return [_orm_to_domain(row) for row in result.scalars().all()]

    async def get_by_id(self, logger_id: int) -> Optional[Logger]:
        result = await self._session.execute(
            select(LoggerORM).where(LoggerORM.logger_id == logger_id)
        )
        row = result.scalar_one_or_none()
        return _orm_to_domain(row) if row else None
