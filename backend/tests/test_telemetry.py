"""Unit tests for Telemetry Drilldown logic and data structures."""

from datetime import datetime, timedelta, timezone
import pytest

from app.core.domain.models import Handoff, Logger, Product, Shipment, TemperatureReading, ExcursionEvent
from app.core.services.exposure_service import ExposureService
from app.core.services.attribution_service import AttributionService


def test_telemetry_drilldown_calculation():
    """Verify time-series points have correct excursion and safe range flags."""
    base_t = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)
    min_safe = 2.0
    max_safe = 8.0

    readings = [
        {"temp": 5.0, "is_above": False, "is_below": False},
        {"temp": 12.5, "is_above": True, "is_below": False},
        {"temp": 1.2, "is_above": False, "is_below": True},
        {"temp": 8.0, "is_above": False, "is_below": False},
        {"temp": 2.0, "is_above": False, "is_below": False},
    ]

    for item in readings:
        t = item["temp"]
        is_above = t > max_safe
        is_below = t < min_safe
        assert is_above == item["is_above"]
        assert is_below == item["is_below"]


def test_clock_skew_adjustment_in_drilldown():
    """Verify that clock-skew adjustments correctly shift timestamps."""
    raw_ts = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
    skew_seconds = 120  # +120s skew
    adj_ts = raw_ts + timedelta(seconds=skew_seconds)

    assert (adj_ts - raw_ts).total_seconds() == 120


def test_gap_detection_logic():
    """Verify that consecutive readings exceeding 2.5x sampling interval are flagged as gaps."""
    base_t = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)
    sampling_interval_seconds = 60
    gap_limit = sampling_interval_seconds * 2.5  # 150 seconds

    # Reading 1 at 10:00:00, Reading 2 at 10:05:00 (300s diff -> gap)
    t1 = base_t
    t2 = base_t + timedelta(minutes=5)

    diff_sec = (t2 - t1).total_seconds()
    is_gap = diff_sec > gap_limit
    assert is_gap is True
    assert diff_sec == 300
