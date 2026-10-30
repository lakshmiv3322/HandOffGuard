"""Handoff schema."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class HandoffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str | int] = None
    handoff_id: str | int
    shipment_id: str | int
    sequence_no: int
    handoff_type: str
    from_party: str
    to_party: str
    location: str
    window_start_utc: datetime
    window_end_utc: datetime
    reported_start_utc: Optional[datetime] = None
    reported_end_utc: Optional[datetime] = None
    clock_skew_seconds: float = 0.0
    dwell_minutes: float = 0.0
