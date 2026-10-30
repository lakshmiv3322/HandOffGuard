"""Exasol implementation of AbstractProductRepository."""

from __future__ import annotations

from typing import Optional

from app.core.domain.models import Product
from app.infrastructure.repositories.base import AbstractProductRepository
from app.infrastructure.repositories.exasol.connection import get_pool, _ts


class ExasolProductRepository(AbstractProductRepository):

    async def get_all(self) -> list[Product]:
        rows = await get_pool().execute(
            "SELECT product_id, name, min_temp_c, max_temp_c, "
            "       allowed_excursion_minutes, thermal_mass_class "
            "FROM HANDOFFGUARD.products "
            "ORDER BY name"
        )
        return [self._row_to_product(r) for r in rows]

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        rows = await get_pool().execute(
            "SELECT product_id, name, min_temp_c, max_temp_c, "
            "       allowed_excursion_minutes, thermal_mass_class "
            "FROM HANDOFFGUARD.products WHERE product_id = {product_id!d}",
            {"product_id": product_id},
        )
        return self._row_to_product(rows[0]) if rows else None

    @staticmethod
    def _row_to_product(r: dict) -> Product:
        return Product(
            product_id=int(r.get("PRODUCT_ID") or r.get("product_id")),
            name=str(r.get("NAME") or r.get("name")),
            min_temp_c=float(r.get("MIN_TEMP_C") or r.get("min_temp_c")),
            max_temp_c=float(r.get("MAX_TEMP_C") or r.get("max_temp_c")),
            allowed_excursion_minutes=float(
                r.get("ALLOWED_EXCURSION_MINUTES") or r.get("allowed_excursion_minutes")
            ),
            thermal_mass_class=str(
                r.get("THERMAL_MASS_CLASS") or r.get("thermal_mass_class")
            ),
        )
