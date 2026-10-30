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
        logger_id: str | int,
        start_utc: Optional[datetime] = None,
        end_utc: Optional[datetime] = None,
    ) -> list[TemperatureReading]:
        params: dict = {"logger_id": str(logger_id)}
        where_extra = ""
        if start_utc:
            where_extra += " AND READING_AT_UTC >= {start_utc}"
            params["start_utc"] = start_utc.strftime("%Y-%m-%d %H:%M:%S")
        if end_utc:
            where_extra += " AND READING_AT_UTC <= {end_utc}"
            params["end_utc"] = end_utc.strftime("%Y-%m-%d %H:%M:%S")

        rows = await get_pool().execute(
            "SELECT READING_ID, LOGGER_ID, READING_AT_UTC, TEMPERATURE_C, BATTERY_PCT "
            "FROM HANDOFFGUARD.LOGGER_READINGS "
            f"WHERE LOGGER_ID = {{logger_id}}{where_extra} "
            "ORDER BY READING_AT_UTC",
            params,
        )
        return [self._row_to_reading(r) for r in rows]

    async def get_by_shipment(self, shipment_id: str | int) -> list[TemperatureReading]:
        rows = await get_pool().execute(
            "SELECT r.READING_ID, r.LOGGER_ID, r.READING_AT_UTC, "
            "       r.TEMPERATURE_C, r.BATTERY_PCT "
            "FROM HANDOFFGUARD.LOGGER_READINGS r "
            "JOIN HANDOFFGUARD.LOGGER_DEVICES ld ON r.LOGGER_ID = ld.LOGGER_ID "
            "WHERE ld.ASSIGNED_SHIPMENT_ID = {shipment_id} "
            "ORDER BY r.READING_AT_UTC",
            {"shipment_id": str(shipment_id)},
        )
        return [self._row_to_reading(r) for r in rows]

    @staticmethod
    def _row_to_reading(r: dict) -> TemperatureReading:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return TemperatureReading(
            reading_id=str(_k("READING_ID") or ""),
            logger_id=str(_k("LOGGER_ID") or ""),
            recorded_at_utc=_ts(_k("READING_AT_UTC")),
            temperature_c=float(_k("TEMPERATURE_C") or 0.0),
            humidity_pct=None,
            battery_pct=(
                float(_k("BATTERY_PCT"))
                if _k("BATTERY_PCT") is not None
                else None
            ),
            quality_flag="good",
        )
