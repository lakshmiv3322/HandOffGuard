"""Exasol implementation of AbstractLoggerRepository."""

from __future__ import annotations

from typing import Optional

from app.core.domain.models import Logger
from app.infrastructure.repositories.base import AbstractLoggerRepository
from app.infrastructure.repositories.exasol.connection import get_pool


class ExasolLoggerRepository(AbstractLoggerRepository):

    async def get_by_shipment(self, shipment_id: str | int) -> list[Logger]:
        rows = await get_pool().execute(
            "SELECT LOGGER_ID, DEVICE_CODE, MODEL, ASSIGNED_SHIPMENT_ID, "
            "       CLOCK_SKEW_SECONDS, 'good' AS DATA_QUALITY_FLAG "
            "FROM HANDOFFGUARD.LOGGER_DEVICES "
            "WHERE ASSIGNED_SHIPMENT_ID = {shipment_id}",
            {"shipment_id": str(shipment_id)},
        )
        return [self._row_to_logger(r) for r in rows]

    async def get_by_id(self, logger_id: str | int) -> Optional[Logger]:
        rows = await get_pool().execute(
            "SELECT LOGGER_ID, DEVICE_CODE, MODEL, ASSIGNED_SHIPMENT_ID, "
            "       CLOCK_SKEW_SECONDS, 'good' AS DATA_QUALITY_FLAG "
            "FROM HANDOFFGUARD.LOGGER_DEVICES "
            "WHERE LOGGER_ID = {logger_id}",
            {"logger_id": str(logger_id)},
        )
        return self._row_to_logger(rows[0]) if rows else None

    @staticmethod
    def _row_to_logger(r: dict) -> Logger:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return Logger(
            logger_id=str(_k("LOGGER_ID") or ""),
            device_type=str(_k("DEVICE_CODE") or _k("MODEL") or "unknown"),
            assigned_shipment_id=str(_k("ASSIGNED_SHIPMENT_ID") or ""),
            sampling_interval_seconds=300,
            clock_skew_seconds=float(_k("CLOCK_SKEW_SECONDS") or 0),
            data_quality_flag=str(_k("DATA_QUALITY_FLAG") or "good"),
        )
