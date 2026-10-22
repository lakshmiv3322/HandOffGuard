"""Dev SQLAlchemy repository for attribution results and prevention suggestions."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.models import AttributionResult, PreventionSuggestion
from app.infrastructure.db.dev_db import AttributionResultORM, PreventionSuggestionORM
from app.infrastructure.repositories.base import AbstractAttributionRepository


def _attr_orm_to_domain(row: AttributionResultORM) -> AttributionResult:
    return AttributionResult(
        excursion_id=row.excursion_id,
        handoff_id=row.handoff_id,
        exposure_degree_minutes=row.exposure_degree_minutes,
        exposure_share_pct=row.exposure_share_pct,
        confidence_score=row.confidence_score,
        confidence_label=row.confidence_label,
        evidence_json=row.evidence_json,
    )


def _prev_orm_to_domain(row: PreventionSuggestionORM) -> PreventionSuggestion:
    return PreventionSuggestion(
        shipment_id=row.shipment_id,
        handoff_id=row.handoff_id,
        risk_score=row.risk_score,
        suggestion=row.suggestion,
        rationale=row.rationale,
        prototype_flag=row.prototype_flag,
    )


class DevAttributionRepository(AbstractAttributionRepository):
    """SQLAlchemy-backed attribution & prevention repository for dev/test environments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_excursion(self, excursion_id: int) -> list[AttributionResult]:
        result = await self._session.execute(
            select(AttributionResultORM)
            .where(AttributionResultORM.excursion_id == excursion_id)
            .order_by(AttributionResultORM.exposure_share_pct.desc())
        )
        return [_attr_orm_to_domain(row) for row in result.scalars().all()]

    async def upsert_results(self, results: list[AttributionResult]) -> None:
        """Delete existing rows for the excursion then insert fresh ones."""
        if not results:
            return
        excursion_id = results[0].excursion_id
        await self._session.execute(
            delete(AttributionResultORM).where(
                AttributionResultORM.excursion_id == excursion_id
            )
        )
        for attr in results:
            orm_row = AttributionResultORM(
                excursion_id=attr.excursion_id,
                handoff_id=attr.handoff_id,
                exposure_degree_minutes=attr.exposure_degree_minutes,
                exposure_share_pct=attr.exposure_share_pct,
                confidence_score=attr.confidence_score,
                confidence_label=attr.confidence_label,
                evidence_json=attr.evidence_json,
            )
            self._session.add(orm_row)
        await self._session.flush()

    async def get_prevention_by_shipment(
        self, shipment_id: int
    ) -> list[PreventionSuggestion]:
        result = await self._session.execute(
            select(PreventionSuggestionORM)
            .where(PreventionSuggestionORM.shipment_id == shipment_id)
            .order_by(PreventionSuggestionORM.risk_score.desc())
        )
        return [_prev_orm_to_domain(row) for row in result.scalars().all()]

    async def upsert_prevention(self, suggestions: list[PreventionSuggestion]) -> None:
        """Delete existing suggestions for the shipment then insert fresh ones."""
        if not suggestions:
            return
        shipment_id = suggestions[0].shipment_id
        await self._session.execute(
            delete(PreventionSuggestionORM).where(
                PreventionSuggestionORM.shipment_id == shipment_id
            )
        )
        for suggestion in suggestions:
            orm_row = PreventionSuggestionORM(
                shipment_id=suggestion.shipment_id,
                handoff_id=suggestion.handoff_id,
                risk_score=suggestion.risk_score,
                suggestion=suggestion.suggestion,
                rationale=suggestion.rationale,
                prototype_flag=suggestion.prototype_flag,
            )
            self._session.add(orm_row)
        await self._session.flush()
