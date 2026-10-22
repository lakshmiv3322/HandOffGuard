"""Shipment schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    name: str
    min_temp_c: float
    max_temp_c: float
    allowed_excursion_minutes: float
    thermal_mass_class: str


class ShipmentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shipment_id: int
    shipment_code: str
    product_name: str
    origin: str
    destination: str
    dispatched_at: datetime
    expected_delivery_at: datetime
    status: str
    has_excursion: bool
    total_exposure_degree_minutes: float
    worst_severity: Optional[str] = None


class ShipmentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shipment_id: int
    shipment_code: str
    product: ProductResponse
    origin: str
    destination: str
    dispatched_at: datetime
    expected_delivery_at: datetime
    status: str
    handoff_count: int
    logger_count: int
    excursion_count: int
    has_excursion: bool
    attribution_status: str
