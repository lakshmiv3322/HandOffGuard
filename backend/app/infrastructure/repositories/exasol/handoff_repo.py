"""Exasol implementation of AbstractHandoffRepository."""

from __future__ import annotations

from typing import Optional

from app.core.domain.models import Handoff
from app.infrastructure.repositories.base import AbstractHandoffRepository
from app.infrastructure.repositories.exasol.connection import get_pool, _ts


class ExasolHandoffRepository(AbstractHandoffRepository):

    async def get_by_shipment(self, shipment_id: int) -> list[Handoff]:
        rows = await get_pool().execute(
            "SELECT handoff_id, shipment_id, sequence_no, handoff_type, "
            "       from_party, to_party, location, "
            "       window_start_utc, window_end_utc, "
            "       reported_start_utc, reported_end_utc, "
            "       clock_skew_seconds, dwell_minutes "
            "FROM HANDOFFGUARD.handoffs "
            "WHERE shipment_id = {shipment_id!d} "
            "ORDER BY sequence_no",
            {"shipment_id": shipment_id},
        )
        return [self._row_to_handoff(r) for r in rows]

    async def get_by_id(self, handoff_id: int) -> Optional[Handoff]:
        rows = await get_pool().execute(
            "SELECT handoff_id, shipment_id, sequence_no, handoff_type, "
            "       from_party, to_party, location, "
            "       window_start_utc, window_end_utc, "
            "       reported_start_utc, reported_end_utc, "
            "       clock_skew_seconds, dwell_minutes "
            "FROM HANDOFFGUARD.handoffs "
            "WHERE handoff_id = {handoff_id!d}",
            {"handoff_id": handoff_id},
        )
        return self._row_to_handoff(rows[0]) if rows else None

    @staticmethod
    def _row_to_handoff(r: dict) -> Handoff:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return Handoff(
            handoff_id=int(_k("handoff_id")),
            shipment_id=int(_k("shipment_id")),
            sequence_no=int(_k("sequence_no")),
            handoff_type=str(_k("handoff_type")),
            from_party=str(_k("from_party")),
            to_party=str(_k("to_party")),
            location=str(_k("location")),
            window_start_utc=_ts(_k("window_start_utc")),
            window_end_utc=_ts(_k("window_end_utc")),
            reported_start_utc=_ts(_k("reported_start_utc")),
            reported_end_utc=_ts(_k("reported_end_utc")),
            clock_skew_seconds=float(_k("clock_skew_seconds") or 0),
            dwell_minutes=float(_k("dwell_minutes") or 0),
        )
