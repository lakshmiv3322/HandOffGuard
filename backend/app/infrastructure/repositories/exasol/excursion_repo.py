"""Exasol implementation of AbstractExcursionRepository."""

from __future__ import annotations

from typing import Optional

from app.core.domain.models import ExcursionEvent
from app.infrastructure.repositories.base import AbstractExcursionRepository
from app.infrastructure.repositories.exasol.connection import get_pool, _ts


class ExasolExcursionRepository(AbstractExcursionRepository):

    async def get_by_shipment(self, shipment_id: str | int) -> list[ExcursionEvent]:
        rows = await get_pool().execute(
            "SELECT EXCURSION_ID, SHIPMENT_ID, STARTED_AT_UTC, ENDED_AT_UTC, "
            "       PEAK_TEMP_C, DURATION_MINUTES, SEVERITY, "
            "       GROUND_TRUTH_HANDOFF_ID, GROUND_TRUTH_CAUSE "
            "FROM ("
            "  SELECT EXCURSION_ID, SHIPMENT_ID, STARTED_AT_UTC, ENDED_AT_UTC, "
            "         MAX_TEMP_C AS PEAK_TEMP_C, "
            "         ROUND(SECONDS_BETWEEN(ENDED_AT_UTC, STARTED_AT_UTC) / 60.0, 1) AS DURATION_MINUTES, "
            "         'CRITICAL' AS SEVERITY, NULL AS GROUND_TRUTH_HANDOFF_ID, NULL AS GROUND_TRUTH_CAUSE "
            "  FROM HANDOFFGUARD.EXCURSIONS "
            "  UNION ALL "
            "  SELECT ID AS EXCURSION_ID, SHIPMENT_ID, STARTED_AT AS STARTED_AT_UTC, ENDED_AT AS ENDED_AT_UTC, "
            "         PEAK_TEMPERATURE_C AS PEAK_TEMP_C, DURATION_MINUTES, SEVERITY, "
            "         HANDOFF_ID AS GROUND_TRUTH_HANDOFF_ID, LIKELY_CAUSE AS GROUND_TRUTH_CAUSE "
            "  FROM HANDOFFGUARD.EXCURSION_EVENTS "
            ") t "
            "WHERE SHIPMENT_ID = {shipment_id} "
            "ORDER BY STARTED_AT_UTC",
            {"shipment_id": str(shipment_id)},
        )
        return [self._row_to_excursion(r) for r in rows]

    async def get_by_id(self, excursion_id: str | int) -> Optional[ExcursionEvent]:
        rows = await get_pool().execute(
            "SELECT EXCURSION_ID, SHIPMENT_ID, STARTED_AT_UTC, ENDED_AT_UTC, "
            "       PEAK_TEMP_C, DURATION_MINUTES, SEVERITY, "
            "       GROUND_TRUTH_HANDOFF_ID, GROUND_TRUTH_CAUSE "
            "FROM ("
            "  SELECT EXCURSION_ID, SHIPMENT_ID, STARTED_AT_UTC, ENDED_AT_UTC, "
            "         MAX_TEMP_C AS PEAK_TEMP_C, "
            "         ROUND(SECONDS_BETWEEN(ENDED_AT_UTC, STARTED_AT_UTC) / 60.0, 1) AS DURATION_MINUTES, "
            "         'CRITICAL' AS SEVERITY, NULL AS GROUND_TRUTH_HANDOFF_ID, NULL AS GROUND_TRUTH_CAUSE "
            "  FROM HANDOFFGUARD.EXCURSIONS "
            "  UNION ALL "
            "  SELECT ID AS EXCURSION_ID, SHIPMENT_ID, STARTED_AT AS STARTED_AT_UTC, ENDED_AT AS ENDED_AT_UTC, "
            "         PEAK_TEMPERATURE_C AS PEAK_TEMP_C, DURATION_MINUTES, SEVERITY, "
            "         HANDOFF_ID AS GROUND_TRUTH_HANDOFF_ID, LIKELY_CAUSE AS GROUND_TRUTH_CAUSE "
            "  FROM HANDOFFGUARD.EXCURSION_EVENTS "
            ") t "
            "WHERE EXCURSION_ID = {excursion_id}",
            {"excursion_id": str(excursion_id)},
        )
        return self._row_to_excursion(rows[0]) if rows else None

    @staticmethod
    def _row_to_excursion(r: dict) -> ExcursionEvent:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return ExcursionEvent(
            excursion_id=str(_k("EXCURSION_ID") or _k("ID") or ""),
            shipment_id=str(_k("SHIPMENT_ID") or ""),
            started_at_utc=_ts(_k("STARTED_AT_UTC")),
            ended_at_utc=_ts(_k("ENDED_AT_UTC")),
            duration_minutes=float(_k("DURATION_MINUTES") or 0),
            peak_temp_c=float(_k("PEAK_TEMP_C") or 0),
            severity=str(_k("SEVERITY") or "unknown"),
            ground_truth_handoff_id=(
                str(_k("GROUND_TRUTH_HANDOFF_ID"))
                if _k("GROUND_TRUTH_HANDOFF_ID") is not None
                else None
            ),
            ground_truth_cause=_k("GROUND_TRUTH_CAUSE"),
        )
