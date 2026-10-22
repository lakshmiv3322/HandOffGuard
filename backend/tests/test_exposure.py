"""Tests for degree-minute calculations, exposure share, and interval overlap assignment."""

from datetime import datetime, timedelta
import pytest

from app.core.domain.models import Handoff, Logger, TemperatureReading
from app.core.services.exposure_service import ExposureService, _correct_timestamp


def test_clock_skew_correction():
    """Corrected timestamp = raw timestamp + clock_skew_seconds."""
    raw_time = datetime(2026, 10, 20, 10, 0, 0)
    logger = Logger(
        logger_id=1,
        device_type="Probe",
        assigned_shipment_id=1,
        sampling_interval_seconds=300,
        clock_skew_seconds=120,  # 2 minutes ahead
        data_quality_flag="good",
    )
    reading = TemperatureReading(
        reading_id=10,
        logger_id=1,
        recorded_at_utc=raw_time,
        temperature_c=9.5,
        humidity_pct=None,
        battery_pct=None,
        quality_flag="good",
    )
    corrected = _correct_timestamp(reading, logger)
    assert corrected == raw_time + timedelta(seconds=120)


def test_degree_minute_calculation(sample_product, sample_handoffs, sample_loggers):
    """
    Verify distance_from_safe_limit * minutes_since_previous_reading.
    Safe limit: 2°C to 8°C.
    Temperature: 11.0°C (distance = 3.0°C)
    Interval: 5 minutes (sampling_interval)
    Degree-minutes = 3.0 * 5.0 = 15.0 °C·min
    """
    service = ExposureService()
    logger = sample_loggers[0]
    base_t = sample_handoffs[0].window_start_utc

    # First reading: uses sampling_interval_seconds / 60 = 5.0 min
    r1 = TemperatureReading(
        reading_id=1,
        logger_id=logger.logger_id,
        recorded_at_utc=base_t + timedelta(minutes=10),
        temperature_c=11.0,
        humidity_pct=None,
        battery_pct=None,
        quality_flag="good",
    )
    # Second reading 5 minutes later, still 11.0°C
    r2 = TemperatureReading(
        reading_id=2,
        logger_id=logger.logger_id,
        recorded_at_utc=base_t + timedelta(minutes=15),
        temperature_c=11.0,
        humidity_pct=None,
        battery_pct=None,
        quality_flag="good",
    )

    exposures, unassigned, total_dm = service.compute_handoff_exposures(
        handoffs=[sample_handoffs[0]],
        loggers=[logger],
        readings_by_logger={logger.logger_id: [r1, r2]},
        min_temp_c=sample_product.min_temp_c,
        max_temp_c=sample_product.max_temp_c,
    )

    # 3.0°C delta * 5 min = 15.0 per reading -> total = 30.0 °C·min
    assert total_dm == pytest.approx(30.0)
    assert exposures[0].exposure_degree_minutes == pytest.approx(30.0)
    assert exposures[0].reading_count == 2


def test_overlapping_handoff_windows(sample_product, sample_handoffs, sample_loggers):
    """
    Readings falling into overlapping windows must not double-count exposure.
    H1 is [08:00 to 10:00], H2 is [09:50 to 13:00].
    At 09:55, reading overlaps both H1 and H2.
    """
    service = ExposureService()
    logger = sample_loggers[0]
    base_t = sample_handoffs[0].window_start_utc

    # Reading at 09:55 (1 hr 55 min after base)
    r = TemperatureReading(
        reading_id=1,
        logger_id=logger.logger_id,
        recorded_at_utc=base_t + timedelta(hours=1, minutes=55),
        temperature_c=10.0,  # 2°C outside safe max of 8°C
        humidity_pct=None,
        battery_pct=None,
        quality_flag="good",
    )

    exposures, _, total_dm = service.compute_handoff_exposures(
        handoffs=sample_handoffs,
        loggers=[logger],
        readings_by_logger={logger.logger_id: [r]},
        min_temp_c=sample_product.min_temp_c,
        max_temp_c=sample_product.max_temp_c,
    )

    # 2°C delta * 5 min = 10.0 °C·min total
    assert total_dm == pytest.approx(10.0)

    # Sum of exposures in handoffs must equal total_dm (no double-counting)
    assigned_sum = sum(exp.exposure_degree_minutes for exp in exposures)
    assert assigned_sum == pytest.approx(total_dm)


def test_unassigned_transit_gap(sample_product, sample_handoffs, sample_loggers):
    """
    Readings falling in a gap between handoff windows must be classified as unassigned.
    H2 ends at 13:00 (base + 5h), H3 starts at 14:00 (base + 6h).
    At 13:30 (base + 5.5h), reading is in an unassigned gap.
    """
    service = ExposureService()
    logger = sample_loggers[0]
    base_t = sample_handoffs[0].window_start_utc

    r = TemperatureReading(
        reading_id=1,
        logger_id=logger.logger_id,
        recorded_at_utc=base_t + timedelta(hours=5, minutes=30),
        temperature_c=12.0,
        humidity_pct=None,
        battery_pct=None,
        quality_flag="good",
    )

    exposures, unassigned, total_dm = service.compute_handoff_exposures(
        handoffs=sample_handoffs,
        loggers=[logger],
        readings_by_logger={logger.logger_id: [r]},
        min_temp_c=sample_product.min_temp_c,
        max_temp_c=sample_product.max_temp_c,
    )

    assert len(unassigned) > 0
    assert unassigned[0].reading_count == 1
    # Handoffs have 0 exposure
    for exp in exposures:
        assert exp.exposure_degree_minutes == 0.0
