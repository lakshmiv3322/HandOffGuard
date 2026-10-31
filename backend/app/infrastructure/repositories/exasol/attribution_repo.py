"""Exasol implementation of AbstractAttributionRepository."""

from __future__ import annotations

import json
from typing import Optional

from app.core.domain.models import AttributionResult, PreventionSuggestion
from app.infrastructure.repositories.base import AbstractAttributionRepository
from app.infrastructure.repositories.exasol.connection import get_pool


class ExasolAttributionRepository(AbstractAttributionRepository):

    async def get_by_excursion(self, excursion_id: str | int) -> list[AttributionResult]:
        pool = get_pool()
        # 1. Query analytical view v_excursion_attribution (Primary analytical truth)
        try:
            view_rows = await pool.execute(
                "SELECT excursion_id, handoff_id, handoff_total_dm, "
                "       exposure_share, attribution_rank, evidence_status, disclaimer "
                "FROM HANDOFFGUARD.v_excursion_attribution "
                "WHERE excursion_id = {excursion_id} "
                "ORDER BY attribution_rank ASC",
                {"excursion_id": str(excursion_id)},
            )
            if view_rows:
                results: list[AttributionResult] = []
                for r in view_rows:
                    def _k(n):
                        return r.get(n.upper()) or r.get(n)

                    tot_dm = float(_k("handoff_total_dm") or 0.0)
                    share = round(float(_k("exposure_share") or 0.0) * 100.0, 2)
                    ev_status = str(_k("evidence_status") or "INCONCLUSIVE")
                    results.append(
                        AttributionResult(
                            excursion_id=str(_k("excursion_id") or excursion_id),
                            handoff_id=str(_k("handoff_id") or ""),
                            exposure_degree_minutes=tot_dm,
                            exposure_share_pct=share,
                            confidence_score=0.0,
                            confidence_label=ev_status,
                            evidence_json=json.dumps({
                                "evidence_status": ev_status,
                                "disclaimer": str(_k("disclaimer") or ""),
                            }),
                        )
                    )
                return results
        except Exception:
            pass

        # 2. Fallback to ATTRIBUTION_RESULTS table if populated
        try:
            rows = await pool.execute(
                "SELECT EXCURSION_ID, HANDOFF_ID, EXPOSURE_DEGREE_MINUTES, "
                "       EXPOSURE_SHARE_PCT, CONFIDENCE_SCORE, CONFIDENCE_LABEL, EVIDENCE_JSON "
                "FROM HANDOFFGUARD.ATTRIBUTION_RESULTS "
                "WHERE EXCURSION_ID = {excursion_id} "
                "ORDER BY EXPOSURE_SHARE_PCT DESC",
                {"excursion_id": str(excursion_id)},
            )
            return [self._row_to_result(r) for r in rows]
        except Exception:
            return []

    async def upsert_results(self, results: list[AttributionResult]) -> None:
        if not results:
            return
        try:
            pool = get_pool()
            excursion_ids = list({r.excursion_id for r in results})
            for eid in excursion_ids:
                await pool.execute(
                    "DELETE FROM HANDOFFGUARD.ATTRIBUTION_RESULTS "
                    "WHERE EXCURSION_ID = {excursion_id}",
                    {"excursion_id": str(eid)},
                )
            for r in results:
                await pool.execute(
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
        except Exception:
            pass

    async def get_prevention_by_shipment(
        self, shipment_id: str | int
    ) -> list[PreventionSuggestion]:
        try:
            rows = await get_pool().execute(
                "SELECT SHIPMENT_ID, HANDOFF_ID, RISK_SCORE, SUGGESTION, "
                "       RATIONALE, PROTOTYPE_FLAG "
                "FROM HANDOFFGUARD.PREVENTION_SUGGESTIONS "
                "WHERE SHIPMENT_ID = {shipment_id} "
                "ORDER BY RISK_SCORE DESC",
                {"shipment_id": str(shipment_id)},
            )
            return [self._row_to_prevention(r) for r in rows]
        except Exception:
            return []

    async def upsert_prevention(self, suggestions: list[PreventionSuggestion]) -> None:
        if not suggestions:
            return
        try:
            pool = get_pool()
            shipment_ids = list({s.shipment_id for s in suggestions})
            for sid in shipment_ids:
                await pool.execute(
                    "DELETE FROM HANDOFFGUARD.PREVENTION_SUGGESTIONS "
                    "WHERE SHIPMENT_ID = {shipment_id}",
                    {"shipment_id": str(sid)},
                )
            for s in suggestions:
                await pool.execute(
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
        except Exception:
            pass

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
