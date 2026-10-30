"""Dev SQLAlchemy repository for products."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.models import Product
from app.infrastructure.db.dev_db import ProductORM
from app.infrastructure.repositories.base import AbstractProductRepository


def _orm_to_domain(row: ProductORM) -> Product:
    return Product(
        product_id=row.product_id,
        name=row.name,
        min_temp_c=row.min_temp_c,
        max_temp_c=row.max_temp_c,
        allowed_excursion_minutes=row.allowed_excursion_minutes,
        thermal_mass_class=row.thermal_mass_class,
    )


class DevProductRepository(AbstractProductRepository):
    """SQLAlchemy-backed product repository for dev/test environments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> list[Product]:
        result = await self._session.execute(select(ProductORM))
        return [_orm_to_domain(row) for row in result.scalars().all()]

    async def get_by_id(self, product_id: str | int) -> Optional[Product]:
        pid = int(product_id) if str(product_id).isdigit() else 0
        result = await self._session.execute(
            select(ProductORM).where(ProductORM.product_id == pid)
        )
        row = result.scalar_one_or_none()
        return _orm_to_domain(row) if row else None
