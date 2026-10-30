"""Exasol implementation of AbstractShipmentRepository."""

from __future__ import annotations

from typing import Optional

from app.core.domain.models import Product, Shipment
from app.infrastructure.repositories.base import AbstractShipmentRepository
from app.infrastructure.repositories.exasol.connection import get_pool, _ts
from app.infrastructure.repositories.exasol.product_repo import ExasolProductRepository


class ExasolShipmentRepository(AbstractShipmentRepository):

    async def get_all(
        self,
        status: Optional[str] = None,
        has_excursion: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Shipment], int]:
        where_clauses = []
        params: dict = {}

        if status:
            where_clauses.append("s.status = {status}")
            params["status"] = status

        if search:
            where_clauses.append(
                "(UPPER(s.shipment_code) LIKE {search} "
                " OR UPPER(s.origin) LIKE {search} "
                " OR UPPER(s.destination) LIKE {search})"
            )
            params["search"] = f"%{search.upper()}%"

        if has_excursion is True:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM HANDOFFGUARD.excursions e "
                "        WHERE e.shipment_id = s.shipment_id)"
            )
        elif has_excursion is False:
            where_clauses.append(
                "NOT EXISTS (SELECT 1 FROM HANDOFFGUARD.excursions e "
                "            WHERE e.shipment_id = s.shipment_id)"
            )

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        count_sql = (
            f"SELECT COUNT(*) AS total FROM HANDOFFGUARD.shipments s {where_sql}"
        )
        count_rows = await get_pool().execute(count_sql, params)
        total = int(count_rows[0].get("TOTAL") or count_rows[0].get("total") or 0)

        offset = (page - 1) * page_size
        data_sql = (
            "SELECT s.shipment_id, s.shipment_code, s.product_id, s.origin, "
            "       s.destination, s.dispatched_at, s.expected_delivery_at, s.status, "
            "       p.name, p.min_temp_c, p.max_temp_c, "
            "       p.allowed_excursion_minutes, p.thermal_mass_class "
            "FROM HANDOFFGUARD.shipments s "
            "JOIN HANDOFFGUARD.products p ON s.product_id = p.product_id "
            f"{where_sql} "
            "ORDER BY s.dispatched_at DESC "
            f"LIMIT {page_size} OFFSET {offset}"
        )
        rows = await get_pool().execute(data_sql, params)
        return [self._row_to_shipment(r) for r in rows], total

    async def get_by_id(self, shipment_id: int) -> Optional[Shipment]:
        rows = await get_pool().execute(
            "SELECT s.shipment_id, s.shipment_code, s.product_id, s.origin, "
            "       s.destination, s.dispatched_at, s.expected_delivery_at, s.status, "
            "       p.name, p.min_temp_c, p.max_temp_c, "
            "       p.allowed_excursion_minutes, p.thermal_mass_class "
            "FROM HANDOFFGUARD.shipments s "
            "JOIN HANDOFFGUARD.products p ON s.product_id = p.product_id "
            "WHERE s.shipment_id = {shipment_id!d}",
            {"shipment_id": shipment_id},
        )
        return self._row_to_shipment(rows[0]) if rows else None

    async def get_upcoming(self) -> list[Shipment]:
        rows = await get_pool().execute(
            "SELECT s.shipment_id, s.shipment_code, s.product_id, s.origin, "
            "       s.destination, s.dispatched_at, s.expected_delivery_at, s.status, "
            "       p.name, p.min_temp_c, p.max_temp_c, "
            "       p.allowed_excursion_minutes, p.thermal_mass_class "
            "FROM HANDOFFGUARD.shipments s "
            "JOIN HANDOFFGUARD.products p ON s.product_id = p.product_id "
            "WHERE s.status = 'in_transit' "
            "ORDER BY s.expected_delivery_at ASC"
        )
        return [self._row_to_shipment(r) for r in rows]

    @staticmethod
    def _row_to_shipment(r: dict) -> Shipment:
        def _k(name: str):
            return r.get(name.upper()) or r.get(name)

        product = Product(
            product_id=int(_k("product_id")),
            name=str(_k("name")),
            min_temp_c=float(_k("min_temp_c")),
            max_temp_c=float(_k("max_temp_c")),
            allowed_excursion_minutes=float(_k("allowed_excursion_minutes")),
            thermal_mass_class=str(_k("thermal_mass_class")),
        )
        return Shipment(
            shipment_id=int(_k("shipment_id")),
            shipment_code=str(_k("shipment_code")),
            product_id=int(_k("product_id")),
            origin=str(_k("origin")),
            destination=str(_k("destination")),
            dispatched_at=_ts(_k("dispatched_at")),
            expected_delivery_at=_ts(_k("expected_delivery_at")),
            status=str(_k("status")),
            product=product,
        )
