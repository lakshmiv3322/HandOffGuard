"""Dev SQLAlchemy repository for temperature readings."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import join, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.models import TemperatureReading
from app.infrastructure.db.dev_db import LoggerORM, TemperatureReadingORM
from app.infrastructure.repositories.base import AbstractReadingRepository


def _orm_to_domain(row: TemperatureReadingORM) -> TemperatureReading:
    return TemperatureReading(
        reading_id=row.reading_id,
        logger_id=row.logger_id,
        recorded_at_utc=row.recorded_at_utc,
        temperature_c=row.temperature_c,
        humidity_pct=row.humidity_pct,
        battery_pct=row.battery_pct,
        quality_flag=row.quality_flag,
    )


class DevReadingRepository(AbstractReadingRepository):
    """SQLAlchemy-backed temperature reading repository for dev/test environments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_logger(
        self,
        logger_id: int,
        start_utc: Optional[datetime] = None,
        end_utc: Optional[datetime] = None,
    ) -> list[TemperatureReading]:
        query = (
            select(TemperatureReadingORM)
            .where(TemperatureReadingORM.logger_id == logger_id)
            .order_by(TemperatureReadingORM.recorded_at_utc)
        )
        if start_utc:
            query = query.where(TemperatureReadingORM.recorded_at_utc >= start_utc)
        if end_utc:
            query = query.where(TemperatureReadingORM.recorded_at_utc <= end_utc)

        result = await self._session.execute(query)
        return [_orm_to_domain(row) for row in result.scalars().all()]

    async def get_by_shipment(self, shipment_id: int) -> list[TemperatureReading]:
        """Return all readings for all loggers assigned to a shipment."""
        j = join(
            TemperatureReadingORM,
            LoggerORM,
            TemperatureReadingORM.logger_id == LoggerORM.logger_id,
        )
        query = (
            select(TemperatureReadingORM)
            .select_from(j)
            .where(LoggerORM.assigned_shipment_id == shipment_id)
            .order_by(TemperatureReadingORM.recorded_at_utc)
        )
        result = await self._session.execute(query)
        return [_orm_to_domain(row) for row in result.scalars().all()]
