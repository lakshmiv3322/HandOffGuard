"""Attribution schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.api.schemas.excursion import ExcursionResponse


class AttributionHandoffItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: Optional[int] = None  # None when inconclusive (no winning rank assigned)
    is_candidate_only: bool = False
    handoff_id: str | int
    handoff_label: str
    sequence_no: int
    handoff_type: str
    from_party: str
    to_party: str
    location: str
    observed_reading_count: int = 0
    supported_observation_minutes: float = 0.0
    unsupported_gap_minutes: float = 0.0
    exposure_degree_minutes: Optional[float] = None  # None when unavailable due to insufficient data
    exposure_share_pct: Optional[float] = None
    allowed_excursion_time_consumed_pct: Optional[float] = None
    confidence_score: Optional[float] = None  # Null unless calibrated method exists
    confidence_label: str
    duration_outside_safe_range_minutes: float
    peak_temp_c: float  # Preserved observed peak temperature
    reading_count: int
    logger_ids: list[str]
    clock_skew_corrections: list[float]
    has_missing_gaps: bool
    has_overlapping_windows: bool
    first_threshold_crossing_utc: Optional[str] = None
    evidence_notes: list[str]
    matches_naive_baseline: Optional[bool] = None


class NaiveBaselineComparison(BaseModel):
    handoff_id: Optional[str | int] = None
    handoff_label: str
    first_crossing_utc: Optional[str] = None
    agrees_with_top_ranked: bool
    explanation: str


class AttributionResponse(BaseModel):
    excursion_id: str | int
    shipment_id: Optional[str | int] = None
    attribution_status: str  # e.g. "INCONCLUSIVE_INSUFFICIENT_DATA", "PROTOTYPE_RANKING"
    selected_handoff_id: Optional[str | int] = None  # Null when inconclusive
    excursion: ExcursionResponse
    ranked_handoffs: list[AttributionHandoffItem]
    top_ranked_handoff: Optional[AttributionHandoffItem] = None
    naive_baseline: Optional[NaiveBaselineComparison] = None
    disclaimer: str
    limitations: list[str]


class AttributionSummaryItem(BaseModel):
    excursion_id: str | int
    severity: str
    duration_minutes: float
    peak_temp_c: float
    top_handoff_id: Optional[str | int] = None
    top_handoff_label: Optional[str] = None
    top_exposure_share_pct: float = 0.0
    confidence_label: str = "Low"
    naive_agrees: bool = False
