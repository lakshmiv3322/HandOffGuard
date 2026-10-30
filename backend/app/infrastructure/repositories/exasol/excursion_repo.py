"""Exasol implementation of AbstractExcursionRepository."""

from __future__ import annotations

from typing import Optional

from app.core.domain.models import ExcursionEvent
from app.infrastructure.repositories.base import AbstractExcursionRepository
from app.infrastructure.repositories.exasol.connection import get_pool, _ts


class ExasolExcursionRepository(AbstractExcursionRepository):

    async def get_by_shipment(self, shipment_id: int) -> list[ExcursionEvent]:
        rows = await get_pool().execute(
            "SELECT excursion_id, shipment_id, "
            "       started_at_utc, ended_at_utc, "
            "       peak_temp_c, duration_minutes, severity, "
            "       ground_truth_handoff_id, ground_truth_cause "
            "FROM HANDOFFGUARD.excursions "
            "WHERE shipment_id = {shipment_id!d} "
            "ORDER BY started_at_utc",
            {"shipment_id": shipment_id},
        )
        return [self._row_to_excursion(r) for r in rows]

    async def get_by_id(self, excursion_id: int) -> Optional[ExcursionEvent]:
        rows = await get_pool().execute(
            "SELECT excursion_id, shipment_id, "
            "       started_at_utc, ended_at_utc, "
            "       peak_temp_c, duration_minutes, severity, "
            "       ground_truth_handoff_id, ground_truth_cause "
            "FROM HANDOFFGUARD.excursions "
            "WHERE excursion_id = {excursion_id!d}",
            {"excursion_id": excursion_id},
        )
        return self._row_to_excursion(rows[0]) if rows else None

    @staticmethod
    def _row_to_excursion(r: dict) -> ExcursionEvent:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return ExcursionEvent(
            excursion_id=int(_k("excursion_id")),
            shipment_id=int(_k("shipment_id")),
            started_at_utc=_ts(_k("started_at_utc")),
            ended_at_utc=_ts(_k("ended_at_utc")),
            duration_minutes=float(_k("duration_minutes") or 0),
            peak_temp_c=float(_k("peak_temp_c") or 0),
            severity=str(_k("severity") or "unknown"),
            ground_truth_handoff_id=(
                int(_k("ground_truth_handoff_id"))
                if _k("ground_truth_handoff_id") is not None
                else None
            ),
            ground_truth_cause=_k("ground_truth_cause"),
        )
