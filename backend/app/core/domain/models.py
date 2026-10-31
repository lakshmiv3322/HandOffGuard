"""
Pure domain dataclasses and Pydantic models used throughout the application.

These types are database-agnostic and framework-agnostic. They represent
the business concepts of the HandoffGuard domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.core.domain.constants import (
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LABEL_HIGH,
    CONFIDENCE_LABEL_LOW,
    CONFIDENCE_LABEL_MEDIUM,
    CONFIDENCE_MEDIUM_THRESHOLD,
    QUALITY_FLAG_GOOD,
    UNASSIGNED_LABEL,
)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Product:
    """A pharmaceutical product with its cold-chain temperature requirements."""

    product_id: str | int
    name: str
    min_temp_c: float
    max_temp_c: float
    allowed_excursion_minutes: float = 0.0
    thermal_mass_class: str = "Standard"

    @property
    def id(self) -> str | int:
        return self.product_id


# ---------------------------------------------------------------------------
# Shipments
# ---------------------------------------------------------------------------


@dataclass
class Shipment:
    """A single cold-chain shipment from origin to destination."""

    shipment_id: str | int
    shipment_code: str
    product_id: str | int
    origin: str
    destination: str
    dispatched_at: Optional[datetime]
    expected_delivery_at: Optional[datetime]
    status: str

    # Joined / computed fields (not stored in the shipments table)
    product: Optional[Product] = field(default=None, compare=False)

    @property
    def id(self) -> str | int:
        return self.shipment_id


# ---------------------------------------------------------------------------
# Handoffs
# ---------------------------------------------------------------------------


@dataclass
class Handoff:
    """
    A single custody segment within a shipment.

    A handoff represents the time window during which a specific party
    (e.g., a courier, warehouse, airline) is responsible for the shipment.
    """

    handoff_id: str | int
    shipment_id: str | int
    sequence_no: int
    handoff_type: str
    from_party: str
    to_party: str
    location: str
    window_start_utc: datetime
    window_end_utc: datetime
    reported_start_utc: Optional[datetime]
    reported_end_utc: Optional[datetime]
    clock_skew_seconds: float
    dwell_minutes: float

    @property
    def id(self) -> str | int:
        return self.handoff_id


# ---------------------------------------------------------------------------
# Loggers
# ---------------------------------------------------------------------------


@dataclass
class Logger:
    """A temperature-logging device assigned to a shipment."""

    logger_id: str | int
    device_type: str
    assigned_shipment_id: str | int
    sampling_interval_seconds: int
    clock_skew_seconds: float
    data_quality_flag: str

    @property
    def id(self) -> str | int:
        return self.logger_id


# ---------------------------------------------------------------------------
# Temperature readings
# ---------------------------------------------------------------------------


@dataclass
class TemperatureReading:
    """
    A single temperature observation recorded by a logger device.

    IMPORTANT: This model intentionally has no handoff_id field.
    Reading-to-handoff assignment is performed in code via interval overlap.
    """

    reading_id: str | int
    logger_id: str | int
    recorded_at_utc: datetime
    temperature_c: float
    humidity_pct: Optional[float]
    battery_pct: Optional[float]
    quality_flag: str

    @property
    def id(self) -> str | int:
        return self.reading_id


# ---------------------------------------------------------------------------
# Excursion events
# ---------------------------------------------------------------------------


@dataclass
class ExcursionEvent:
    """A detected temperature excursion event for a shipment."""

    excursion_id: str | int
    shipment_id: str | int
    started_at_utc: datetime
    ended_at_utc: datetime
    duration_minutes: float
    peak_temp_c: float
    severity: str
    ground_truth_handoff_id: Optional[str | int]
    ground_truth_cause: Optional[str]

    @property
    def id(self) -> str | int:
        return self.excursion_id


# ---------------------------------------------------------------------------
# Attribution results
# ---------------------------------------------------------------------------


@dataclass
class AttributionResult:
    """
    Computed attribution of an excursion to a specific handoff.

    One excursion can have multiple attribution result rows, one per handoff
    that is considered responsible for some portion of the exposure.
    """

    excursion_id: int
    handoff_id: int
    exposure_degree_minutes: float
    exposure_share_pct: float
    confidence_score: float
    confidence_label: str
    evidence_json: str  # JSON-serialised evidence dict


# ---------------------------------------------------------------------------
# Prevention suggestions
# ---------------------------------------------------------------------------


@dataclass
class PreventionSuggestion:
    """A proactive risk-reduction suggestion for an upcoming shipment handoff."""

    shipment_id: str | int
    handoff_id: str | int
    risk_score: float
    suggestion: str
    rationale: str
    prototype_flag: bool


# ---------------------------------------------------------------------------
# Computed / intermediate domain objects
# ---------------------------------------------------------------------------


@dataclass
class ReadingWithCorrection:
    """A temperature reading with its clock-skew-corrected timestamp."""

    reading: TemperatureReading
    corrected_at_utc: datetime
    logger: Logger


@dataclass
class HandoffExposure:
    """
    Aggregated exposure metrics for a single handoff within an excursion.

    Produced by the ExposureService and consumed by AttributionService.
    """

    handoff: Handoff
    exposure_degree_minutes: float
    reading_count: int
    expected_reading_count: int
    good_quality_reading_count: int
    ambiguous_reading_count: int
    readings: list[ReadingWithCorrection] = field(default_factory=list)

    @property
    def coverage_ratio(self) -> float:
        """Fraction of expected readings that were actually observed."""
        if self.expected_reading_count == 0:
            return 0.0
        return min(1.0, self.reading_count / self.expected_reading_count)

    @property
    def quality_ratio(self) -> float:
        """Fraction of observed readings with a good quality flag."""
        if self.reading_count == 0:
            return 0.0
        return self.good_quality_reading_count / self.reading_count


@dataclass
class UnassignedInterval:
    """A contiguous block of readings that could not be assigned to any handoff."""

    label: str
    start_utc: datetime
    end_utc: datetime
    reading_count: int
    exposure_degree_minutes: float


@dataclass
class NaiveBaselineResult:
    """Result of the naive attribution baseline (blame-first-crossing)."""

    naive_handoff_id: Optional[int]
    naive_handoff_label: str
    handoffguard_top_handoff_id: Optional[int]
    agree: bool
    explanation: str


@dataclass
class ConfidenceAssessment:
    """Confidence score and label for a ranked attribution result."""

    raw_score: float
    adjusted_score: float
    label: str
    coverage_ratio: float
    quality_ratio: float
    clock_skew_penalty_applied: bool
    ambiguity_penalty_applied: bool

    @staticmethod
    def label_for_score(score: float) -> str:
        """Return the human-readable confidence label for a numeric score."""
        if score >= CONFIDENCE_HIGH_THRESHOLD:
            return CONFIDENCE_LABEL_HIGH
        if score >= CONFIDENCE_MEDIUM_THRESHOLD:
            return CONFIDENCE_LABEL_MEDIUM
        return CONFIDENCE_LABEL_LOW


@dataclass
class EvidenceBundle:
    """
    All evidence gathered for one handoff's attribution.

    Serialised to JSON and stored in attribution_results.evidence_json.
    """

    handoff_id: int
    handoff_label: str
    reading_count: int
    expected_reading_count: int
    good_quality_reading_count: int
    ambiguous_reading_count: int
    coverage_ratio: float
    quality_ratio: float
    clock_skew_seconds: float
    clock_skew_penalty_applied: bool
    ambiguity_penalty: float
    peak_temp_c: Optional[float]
    first_excursion_reading_at: Optional[str]  # ISO string
