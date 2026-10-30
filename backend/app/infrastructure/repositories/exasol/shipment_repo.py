"""Exasol implementation of AbstractShipmentRepository."""

from __future__ import annotations

from typing import Optional

from app.core.domain.models import Product, Shipment
from app.infrastructure.repositories.base import AbstractShipmentRepository
from app.infrastructure.repositories.exasol.connection import get_pool, _ts


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
            where_clauses.append("UPPER(s.STATUS) = {status}")
            params["status"] = status.upper()

        if search:
            where_clauses.append(
                "(UPPER(s.SHIPMENT_CODE) LIKE {search} "
                " OR UPPER(s.ORIGIN) LIKE {search} "
                " OR UPPER(s.DESTINATION) LIKE {search} "
                " OR UPPER(s.ID) LIKE {search})"
            )
            params["search"] = f"%{search.upper()}%"

        if has_excursion is True:
            where_clauses.append(
                "(EXISTS (SELECT 1 FROM HANDOFFGUARD.EXCURSION_EVENTS e WHERE e.SHIPMENT_ID = s.ID) "
                " OR EXISTS (SELECT 1 FROM HANDOFFGUARD.EXCURSIONS e WHERE e.SHIPMENT_ID = s.ID))"
            )
        elif has_excursion is False:
            where_clauses.append(
                "(NOT EXISTS (SELECT 1 FROM HANDOFFGUARD.EXCURSION_EVENTS e WHERE e.SHIPMENT_ID = s.ID) "
                " AND NOT EXISTS (SELECT 1 FROM HANDOFFGUARD.EXCURSIONS e WHERE e.SHIPMENT_ID = s.ID))"
            )

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        count_sql = (
            f"SELECT COUNT(*) AS total FROM HANDOFFGUARD.SHIPMENTS s {where_sql}"
        )
        count_rows = await get_pool().execute(count_sql, params)
        total = int(count_rows[0].get("TOTAL") or count_rows[0].get("total") or 0)

        offset = (page - 1) * page_size
        data_sql = (
            "SELECT s.ID, s.SHIPMENT_CODE, s.PRODUCT_ID, s.ORIGIN, "
            "       s.DESTINATION, s.DISPATCHED_AT, s.EXPECTED_DELIVERY_AT, s.STATUS, "
            "       p.ID AS PROD_ID, p.NAME, p.MIN_TEMP_C, p.MAX_TEMP_C, "
            "       p.MAX_EXCURSION_MINUTES, p.CATEGORY AS thermal_mass_class "
            "FROM HANDOFFGUARD.SHIPMENTS s "
            "LEFT JOIN HANDOFFGUARD.PRODUCTS p ON s.PRODUCT_ID = p.ID "
            f"{where_sql} "
            "ORDER BY s.DISPATCHED_AT DESC "
            f"LIMIT {page_size} OFFSET {offset}"
        )
        rows = await get_pool().execute(data_sql, params)
        return [self._row_to_shipment(r) for r in rows], total

    async def get_by_id(self, shipment_id: str | int) -> Optional[Shipment]:
        shipment_str = str(shipment_id)
        rows = await get_pool().execute(
            "SELECT s.ID, s.SHIPMENT_CODE, s.PRODUCT_ID, s.ORIGIN, "
            "       s.DESTINATION, s.DISPATCHED_AT, s.EXPECTED_DELIVERY_AT, s.STATUS, "
            "       p.ID AS PROD_ID, p.NAME, p.MIN_TEMP_C, p.MAX_TEMP_C, "
            "       p.MAX_EXCURSION_MINUTES, p.CATEGORY AS thermal_mass_class "
            "FROM HANDOFFGUARD.SHIPMENTS s "
            "LEFT JOIN HANDOFFGUARD.PRODUCTS p ON s.PRODUCT_ID = p.ID "
            "WHERE s.ID = {shipment_id} OR s.SHIPMENT_CODE = {shipment_id}",
            {"shipment_id": shipment_str},
        )
        return self._row_to_shipment(rows[0]) if rows else None

    async def get_upcoming(self) -> list[Shipment]:
        rows = await get_pool().execute(
            "SELECT s.ID, s.SHIPMENT_CODE, s.PRODUCT_ID, s.ORIGIN, "
            "       s.DESTINATION, s.DISPATCHED_AT, s.EXPECTED_DELIVERY_AT, s.STATUS, "
            "       p.ID AS PROD_ID, p.NAME, p.MIN_TEMP_C, p.MAX_TEMP_C, "
            "       p.MAX_EXCURSION_MINUTES, p.CATEGORY AS thermal_mass_class "
            "FROM HANDOFFGUARD.SHIPMENTS s "
            "LEFT JOIN HANDOFFGUARD.PRODUCTS p ON s.PRODUCT_ID = p.ID "
            "WHERE UPPER(s.STATUS) = 'IN_TRANSIT' "
            "ORDER BY s.EXPECTED_DELIVERY_AT ASC"
        )
        return [self._row_to_shipment(r) for r in rows]

    @staticmethod
    def _row_to_shipment(r: dict) -> Shipment:
        def _k(name: str):
            return r.get(name.upper()) or r.get(name)

        prod_id = _k("PROD_ID") or _k("PRODUCT_ID")
        product = None
        if prod_id and _k("NAME"):
            min_temp = _k("MIN_TEMP_C")
            max_temp = _k("MAX_TEMP_C")
            max_exc = _k("MAX_EXCURSION_MINUTES") or _k("ALLOWED_EXCURSION_MINUTES")
            product = Product(
                product_id=str(prod_id),
                name=str(_k("NAME")),
                min_temp_c=float(min_temp) if min_temp is not None else 0.0,
                max_temp_c=float(max_temp) if max_temp is not None else 0.0,
                allowed_excursion_minutes=float(max_exc) if max_exc is not None else 0.0,
                thermal_mass_class=str(_k("THERMAL_MASS_CLASS") or _k("thermal_mass_class") or "Standard"),
            )

        shipment_pk = str(_k("ID") or _k("SHIPMENT_ID"))
        return Shipment(
            shipment_id=shipment_pk,
            shipment_code=str(_k("SHIPMENT_CODE") or shipment_pk),
            product_id=str(_k("PRODUCT_ID") or ""),
            origin=str(_k("ORIGIN") or ""),
            destination=str(_k("DESTINATION") or ""),
            dispatched_at=_ts(_k("DISPATCHED_AT")),
            expected_delivery_at=_ts(_k("EXPECTED_DELIVERY_AT")),
            status=str(_k("STATUS") or ""),
            product=product,
        )
