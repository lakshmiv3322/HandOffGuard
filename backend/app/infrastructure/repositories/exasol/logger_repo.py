"""Exasol implementation of AbstractLoggerRepository."""

from __future__ import annotations

from typing import Optional

from app.core.domain.models import Logger
from app.infrastructure.repositories.base import AbstractLoggerRepository
from app.infrastructure.repositories.exasol.connection import get_pool


class ExasolLoggerRepository(AbstractLoggerRepository):

    async def get_by_shipment(self, shipment_id: int) -> list[Logger]:
        rows = await get_pool().execute(
            "SELECT logger_id, device_code, model, assigned_shipment_id, "
            "       clock_skew_seconds, data_quality_flag "
            "FROM HANDOFFGUARD.logger_devices "
            "WHERE assigned_shipment_id = {shipment_id!d}",
            {"shipment_id": shipment_id},
        )
        return [self._row_to_logger(r) for r in rows]

    async def get_by_id(self, logger_id: int) -> Optional[Logger]:
        rows = await get_pool().execute(
            "SELECT logger_id, device_code, model, assigned_shipment_id, "
            "       clock_skew_seconds, data_quality_flag "
            "FROM HANDOFFGUARD.logger_devices "
            "WHERE logger_id = {logger_id!d}",
            {"logger_id": logger_id},
        )
        return self._row_to_logger(rows[0]) if rows else None

    @staticmethod
    def _row_to_logger(r: dict) -> Logger:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return Logger(
            logger_id=int(_k("logger_id")),
            # Map Exasol's device_code → domain device_type (closest equivalent)
            device_type=str(_k("device_code") or _k("model") or "unknown"),
            assigned_shipment_id=int(_k("assigned_shipment_id")),
            # Exasol schema does not store sampling_interval; default to 300 s (5 min)
            sampling_interval_seconds=300,
            clock_skew_seconds=float(_k("clock_skew_seconds") or 0),
            data_quality_flag=str(_k("data_quality_flag") or "good"),
        )
