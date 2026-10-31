"""
TimelineService — constructs the comprehensive shipment custody timeline.

Assembles product safe band, ordered handoffs, logger coverage, downsampled
temperature readings, excursion intervals, clock skew corrections, and data gap intervals.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app.core.domain.constants import GOOD_QUALITY_FLAGS, MAX_CHART_POINTS_PER_LOGGER
from app.core.domain.models import (
    ExcursionEvent,
    Handoff,
    Logger,
    Product,
    Shipment,
    TemperatureReading,
)
from app.core.services.exposure_service import ExposureService, _correct_timestamp


class TimelineService:
    """Service to prepare custody timeline payload for visualization."""

    def __init__(self, exposure_service: Optional[ExposureService] = None) -> None:
        self.exposure_service = exposure_service or ExposureService()

    def build_timeline(
        self,
        shipment: Shipment,
        product: Product,
        handoffs: list[Handoff],
        loggers: list[Logger],
        readings_by_logger: dict[int, list[TemperatureReading]],
        excursions: list[ExcursionEvent],
        suspected_handoff_id: Optional[str | int] = None,
        max_points_per_logger: int = MAX_CHART_POINTS_PER_LOGGER,
    ) -> dict:
        """
        Assemble the complete timeline response structure.
        """
        all_readings_flat: list[TemperatureReading] = []
        for lg_readings in readings_by_logger.values():
            all_readings_flat.extend(lg_readings)

        # 1. Downsample readings per logger for UI performance
        downsampled_readings: list[TemperatureReading] = []
        for logger in loggers:
            raw_readings = readings_by_logger.get(logger.logger_id, [])
            if not raw_readings:
                continue
            if len(raw_readings) <= max_points_per_logger:
                downsampled_readings.extend(raw_readings)
            else:
                step = len(raw_readings) / max_points_per_logger
                sampled = [
                    raw_readings[int(i * step)]
                    for i in range(max_points_per_logger)
                ]
                # Ensure the last reading is included
                if raw_readings[-1] not in sampled:
                    sampled[-1] = raw_readings[-1]
                downsampled_readings.extend(sampled)

        # Sort all sampled readings chronologically
        downsampled_readings.sort(key=lambda r: r.recorded_at_utc)

        # 2. Data quality summary
        total_readings = len(all_readings_flat)
        good_readings = sum(
            1 for r in all_readings_flat if r.quality_flag in GOOD_QUALITY_FLAGS
        )
        flagged_readings = total_readings - good_readings
        loggers_with_skew = sum(1 for lg in loggers if abs(lg.clock_skew_seconds) > 0)

        # 3. Detect missing-reading gaps (> 3 * sampling interval)
        missing_gaps_count = 0
        unassigned_intervals: list[dict] = []

        for logger in loggers:
            lg_readings = sorted(
                readings_by_logger.get(logger.logger_id, []),
                key=lambda r: r.recorded_at_utc,
            )
            interval_sec = max(60, logger.sampling_interval_seconds)
            gap_threshold = timedelta(seconds=interval_sec * 2.5)

            for i in range(1, len(lg_readings)):
                prev_time = lg_readings[i - 1].recorded_at_utc
                curr_time = lg_readings[i].recorded_at_utc
                if (curr_time - prev_time) > gap_threshold:
                    missing_gaps_count += 1
                    unassigned_intervals.append({
                        "start_utc": prev_time.isoformat() + "Z",
                        "end_utc": curr_time.isoformat() + "Z",
                    })

        # 4. Clock-skew corrections list
        clock_skew_corrections = [
            {
                "logger_id": str(lg.logger_id),
                "skew_seconds": int(lg.clock_skew_seconds),
            }
            for lg in loggers
        ]

        # 5. Fallback suspected handoff if not provided: ground truth or highest severity
        if suspected_handoff_id is None and excursions:
            # Check ground truth
            for ex in excursions:
                if ex.ground_truth_handoff_id:
                    suspected_handoff_id = ex.ground_truth_handoff_id
                    break

        return {
            "shipment": shipment,
            "product": product,
            "handoffs": handoffs,
            "loggers": loggers,
            "readings": downsampled_readings,
            "excursion_intervals": excursions,
            "suspected_handoff_id": suspected_handoff_id,
            "data_quality_summary": {
                "total_readings": total_readings,
                "good_readings": good_readings,
                "flagged_readings": flagged_readings,
                "missing_gaps": missing_gaps_count,
                "loggers_with_skew": loggers_with_skew,
            },
            "clock_skew_corrections": clock_skew_corrections,
            "unassigned_intervals": unassigned_intervals,
        }
