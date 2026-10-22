"""Logger schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LoggerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    logger_id: int
    device_type: str
    assigned_shipment_id: int
    sampling_interval_seconds: int
    clock_skew_seconds: float
    data_quality_flag: str
