"""Dev SQLAlchemy repository for excursion events."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.models import ExcursionEvent
from app.infrastructure.db.dev_db import ExcursionEventORM
from app.infrastructure.repositories.base import AbstractExcursionRepository


def _orm_to_domain(row: ExcursionEventORM) -> ExcursionEvent:
    return ExcursionEvent(
        excursion_id=row.excursion_id,
        shipment_id=row.shipment_id,
        started_at_utc=row.started_at_utc,
        ended_at_utc=row.ended_at_utc,
        duration_minutes=row.duration_minutes,
        peak_temp_c=row.peak_temp_c,
        severity=row.severity,
        ground_truth_handoff_id=row.ground_truth_handoff_id,
        ground_truth_cause=row.ground_truth_cause,
    )


class DevExcursionRepository(AbstractExcursionRepository):
    """SQLAlchemy-backed excursion repository for dev/test environments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_shipment(self, shipment_id: int) -> list[ExcursionEvent]:
        result = await self._session.execute(
            select(ExcursionEventORM)
            .where(ExcursionEventORM.shipment_id == shipment_id)
            .order_by(ExcursionEventORM.started_at_utc)
        )
        return [_orm_to_domain(row) for row in result.scalars().all()]

    async def get_by_id(self, excursion_id: int) -> Optional[ExcursionEvent]:
        result = await self._session.execute(
            select(ExcursionEventORM).where(ExcursionEventORM.excursion_id == excursion_id)
        )
        row = result.scalar_one_or_none()
        return _orm_to_domain(row) if row else None
