"""Exasol implementation of AbstractAttributionRepository."""

from __future__ import annotations

import json
from typing import Optional

from app.core.domain.models import AttributionResult, PreventionSuggestion
from app.infrastructure.repositories.base import AbstractAttributionRepository
from app.infrastructure.repositories.exasol.connection import get_pool


class ExasolAttributionRepository(AbstractAttributionRepository):

    async def get_by_excursion(self, excursion_id: int) -> list[AttributionResult]:
        rows = await get_pool().execute(
            "SELECT excursion_id, handoff_id, exposure_degree_minutes, "
            "       exposure_share_pct, confidence_score, confidence_label, evidence_json "
            "FROM HANDOFFGUARD.attribution_results "
            "WHERE excursion_id = {excursion_id!d} "
            "ORDER BY exposure_share_pct DESC",
            {"excursion_id": excursion_id},
        )
        return [self._row_to_result(r) for r in rows]

    async def upsert_results(self, results: list[AttributionResult]) -> None:
        # Exasol does not have a native UPSERT; delete then re-insert
        if not results:
            return
        excursion_ids = list({r.excursion_id for r in results})
        for eid in excursion_ids:
            await get_pool().execute(
                "DELETE FROM HANDOFFGUARD.attribution_results "
                "WHERE excursion_id = {excursion_id!d}",
                {"excursion_id": eid},
            )
        for r in results:
            await get_pool().execute(
                "INSERT INTO HANDOFFGUARD.attribution_results "
                "(excursion_id, handoff_id, exposure_degree_minutes, "
                " exposure_share_pct, confidence_score, confidence_label, evidence_json) "
                "VALUES ({excursion_id!d}, {handoff_id!d}, {edm}, {esp}, {cs}, {cl}, {ej})",
                {
                    "excursion_id": r.excursion_id,
                    "handoff_id": r.handoff_id,
                    "edm": r.exposure_degree_minutes,
                    "esp": r.exposure_share_pct,
                    "cs": r.confidence_score,
                    "cl": r.confidence_label,
                    "ej": r.evidence_json,
                },
            )

    async def get_prevention_by_shipment(
        self, shipment_id: int
    ) -> list[PreventionSuggestion]:
        rows = await get_pool().execute(
            "SELECT shipment_id, handoff_id, risk_score, suggestion, "
            "       rationale, prototype_flag "
            "FROM HANDOFFGUARD.prevention_suggestions "
            "WHERE shipment_id = {shipment_id!d} "
            "ORDER BY risk_score DESC",
            {"shipment_id": shipment_id},
        )
        return [self._row_to_prevention(r) for r in rows]

    async def upsert_prevention(self, suggestions: list[PreventionSuggestion]) -> None:
        if not suggestions:
            return
        shipment_ids = list({s.shipment_id for s in suggestions})
        for sid in shipment_ids:
            await get_pool().execute(
                "DELETE FROM HANDOFFGUARD.prevention_suggestions "
                "WHERE shipment_id = {shipment_id!d}",
                {"shipment_id": sid},
            )
        for s in suggestions:
            await get_pool().execute(
                "INSERT INTO HANDOFFGUARD.prevention_suggestions "
                "(shipment_id, handoff_id, risk_score, suggestion, rationale, prototype_flag) "
                "VALUES ({shipment_id!d}, {handoff_id!d}, {rs}, {sg}, {ra}, {pf})",
                {
                    "shipment_id": s.shipment_id,
                    "handoff_id": s.handoff_id,
                    "rs": s.risk_score,
                    "sg": s.suggestion,
                    "ra": s.rationale,
                    "pf": s.prototype_flag,
                },
            )

    @staticmethod
    def _row_to_result(r: dict) -> AttributionResult:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return AttributionResult(
            excursion_id=int(_k("excursion_id")),
            handoff_id=int(_k("handoff_id")),
            exposure_degree_minutes=float(_k("exposure_degree_minutes") or 0),
            exposure_share_pct=float(_k("exposure_share_pct") or 0),
            confidence_score=float(_k("confidence_score") or 0),
            confidence_label=str(_k("confidence_label") or "low"),
            evidence_json=str(_k("evidence_json") or "{}"),
        )

    @staticmethod
    def _row_to_prevention(r: dict) -> PreventionSuggestion:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return PreventionSuggestion(
            shipment_id=int(_k("shipment_id")),
            handoff_id=int(_k("handoff_id")),
            risk_score=float(_k("risk_score") or 0),
            suggestion=str(_k("suggestion") or ""),
            rationale=str(_k("rationale") or ""),
            prototype_flag=bool(_k("prototype_flag")),
        )
