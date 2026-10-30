"""Exasol implementation of AbstractAttributionRepository."""

from __future__ import annotations

import json
from typing import Optional

from app.core.domain.models import AttributionResult, PreventionSuggestion
from app.infrastructure.repositories.base import AbstractAttributionRepository
from app.infrastructure.repositories.exasol.connection import get_pool


class ExasolAttributionRepository(AbstractAttributionRepository):

    async def get_by_excursion(self, excursion_id: str | int) -> list[AttributionResult]:
        rows = await get_pool().execute(
            "SELECT EXCURSION_ID, HANDOFF_ID, EXPOSURE_DEGREE_MINUTES, "
            "       EXPOSURE_SHARE_PCT, CONFIDENCE_SCORE, CONFIDENCE_LABEL, EVIDENCE_JSON "
            "FROM HANDOFFGUARD.ATTRIBUTION_RESULTS "
            "WHERE EXCURSION_ID = {excursion_id} "
            "ORDER BY EXPOSURE_SHARE_PCT DESC",
            {"excursion_id": str(excursion_id)},
        )
        return [self._row_to_result(r) for r in rows]

    async def upsert_results(self, results: list[AttributionResult]) -> None:
        if not results:
            return
        excursion_ids = list({r.excursion_id for r in results})
        for eid in excursion_ids:
            await get_pool().execute(
                "DELETE FROM HANDOFFGUARD.ATTRIBUTION_RESULTS "
                "WHERE EXCURSION_ID = {excursion_id}",
                {"excursion_id": str(eid)},
            )
        for r in results:
            await get_pool().execute(
                "INSERT INTO HANDOFFGUARD.ATTRIBUTION_RESULTS "
                "(EXCURSION_ID, HANDOFF_ID, EXPOSURE_DEGREE_MINUTES, "
                " EXPOSURE_SHARE_PCT, CONFIDENCE_SCORE, CONFIDENCE_LABEL, EVIDENCE_JSON) "
                "VALUES ({excursion_id}, {handoff_id}, {edm}, {esp}, {cs}, {cl}, {ej})",
                {
                    "excursion_id": str(r.excursion_id),
                    "handoff_id": str(r.handoff_id),
                    "edm": r.exposure_degree_minutes,
                    "esp": r.exposure_share_pct,
                    "cs": r.confidence_score,
                    "cl": r.confidence_label,
                    "ej": r.evidence_json,
                },
            )

    async def get_prevention_by_shipment(
        self, shipment_id: str | int
    ) -> list[PreventionSuggestion]:
        rows = await get_pool().execute(
            "SELECT SHIPMENT_ID, HANDOFF_ID, RISK_SCORE, SUGGESTION, "
            "       RATIONALE, PROTOTYPE_FLAG "
            "FROM HANDOFFGUARD.PREVENTION_SUGGESTIONS "
            "WHERE SHIPMENT_ID = {shipment_id} "
            "ORDER BY RISK_SCORE DESC",
            {"shipment_id": str(shipment_id)},
        )
        return [self._row_to_prevention(r) for r in rows]

    async def upsert_prevention(self, suggestions: list[PreventionSuggestion]) -> None:
        if not suggestions:
            return
        shipment_ids = list({s.shipment_id for s in suggestions})
        for sid in shipment_ids:
            await get_pool().execute(
                "DELETE FROM HANDOFFGUARD.PREVENTION_SUGGESTIONS "
                "WHERE SHIPMENT_ID = {shipment_id}",
                {"shipment_id": str(sid)},
            )
        for s in suggestions:
            await get_pool().execute(
                "INSERT INTO HANDOFFGUARD.PREVENTION_SUGGESTIONS "
                "(SHIPMENT_ID, HANDOFF_ID, RISK_SCORE, SUGGESTION, RATIONALE, PROTOTYPE_FLAG) "
                "VALUES ({shipment_id}, {handoff_id}, {risk_score}, {suggestion}, {rationale}, {prototype_flag})",
                {
                    "shipment_id": str(s.shipment_id),
                    "handoff_id": str(s.handoff_id),
                    "risk_score": s.risk_score,
                    "suggestion": s.suggestion,
                    "rationale": s.rationale,
                    "prototype_flag": s.prototype_flag,
                },
            )

    @staticmethod
    def _row_to_result(r: dict) -> AttributionResult:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return AttributionResult(
            excursion_id=str(_k("EXCURSION_ID") or ""),
            handoff_id=str(_k("HANDOFF_ID") or ""),
            exposure_degree_minutes=float(_k("EXPOSURE_DEGREE_MINUTES") or 0.0),
            exposure_share_pct=float(_k("EXPOSURE_SHARE_PCT") or 0.0),
            confidence_score=float(_k("CONFIDENCE_SCORE") or 0.0),
            confidence_label=str(_k("CONFIDENCE_LABEL") or "Low"),
            evidence_json=str(_k("EVIDENCE_JSON") or "{}"),
        )

    @staticmethod
    def _row_to_prevention(r: dict) -> PreventionSuggestion:
        def _k(n):
            return r.get(n.upper()) or r.get(n)

        return PreventionSuggestion(
            shipment_id=str(_k("SHIPMENT_ID") or ""),
            handoff_id=str(_k("HANDOFF_ID") or ""),
            risk_score=float(_k("RISK_SCORE") or 0.0),
            suggestion=str(_k("SUGGESTION") or ""),
            rationale=str(_k("RATIONALE") or ""),
            prototype_flag=bool(_k("PROTOTYPE_FLAG") or False),
        )
