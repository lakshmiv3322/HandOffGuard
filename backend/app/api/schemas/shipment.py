"""Shipment schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str | int] = None
    product_id: str | int
    name: str
    min_temp_c: float
    max_temp_c: float
    allowed_excursion_minutes: float = 0.0
    thermal_mass_class: str = "Standard"


class ShipmentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | int
    shipment_id: str | int
    shipment_code: str
    product_name: str
    origin: str
    destination: str
    dispatched_at: Optional[datetime] = None
    expected_delivery_at: Optional[datetime] = None
    status: str
    has_excursion: bool = False
    total_exposure_degree_minutes: float = 0.0
    worst_severity: Optional[str] = None


class ShipmentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | int
    shipment_id: str | int
    shipment_code: str
    product: Optional[ProductResponse] = None
    origin: str
    destination: str
    dispatched_at: Optional[datetime] = None
    expected_delivery_at: Optional[datetime] = None
    status: str
    handoff_count: int = 0
    logger_count: int = 0
    excursion_count: int = 0
    has_excursion: bool = False
    attribution_status: str = "Compliant"
