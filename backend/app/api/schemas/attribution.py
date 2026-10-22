"""Attribution schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.api.schemas.excursion import ExcursionResponse


class AttributionHandoffItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    handoff_id: int
    handoff_label: str
    sequence_no: int
    handoff_type: str
    from_party: str
    to_party: str
    location: str
    exposure_degree_minutes: float
    exposure_share_pct: float
    allowed_excursion_time_consumed_pct: float
    confidence_score: float
    confidence_label: str
    duration_outside_safe_range_minutes: float
    peak_temp_c: float
    reading_count: int
    logger_ids: list[str]
    clock_skew_corrections: list[float]
    has_missing_gaps: bool
    has_overlapping_windows: bool
    first_threshold_crossing_utc: Optional[str] = None
    evidence_notes: list[str]
    matches_naive_baseline: bool = False


class NaiveBaselineComparison(BaseModel):
    handoff_id: Optional[int] = None
    handoff_label: str
    first_crossing_utc: Optional[str] = None
    agrees_with_top_ranked: bool
    explanation: str


class AttributionResponse(BaseModel):
    excursion_id: int
    excursion: ExcursionResponse
    ranked_handoffs: list[AttributionHandoffItem]
    top_ranked_handoff: Optional[AttributionHandoffItem] = None
    naive_baseline: Optional[NaiveBaselineComparison] = None
    disclaimer: str
    limitations: list[str]


class AttributionSummaryItem(BaseModel):
    excursion_id: int
    severity: str
    duration_minutes: float
    peak_temp_c: float
    top_handoff_id: Optional[int] = None
    top_handoff_label: Optional[str] = None
    top_exposure_share_pct: float = 0.0
    confidence_label: str = "Low"
    naive_agrees: bool = False
