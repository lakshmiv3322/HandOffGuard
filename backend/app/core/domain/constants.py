"""
Domain constants for HandoffGuard.

All numeric thresholds and labels used across services live here.
No magic numbers should appear in service code.
"""

# ---------------------------------------------------------------------------
# Clock-skew & time alignment
# ---------------------------------------------------------------------------

# Default tolerance applied to handoff window boundaries when assigning readings.
# A reading is eligible for a handoff if its corrected timestamp falls within
# [window_start - tolerance, window_end + tolerance].
DEFAULT_SKEW_TOLERANCE_SECONDS: int = 120

# If a logger's |clock_skew_seconds| exceeds this threshold the confidence score
# receives a penalty during attribution.
CLOCK_SKEW_PENALTY_THRESHOLD_SECONDS: int = 300

# ---------------------------------------------------------------------------
# Confidence score thresholds
# ---------------------------------------------------------------------------

CONFIDENCE_HIGH_THRESHOLD: float = 0.75
CONFIDENCE_MEDIUM_THRESHOLD: float = 0.45

CONFIDENCE_LABEL_HIGH: str = "High"
CONFIDENCE_LABEL_MEDIUM: str = "Medium"
CONFIDENCE_LABEL_LOW: str = "Low"

# ---------------------------------------------------------------------------
# Confidence score adjustment weights
# ---------------------------------------------------------------------------

# Weight of data coverage in the confidence adjustment
COVERAGE_WEIGHT: float = 0.30

# Weight of data quality (good readings fraction) in the confidence adjustment
QUALITY_WEIGHT: float = 0.25

# Penalty subtracted from confidence when |clock_skew| > threshold
CLOCK_SKEW_CONFIDENCE_PENALTY: float = 0.10

# Penalty subtracted per ambiguous reading assignment (capped at 0.15)
AMBIGUITY_CONFIDENCE_PENALTY_PER_READING: float = 0.02
MAX_AMBIGUITY_PENALTY: float = 0.15

# ---------------------------------------------------------------------------
# Excursion severity thresholds (degree-minutes above safe range)
# ---------------------------------------------------------------------------

SEVERITY_CRITICAL_THRESHOLD_DEGREE_MINUTES: float = 100.0
SEVERITY_HIGH_THRESHOLD_DEGREE_MINUTES: float = 50.0
SEVERITY_MEDIUM_THRESHOLD_DEGREE_MINUTES: float = 10.0

SEVERITY_CRITICAL: str = "critical"
SEVERITY_HIGH: str = "high"
SEVERITY_MEDIUM: str = "medium"
SEVERITY_LOW: str = "low"

# ---------------------------------------------------------------------------
# Timeline / chart
# ---------------------------------------------------------------------------

# Maximum readings returned per logger in the custody-timeline response.
MAX_CHART_POINTS_PER_LOGGER: int = 500

# Label used when a reading cannot be assigned to any handoff window.
UNASSIGNED_LABEL: str = "Unassigned / in-transit gap"

# ---------------------------------------------------------------------------
# Quality flags
# ---------------------------------------------------------------------------

QUALITY_FLAG_GOOD: str = "good"
QUALITY_FLAG_SUSPECT: str = "suspect"
QUALITY_FLAG_BAD: str = "bad"

GOOD_QUALITY_FLAGS: frozenset[str] = frozenset({QUALITY_FLAG_GOOD})

# ---------------------------------------------------------------------------
# Shipment statuses
# ---------------------------------------------------------------------------

STATUS_IN_TRANSIT: str = "in_transit"
STATUS_DELIVERED: str = "delivered"
STATUS_CANCELLED: str = "cancelled"

# ---------------------------------------------------------------------------
# Handoff types
# ---------------------------------------------------------------------------

HANDOFF_TYPE_PICKUP: str = "pickup"
HANDOFF_TYPE_TRANSFER: str = "transfer"
HANDOFF_TYPE_DELIVERY: str = "delivery"
HANDOFF_TYPE_STORAGE: str = "storage"

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

SCHEMA_VERSION: str = "1.0.0"
