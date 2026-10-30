"""Exasol implementation of AbstractHandoffRepository."""

from __future__ import annotations

from typing import Optional

from app.core.domain.models import Handoff
from app.infrastructure.repositories.base import AbstractHandoffRepository
from app.infrastructure.repositories.exasol.connection import get_pool, _ts


class ExasolHandoffRepository(AbstractHandoffRepository):

    async def get_by_shipment(self, shipment_id: str | int) -> list[Handoff]:
        rows = await get_pool().execute(
            "SELECT ID AS HANDOFF_ID, SHIPMENT_ID, SEQUENCE_NUMBER AS SEQUENCE_NO, "
            "       HANDOFF_TYPE, FROM_PARTY, TO_PARTY, LOCATION, "
            "       COALESCE(ACTUAL_START_AT, PLANNED_START_AT) AS WINDOW_START_UTC, "
            "       COALESCE(ACTUAL_END_AT, PLANNED_END_AT) AS WINDOW_END_UTC, "
            "       PLANNED_START_AT AS REPORTED_START_UTC, PLANNED_END_AT AS REPORTED_END_UTC, "
            "       0 AS CLOCK_SKEW_SECONDS, DWELL_MINUTES "
            "FROM HANDOFFGUARD.HANDOFFS "
            "WHERE SHIPMENT_ID = {shipment_id} "
            "ORDER BY SEQUENCE_NUMBER",
            {"shipment_id": str(shipment_id)},
        )
        return [self._row_to_handoff(r) for r in rows]

    async def get_by_id(self, handoff_id: str | int) -> Optional[Handoff]:
        rows = await get_pool().execute(
            "SELECT ID AS HANDOFF_ID, SHIPMENT_ID, SEQUENCE_NUMBER AS SEQUENCE_NO, "
            "       HANDOFF_TYPE, FROM_PARTY, TO_PARTY, LOCATION, "
            "       COALESCE(ACTUAL_START_AT, PLANNED_START_AT) AS WINDOW_START_UTC, "
            "       COALESCE(ACTUAL_END_AT, PLANNED_END_AT) AS WINDOW_END_UTC, "
            "       PLANNED_START_AT AS REPORTED_START_UTC, PLANNED_END_AT AS REPORTED_END_UTC, "
            "       0 AS CLOCK_SKEW_SECONDS, DWELL_MINUTES "
            "FROM HANDOFFGUARD.HANDOFFS "
            "WHERE ID = {handoff_id}",
            {"handoff_id": str(handoff_id)},
        )
        return self._row_to_handoff(rows[0]) if rows else None

    @staticmethod
    def _row_to_handoff(r: dict) -> Handoff:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return Handoff(
            handoff_id=str(_k("HANDOFF_ID") or _k("ID") or ""),
            shipment_id=str(_k("SHIPMENT_ID") or ""),
            sequence_no=int(_k("SEQUENCE_NO") or _k("SEQUENCE_NUMBER") or 1),
            handoff_type=str(_k("HANDOFF_TYPE") or ""),
            from_party=str(_k("FROM_PARTY") or ""),
            to_party=str(_k("TO_PARTY") or ""),
            location=str(_k("LOCATION") or ""),
            window_start_utc=_ts(_k("WINDOW_START_UTC")),
            window_end_utc=_ts(_k("WINDOW_END_UTC")),
            reported_start_utc=_ts(_k("REPORTED_START_UTC")),
            reported_end_utc=_ts(_k("REPORTED_END_UTC")),
            clock_skew_seconds=float(_k("CLOCK_SKEW_SECONDS") or 0),
            dwell_minutes=float(_k("DWELL_MINUTES") or 0),
        )
