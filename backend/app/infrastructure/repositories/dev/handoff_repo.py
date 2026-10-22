"""Dev SQLAlchemy repository for handoffs."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.models import Handoff
from app.infrastructure.db.dev_db import HandoffORM
from app.infrastructure.repositories.base import AbstractHandoffRepository


def _orm_to_domain(row: HandoffORM) -> Handoff:
    return Handoff(
        handoff_id=row.handoff_id,
        shipment_id=row.shipment_id,
        sequence_no=row.sequence_no,
        handoff_type=row.handoff_type,
        from_party=row.from_party,
        to_party=row.to_party,
        location=row.location,
        window_start_utc=row.window_start_utc,
        window_end_utc=row.window_end_utc,
        reported_start_utc=row.reported_start_utc,
        reported_end_utc=row.reported_end_utc,
        clock_skew_seconds=row.clock_skew_seconds,
        dwell_minutes=row.dwell_minutes,
    )


class DevHandoffRepository(AbstractHandoffRepository):
    """SQLAlchemy-backed handoff repository for dev/test environments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_shipment(self, shipment_id: int) -> list[Handoff]:
        result = await self._session.execute(
            select(HandoffORM)
            .where(HandoffORM.shipment_id == shipment_id)
            .order_by(HandoffORM.sequence_no)
        )
        return [_orm_to_domain(row) for row in result.scalars().all()]

    async def get_by_id(self, handoff_id: int) -> Optional[Handoff]:
        result = await self._session.execute(
            select(HandoffORM).where(HandoffORM.handoff_id == handoff_id)
        )
        row = result.scalar_one_or_none()
        return _orm_to_domain(row) if row else None
