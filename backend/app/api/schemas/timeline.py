"""Custody timeline schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel
from app.api.schemas.handoff import HandoffResponse
from app.api.schemas.logger import LoggerResponse
from app.api.schemas.reading import TemperatureReadingResponse
from app.api.schemas.excursion import ExcursionResponse
from app.api.schemas.shipment import ProductResponse, ShipmentDetail


class DataQualitySummary(BaseModel):
    total_readings: int
    good_readings: int
    flagged_readings: int
    missing_gaps: int
    loggers_with_skew: int


class ClockSkewCorrection(BaseModel):
    logger_id: str
    skew_seconds: int


class UnassignedIntervalResponse(BaseModel):
    start_utc: str
    end_utc: str


class CustodyTimelineResponse(BaseModel):
    shipment: ShipmentDetail
    product: ProductResponse
    handoffs: list[HandoffResponse]
    loggers: list[LoggerResponse]
    readings: list[TemperatureReadingResponse]
    excursion_intervals: list[ExcursionResponse]
    suspected_handoff_id: Optional[int] = None
    data_quality_summary: DataQualitySummary
    clock_skew_corrections: list[ClockSkewCorrection]
    unassigned_intervals: list[UnassignedIntervalResponse]
