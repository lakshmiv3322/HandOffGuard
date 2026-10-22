"""Dev SQLAlchemy repository for shipments."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.domain.models import Product, Shipment
from app.infrastructure.db.dev_db import ExcursionEventORM, ProductORM, ShipmentORM
from app.infrastructure.repositories.base import AbstractShipmentRepository


def _orm_to_domain(row: ShipmentORM) -> Shipment:
    product: Optional[Product] = None
    if row.product:
        product = Product(
            product_id=row.product.product_id,
            name=row.product.name,
            min_temp_c=row.product.min_temp_c,
            max_temp_c=row.product.max_temp_c,
            allowed_excursion_minutes=row.product.allowed_excursion_minutes,
            thermal_mass_class=row.product.thermal_mass_class,
        )
    return Shipment(
        shipment_id=row.shipment_id,
        shipment_code=row.shipment_code,
        product_id=row.product_id,
        origin=row.origin,
        destination=row.destination,
        dispatched_at=row.dispatched_at,
        expected_delivery_at=row.expected_delivery_at,
        status=row.status,
        product=product,
    )


class DevShipmentRepository(AbstractShipmentRepository):
    """SQLAlchemy-backed shipment repository for dev/test environments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(
        self,
        status: Optional[str] = None,
        has_excursion: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Shipment], int]:
        query = (
            select(ShipmentORM)
            .options(selectinload(ShipmentORM.product))
            .order_by(ShipmentORM.dispatched_at.desc())
        )

        if status:
            query = query.where(ShipmentORM.status == status)

        if has_excursion is True:
            subq = select(ExcursionEventORM.shipment_id).distinct()
            query = query.where(ShipmentORM.shipment_id.in_(subq))
        elif has_excursion is False:
            subq = select(ExcursionEventORM.shipment_id).distinct()
            query = query.where(ShipmentORM.shipment_id.not_in(subq))

        if search:
            pattern = f"%{search}%"
            query = query.where(
                ShipmentORM.shipment_code.ilike(pattern)
                | ShipmentORM.origin.ilike(pattern)
                | ShipmentORM.destination.ilike(pattern)
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self._session.execute(query)
        return [_orm_to_domain(row) for row in result.scalars().all()], total

    async def get_by_id(self, shipment_id: int) -> Optional[Shipment]:
        result = await self._session.execute(
            select(ShipmentORM)
            .options(selectinload(ShipmentORM.product))
            .where(ShipmentORM.shipment_id == shipment_id)
        )
        row = result.scalar_one_or_none()
        return _orm_to_domain(row) if row else None

    async def get_upcoming(self) -> list[Shipment]:
        result = await self._session.execute(
            select(ShipmentORM)
            .options(selectinload(ShipmentORM.product))
            .where(ShipmentORM.status == "in_transit")
            .order_by(ShipmentORM.expected_delivery_at.asc())
        )
        return [_orm_to_domain(row) for row in result.scalars().all()]
