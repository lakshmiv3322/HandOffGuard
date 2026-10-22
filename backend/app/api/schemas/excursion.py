"""Excursion event schema."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ExcursionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    excursion_id: int
    shipment_id: int
    started_at_utc: datetime
    ended_at_utc: datetime
    duration_minutes: float
    peak_temp_c: float
    severity: str
    ground_truth_handoff_id: Optional[int] = None
    ground_truth_cause: Optional[str] = None
