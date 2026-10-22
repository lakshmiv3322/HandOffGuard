"""Temperature reading schema."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TemperatureReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reading_id: int
    logger_id: int
    recorded_at_utc: datetime
    temperature_c: float
    humidity_pct: Optional[float] = None
    battery_pct: Optional[float] = None
    quality_flag: str
