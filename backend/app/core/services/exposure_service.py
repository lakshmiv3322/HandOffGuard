"""
ExposureService — degree-minute calculation engine.

Computes how much thermal exposure (degree-minutes above/below the safe range)
each temperature reading contributes, then aggregates that exposure per handoff
by assigning readings to handoffs via corrected-timestamp interval overlap.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app.core.domain.constants import (
    CLOCK_SKEW_PENALTY_THRESHOLD_SECONDS,
    GOOD_QUALITY_FLAGS,
    QUALITY_FLAG_GOOD,
    UNASSIGNED_LABEL,
)
from app.core.domain.models import (
    Handoff,
    HandoffExposure,
    Logger,
    ReadingWithCorrection,
    TemperatureReading,
    UnassignedInterval,
)
from app.config import settings


def _correct_timestamp(
    reading: TemperatureReading, logger: Logger
) -> datetime:
    """Apply logger clock-skew correction to a raw reading timestamp."""
    return reading.recorded_at_utc + timedelta(seconds=logger.clock_skew_seconds)


def _nearest_safe_limit_distance(temperature_c: float, min_temp_c: float, max_temp_c: float) -> float:
    """
    Return the absolute distance from the nearest safe temperature limit.

    If temperature is within [min_temp_c, max_temp_c] the distance is 0.
    """
    if temperature_c < min_temp_c:
        return min_temp_c - temperature_c
    if temperature_c > max_temp_c:
        return temperature_c - max_temp_c
    return 0.0


def _is_in_excursion(temperature_c: float, min_temp_c: float, max_temp_c: float) -> bool:
    """Return True if the temperature is outside the safe range."""
    return temperature_c < min_temp_c or temperature_c > max_temp_c


def _assign_reading_to_handoffs(
    corrected_reading: ReadingWithCorrection,
    handoffs: list[Handoff],
    skew_tolerance_seconds: int,
) -> list[Handoff]:
    """
    Return the handoffs whose window contains the corrected reading timestamp.

    A handoff window is expanded by ±skew_tolerance_seconds to account for
    residual clock uncertainty after correction.

    Returns an empty list if no handoff matches (reading is in a gap).
    Returns multiple handoffs if windows overlap (ambiguous assignment).
    """
    tolerance = timedelta(seconds=skew_tolerance_seconds)
    corrected_at = corrected_reading.corrected_at_utc
    matched: list[Handoff] = []
    for handoff in handoffs:
        window_start = handoff.window_start_utc - tolerance
        window_end = handoff.window_end_utc + tolerance
        if window_start <= corrected_at <= window_end:
            matched.append(handoff)
    return matched


class ExposureService:
    """
    Calculates degree-minute exposure for each handoff within a shipment.

    The algorithm:
    1. Correct all reading timestamps for logger clock skew.
    2. For each pair of consecutive corrected readings, compute:
         interval_minutes = delta_time_seconds / 60
         distance_c = |temperature - nearest safe limit|  (0 if in range)
         degree_minutes = distance_c * interval_minutes
    3. Assign each reading to the handoff(s) whose window covers its corrected
       timestamp. Readings in no handoff window are "unassigned".
    4. If a reading falls in multiple overlapping handoff windows, split its
       exposure proportionally to the overlap duration each handoff has with
       the reading's interval.
    5. Aggregate degree-minutes per handoff.
    """

    def compute_handoff_exposures(
        self,
        handoffs: list[Handoff],
        loggers: list[Logger],
        readings_by_logger: dict[int, list[TemperatureReading]],
        min_temp_c: float,
        max_temp_c: float,
        skew_tolerance_seconds: Optional[int] = None,
    ) -> tuple[list[HandoffExposure], list[UnassignedInterval], float]:
        """
        Compute per-handoff exposure aggregates for a shipment.

        Parameters
        ----------
        handoffs:
            All handoffs for the shipment, in sequence order.
        loggers:
            All loggers assigned to the shipment.
        readings_by_logger:
            Mapping from logger_id to its list of TemperatureReadings (sorted by time).
        min_temp_c / max_temp_c:
            Product safe temperature range.
        skew_tolerance_seconds:
            Override the global tolerance; falls back to settings value.

        Returns
        -------
        (handoff_exposures, unassigned_intervals, shipment_total_degree_minutes)
        """
        tolerance = (
            skew_tolerance_seconds
            if skew_tolerance_seconds is not None
            else settings.skew_tolerance_seconds
        )

        # Accumulate per-handoff data
        exposure_map: dict[int, HandoffExposure] = {}
        for handoff in handoffs:
            exposure_map[handoff.handoff_id] = HandoffExposure(
                handoff=handoff,
                exposure_degree_minutes=0.0,
                reading_count=0,
                expected_reading_count=self._estimate_expected_readings(
                    handoff, loggers
                ),
                good_quality_reading_count=0,
                ambiguous_reading_count=0,
                readings=[],
            )

        unassigned_readings: list[ReadingWithCorrection] = []
        shipment_total: float = 0.0

        for logger in loggers:
            raw_readings = readings_by_logger.get(logger.logger_id, [])
            if not raw_readings:
                continue

            corrected_readings = [
                ReadingWithCorrection(
                    reading=r,
                    corrected_at_utc=_correct_timestamp(r, logger),
                    logger=logger,
                )
                for r in raw_readings
            ]

            for index, corrected in enumerate(corrected_readings):
                # Compute interval duration and degree-minutes for this reading
                interval_minutes = self._interval_minutes(
                    corrected, corrected_readings, index, logger
                )
                distance_c = _nearest_safe_limit_distance(
                    corrected.reading.temperature_c, min_temp_c, max_temp_c
                )
                degree_minutes = distance_c * interval_minutes
                shipment_total += degree_minutes

                matched_handoffs = _assign_reading_to_handoffs(
                    corrected, handoffs, tolerance
                )

                if not matched_handoffs:
                    unassigned_readings.append(corrected)
                    continue

                is_ambiguous = len(matched_handoffs) > 1

                if is_ambiguous:
                    # Split exposure proportionally by overlap duration
                    split_dm = self._split_exposure_proportionally(
                        corrected, matched_handoffs, degree_minutes, tolerance
                    )
                else:
                    split_dm = {matched_handoffs[0].handoff_id: degree_minutes}

                for handoff in matched_handoffs:
                    exposure_obj = exposure_map[handoff.handoff_id]
                    exposure_obj.exposure_degree_minutes += split_dm.get(
                        handoff.handoff_id, 0.0
                    )
                    exposure_obj.reading_count += 1
                    if corrected.reading.quality_flag in GOOD_QUALITY_FLAGS:
                        exposure_obj.good_quality_reading_count += 1
                    if is_ambiguous:
                        exposure_obj.ambiguous_reading_count += 1
                    exposure_obj.readings.append(corrected)

        # Build unassigned intervals from gaps
        unassigned_intervals = self._build_unassigned_intervals(
            unassigned_readings, min_temp_c, max_temp_c
        )

        return list(exposure_map.values()), unassigned_intervals, shipment_total

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _interval_minutes(
        self,
        corrected: ReadingWithCorrection,
        all_corrected: list[ReadingWithCorrection],
        index: int,
        logger: Logger,
    ) -> float:
        """
        Compute the time interval (in minutes) this reading represents.

        For the first reading, use logger.sampling_interval_seconds / 60.
        For subsequent readings, use the delta from the previous reading.
        """
        if index == 0:
            return logger.sampling_interval_seconds / 60.0
        previous = all_corrected[index - 1]
        delta_seconds = (
            corrected.corrected_at_utc - previous.corrected_at_utc
        ).total_seconds()
        return delta_seconds / 60.0

    def _estimate_expected_readings(
        self, handoff: Handoff, loggers: list[Logger]
    ) -> int:
        """
        Estimate how many readings we expect in a handoff window based on the
        logger sampling intervals. Uses the minimum sampling interval across
        all loggers (most conservative estimate).
        """
        if not loggers:
            return 0
        window_seconds = (
            handoff.window_end_utc - handoff.window_start_utc
        ).total_seconds()
        min_interval = min(lg.sampling_interval_seconds for lg in loggers)
        if min_interval <= 0:
            return 0
        return max(1, int(window_seconds / min_interval))

    def _split_exposure_proportionally(
        self,
        corrected: ReadingWithCorrection,
        matched_handoffs: list[Handoff],
        total_degree_minutes: float,
        tolerance_seconds: int,
    ) -> dict[int, float]:
        """
        Split degree-minutes exposure among overlapping handoffs proportionally
        to the overlap each window has with the tolerance-expanded boundary.

        If we cannot determine meaningful overlap fractions, split equally.
        """
        tolerance = timedelta(seconds=tolerance_seconds)
        corrected_at = corrected.corrected_at_utc

        overlaps: dict[int, float] = {}
        for handoff in matched_handoffs:
            start = max(handoff.window_start_utc - tolerance, corrected_at - timedelta(minutes=5))
            end = min(handoff.window_end_utc + tolerance, corrected_at + timedelta(minutes=5))
            overlap_seconds = max(0.0, (end - start).total_seconds())
            overlaps[handoff.handoff_id] = overlap_seconds

        total_overlap = sum(overlaps.values())
        if total_overlap == 0:
            # Fallback: split equally
            equal_share = total_degree_minutes / len(matched_handoffs)
            return {h.handoff_id: equal_share for h in matched_handoffs}

        return {
            handoff_id: total_degree_minutes * (overlap / total_overlap)
            for handoff_id, overlap in overlaps.items()
        }

    def _build_unassigned_intervals(
        self,
        unassigned_readings: list[ReadingWithCorrection],
        min_temp_c: float,
        max_temp_c: float,
    ) -> list[UnassignedInterval]:
        """
        Merge consecutive unassigned readings into contiguous intervals.
        """
        if not unassigned_readings:
            return []

        # Sort by corrected timestamp
        sorted_readings = sorted(
            unassigned_readings, key=lambda r: r.corrected_at_utc
        )

        intervals: list[UnassignedInterval] = []
        group_start = sorted_readings[0]
        group_end = sorted_readings[0]
        group_readings = [sorted_readings[0]]
        group_dm = 0.0

        for current in sorted_readings[1:]:
            gap_seconds = (
                current.corrected_at_utc - group_end.corrected_at_utc
            ).total_seconds()

            if gap_seconds <= current.logger.sampling_interval_seconds * 2:
                # Still part of the same gap
                group_end = current
                group_readings.append(current)
                interval_min = gap_seconds / 60.0
                distance_c = _nearest_safe_limit_distance(
                    current.reading.temperature_c, min_temp_c, max_temp_c
                )
                group_dm += distance_c * interval_min
            else:
                intervals.append(
                    UnassignedInterval(
                        label=UNASSIGNED_LABEL,
                        start_utc=group_start.corrected_at_utc,
                        end_utc=group_end.corrected_at_utc,
                        reading_count=len(group_readings),
                        exposure_degree_minutes=group_dm,
                    )
                )
                group_start = current
                group_end = current
                group_readings = [current]
                group_dm = 0.0

        intervals.append(
            UnassignedInterval(
                label=UNASSIGNED_LABEL,
                start_utc=group_start.corrected_at_utc,
                end_utc=group_end.corrected_at_utc,
                reading_count=len(group_readings),
                exposure_degree_minutes=group_dm,
            )
        )
        return intervals
