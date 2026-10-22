"""Tests for custody timeline construction, downsampling, and data gap detection."""

from datetime import datetime, timedelta
import pytest

from app.core.domain.models import TemperatureReading
from app.core.services.timeline_service import TimelineService


def test_timeline_downsampling(sample_shipment, sample_product, sample_handoffs, sample_loggers):
    """If logger has 1000 readings and max is 100, downsampled list must be <= 100."""
    service = TimelineService()
    logger = sample_loggers[0]
    base_t = sample_handoffs[0].window_start_utc

    # Generate 1000 readings
    readings = [
        TemperatureReading(
            reading_id=i,
            logger_id=logger.logger_id,
            recorded_at_utc=base_t + timedelta(minutes=i),
            temperature_c=4.5,
            humidity_pct=None,
            battery_pct=None,
            quality_flag="good",
        )
        for i in range(1000)
    ]

    timeline_data = service.build_timeline(
        shipment=sample_shipment,
        product=sample_product,
        handoffs=sample_handoffs,
        loggers=[logger],
        readings_by_logger={logger.logger_id: readings},
        excursions=[],
        max_points_per_logger=100,
    )

    assert len(timeline_data["readings"]) <= 100
    assert timeline_data["data_quality_summary"]["total_readings"] == 1000


def test_timeline_gap_detection(sample_shipment, sample_product, sample_handoffs, sample_loggers):
    """A jump of > 2.5 * sampling interval between readings should be flagged as a data gap."""
    service = TimelineService()
    logger = sample_loggers[0]  # interval = 300s (5m)
    base_t = sample_handoffs[0].window_start_utc

    # Reading 1 at 00:00, Reading 2 at 00:30 (gap of 30 mins > 12.5 mins threshold)
    r1 = TemperatureReading(
        reading_id=1,
        logger_id=logger.logger_id,
        recorded_at_utc=base_t,
        temperature_c=4.5,
        humidity_pct=None,
        battery_pct=None,
        quality_flag="good",
    )
    r2 = TemperatureReading(
        reading_id=2,
        logger_id=logger.logger_id,
        recorded_at_utc=base_t + timedelta(minutes=30),
        temperature_c=4.5,
        humidity_pct=None,
        battery_pct=None,
        quality_flag="good",
    )

    timeline_data = service.build_timeline(
        shipment=sample_shipment,
        product=sample_product,
        handoffs=sample_handoffs,
        loggers=[logger],
        readings_by_logger={logger.logger_id: [r1, r2]},
        excursions=[],
    )

    assert timeline_data["data_quality_summary"]["missing_gaps"] >= 1
    assert len(timeline_data["unassigned_intervals"]) >= 1
