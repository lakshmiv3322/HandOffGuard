"""Logger schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LoggerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str | int] = None
    logger_id: str | int
    device_type: str
    assigned_shipment_id: str | int
    sampling_interval_seconds: int = 300
    clock_skew_seconds: float = 0.0
    data_quality_flag: str = "good"
