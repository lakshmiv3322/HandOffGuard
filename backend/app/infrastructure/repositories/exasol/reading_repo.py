"""Exasol implementation of AbstractReadingRepository.

IMPORTANT: logger_readings has NO handoff_id column.
All queries here work purely on logger_id and reading_at_utc.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.core.domain.models import TemperatureReading
from app.infrastructure.repositories.base import AbstractReadingRepository
from app.infrastructure.repositories.exasol.connection import get_pool, _ts


class ExasolReadingRepository(AbstractReadingRepository):

    async def get_by_logger(
        self,
        logger_id: int,
        start_utc: Optional[datetime] = None,
        end_utc: Optional[datetime] = None,
    ) -> list[TemperatureReading]:
        params: dict = {"logger_id": logger_id}
        where_extra = ""
        if start_utc:
            where_extra += " AND reading_at_utc >= {start_utc}"
            params["start_utc"] = start_utc.strftime("%Y-%m-%d %H:%M:%S")
        if end_utc:
            where_extra += " AND reading_at_utc <= {end_utc}"
            params["end_utc"] = end_utc.strftime("%Y-%m-%d %H:%M:%S")

        rows = await get_pool().execute(
            "SELECT reading_id, logger_id, reading_at_utc, temperature_c, battery_pct "
            "FROM HANDOFFGUARD.logger_readings "
            f"WHERE logger_id = {{logger_id!d}}{where_extra} "
            "ORDER BY reading_at_utc",
            params,
        )
        return [self._row_to_reading(r) for r in rows]

    async def get_by_shipment(self, shipment_id: int) -> list[TemperatureReading]:
        rows = await get_pool().execute(
            "SELECT r.reading_id, r.logger_id, r.reading_at_utc, "
            "       r.temperature_c, r.battery_pct "
            "FROM HANDOFFGUARD.logger_readings r "
            "JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id "
            "WHERE ld.assigned_shipment_id = {shipment_id!d} "
            "ORDER BY r.reading_at_utc",
            {"shipment_id": shipment_id},
        )
        return [self._row_to_reading(r) for r in rows]

    @staticmethod
    def _row_to_reading(r: dict) -> TemperatureReading:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return TemperatureReading(
            reading_id=int(_k("reading_id")),
            logger_id=int(_k("logger_id")),
            # Exasol column is reading_at_utc; domain field is recorded_at_utc
            recorded_at_utc=_ts(_k("reading_at_utc")),
            temperature_c=float(_k("temperature_c")),
            humidity_pct=None,  # not stored in Exasol schema
            battery_pct=float(_k("battery_pct")) if _k("battery_pct") is not None else None,
            quality_flag="good",
        )
