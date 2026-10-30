"""Exasol implementation of AbstractProductRepository."""

from __future__ import annotations

from typing import Optional

from app.core.domain.models import Product
from app.infrastructure.repositories.base import AbstractProductRepository
from app.infrastructure.repositories.exasol.connection import get_pool, _ts


class ExasolProductRepository(AbstractProductRepository):

    async def get_all(self) -> list[Product]:
        rows = await get_pool().execute(
            "SELECT ID, NAME, MIN_TEMP_C, MAX_TEMP_C, "
            "       MAX_EXCURSION_MINUTES, CATEGORY AS THERMAL_MASS_CLASS "
            "FROM HANDOFFGUARD.PRODUCTS "
            "ORDER BY NAME"
        )
        return [self._row_to_product(r) for r in rows]

    async def get_by_id(self, product_id: str | int) -> Optional[Product]:
        rows = await get_pool().execute(
            "SELECT ID, NAME, MIN_TEMP_C, MAX_TEMP_C, "
            "       MAX_EXCURSION_MINUTES, CATEGORY AS THERMAL_MASS_CLASS "
            "FROM HANDOFFGUARD.PRODUCTS WHERE ID = {product_id}",
            {"product_id": str(product_id)},
        )
        return self._row_to_product(rows[0]) if rows else None

    @staticmethod
    def _row_to_product(r: dict) -> Product:
        def _k(name: str):
            return r.get(name.upper()) or r.get(name)

        min_temp = _k("MIN_TEMP_C")
        max_temp = _k("MAX_TEMP_C")
        max_exc = _k("MAX_EXCURSION_MINUTES") or _k("ALLOWED_EXCURSION_MINUTES")

        return Product(
            product_id=str(_k("ID") or _k("PRODUCT_ID")),
            name=str(_k("NAME") or ""),
            min_temp_c=float(min_temp) if min_temp is not None else 0.0,
            max_temp_c=float(max_temp) if max_temp is not None else 0.0,
            allowed_excursion_minutes=float(max_exc) if max_exc is not None else 0.0,
            thermal_mass_class=str(_k("THERMAL_MASS_CLASS") or _k("CATEGORY") or "Standard"),
        )
