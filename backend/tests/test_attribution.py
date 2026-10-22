"""Tests for attribution ranking, confidence labels, and naive baseline comparison."""

from datetime import datetime, timedelta
import pytest

from app.core.domain.constants import (
    CONFIDENCE_LABEL_HIGH,
    CONFIDENCE_LABEL_LOW,
    CONFIDENCE_LABEL_MEDIUM,
)
from app.core.domain.models import ExcursionEvent, TemperatureReading
from app.core.services.attribution_service import AttributionService


def test_confidence_label_thresholds():
    """Verify confidence score mapping to High, Medium, Low."""
    from app.core.domain.models import ConfidenceAssessment

    assert ConfidenceAssessment.label_for_score(0.85) == CONFIDENCE_LABEL_HIGH
    assert ConfidenceAssessment.label_for_score(0.75) == CONFIDENCE_LABEL_HIGH
    assert ConfidenceAssessment.label_for_score(0.74) == CONFIDENCE_LABEL_MEDIUM
    assert ConfidenceAssessment.label_for_score(0.45) == CONFIDENCE_LABEL_MEDIUM
    assert ConfidenceAssessment.label_for_score(0.44) == CONFIDENCE_LABEL_LOW
    assert ConfidenceAssessment.label_for_score(0.10) == CONFIDENCE_LABEL_LOW


def test_naive_baseline_difference(sample_shipment, sample_product, sample_handoffs, sample_loggers):
    """
    Scenario:
    Handoff 1 has a tiny first crossing (8.1°C for 5 mins = 0.5 °C·min).
    Handoff 2 has a large sustained breach (14.0°C for 60 mins = 360 °C·min).
    Naive baseline must blame Handoff 1.
    HandoffGuard must rank Handoff 2 as #1.
    They must disagree (agree == False) and give a clear explanation.
    """
    attribution_service = AttributionService()
    logger = sample_loggers[0]
    base_t = sample_handoffs[0].window_start_utc

    # Reading during Handoff 1: 8.1°C at base + 30m (safe range is 2-8°C)
    r_h1 = TemperatureReading(
        reading_id=1,
        logger_id=logger.logger_id,
        recorded_at_utc=base_t + timedelta(minutes=30),
        temperature_c=8.1,
        humidity_pct=None,
        battery_pct=None,
        quality_flag="good",
    )

    # Readings during Handoff 2: 14.0°C at base + 2.5h and base + 3.0h
    r_h2_1 = TemperatureReading(
        reading_id=2,
        logger_id=logger.logger_id,
        recorded_at_utc=base_t + timedelta(hours=2, minutes=30),
        temperature_c=14.0,
        humidity_pct=None,
        battery_pct=None,
        quality_flag="good",
    )
    r_h2_2 = TemperatureReading(
        reading_id=3,
        logger_id=logger.logger_id,
        recorded_at_utc=base_t + timedelta(hours=3, minutes=0),
        temperature_c=14.0,
        humidity_pct=None,
        battery_pct=None,
        quality_flag="good",
    )

    excursion = ExcursionEvent(
        excursion_id=1,
        shipment_id=sample_shipment.shipment_id,
        started_at_utc=base_t + timedelta(minutes=30),
        ended_at_utc=base_t + timedelta(hours=3, minutes=30),
        duration_minutes=180.0,
        peak_temp_c=14.0,
        severity="critical",
        ground_truth_handoff_id=sample_handoffs[1].handoff_id,
        ground_truth_cause="Cooling failure",
    )

    attr_results, naive_res, evidence_list = attribution_service.compute_attribution(
        shipment=sample_shipment,
        product=sample_product,
        excursion=excursion,
        handoffs=sample_handoffs,
        loggers=[logger],
        readings_by_logger={logger.logger_id: [r_h1, r_h2_1, r_h2_2]},
    )

    # Top-ranked by HandoffGuard should be Handoff 2 (handoff_id=102)
    assert len(evidence_list) >= 2
    top_ranked = evidence_list[0]
    assert top_ranked["handoff_id"] == sample_handoffs[1].handoff_id
    assert top_ranked["rank"] == 1

    # Naive baseline should blame Handoff 1 (handoff_id=101)
    assert naive_res.naive_handoff_id == sample_handoffs[0].handoff_id
    assert naive_res.agree is False
    assert len(naive_res.explanation) > 0
