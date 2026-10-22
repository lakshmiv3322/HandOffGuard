"""
AttributionService — ranks handoffs by estimated thermal exposure contribution.

Implements explainable scoring (no black-box ML), naive baseline comparison
(first crossing), and evidence bundle generation.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from app.core.domain.constants import (
    AMBIGUITY_CONFIDENCE_PENALTY_PER_READING,
    CLOCK_SKEW_CONFIDENCE_PENALTY,
    CLOCK_SKEW_PENALTY_THRESHOLD_SECONDS,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LABEL_HIGH,
    CONFIDENCE_LABEL_LOW,
    CONFIDENCE_LABEL_MEDIUM,
    CONFIDENCE_MEDIUM_THRESHOLD,
    COVERAGE_WEIGHT,
    GOOD_QUALITY_FLAGS,
    MAX_AMBIGUITY_PENALTY,
    QUALITY_WEIGHT,
)
from app.core.domain.models import (
    AttributionResult,
    ConfidenceAssessment,
    EvidenceBundle,
    ExcursionEvent,
    Handoff,
    HandoffExposure,
    Logger,
    NaiveBaselineResult,
    Product,
    ReadingWithCorrection,
    Shipment,
    TemperatureReading,
)
from app.core.services.exposure_service import ExposureService, _correct_timestamp


class AttributionService:
    """
    Ranks handoffs by exposure degree-minutes, calculates explainable confidence scores,
    and compares against the naive baseline (first-crossing).
    """

    def __init__(self, exposure_service: Optional[ExposureService] = None) -> None:
        self.exposure_service = exposure_service or ExposureService()

    def compute_attribution(
        self,
        shipment: Shipment,
        product: Product,
        excursion: ExcursionEvent,
        handoffs: list[Handoff],
        loggers: list[Logger],
        readings_by_logger: dict[int, list[TemperatureReading]],
        skew_tolerance_seconds: Optional[int] = None,
    ) -> tuple[list[AttributionResult], NaiveBaselineResult, list[dict]]:
        """
        Compute attribution ranking, naive baseline, and evidence for an excursion.

        Returns:
            (attribution_results, naive_baseline, ranked_evidence_list)
        """
        # 1. Compute exposures across handoffs
        exposures, _, total_shipment_dm = self.exposure_service.compute_handoff_exposures(
            handoffs=handoffs,
            loggers=loggers,
            readings_by_logger=readings_by_logger,
            min_temp_c=product.min_temp_c,
            max_temp_c=product.max_temp_c,
            skew_tolerance_seconds=skew_tolerance_seconds,
        )

        total_excursion_dm = sum(exp.exposure_degree_minutes for exp in exposures)

        # 2. Determine Naive Baseline: handoff during which the threshold was first crossed
        naive_result = self._compute_naive_baseline(
            product=product,
            handoffs=handoffs,
            loggers=loggers,
            readings_by_logger=readings_by_logger,
            skew_tolerance_seconds=skew_tolerance_seconds,
        )

        # Sort exposures by degree-minutes descending
        sorted_exposures = sorted(
            exposures, key=lambda x: x.exposure_degree_minutes, reverse=True
        )

        attribution_results: list[AttributionResult] = []
        ranked_evidence_list: list[dict] = []

        # Find top ranked handoff id (if any exposure > 0)
        top_handoff_id = (
            sorted_exposures[0].handoff.handoff_id
            if sorted_exposures and sorted_exposures[0].exposure_degree_minutes > 0
            else (sorted_exposures[0].handoff.handoff_id if sorted_exposures else None)
        )

        # Update naive_result agreement
        if naive_result.naive_handoff_id is not None and top_handoff_id is not None:
            naive_result.handoffguard_top_handoff_id = top_handoff_id
            naive_result.agree = naive_result.naive_handoff_id == top_handoff_id
            if naive_result.agree:
                naive_result.explanation = (
                    "HandoffGuard agrees with the naive baseline: the handoff where the "
                    "temperature threshold was first crossed also accumulated the highest overall exposure."
                )
            else:
                naive_result.explanation = (
                    f"HandoffGuard identifies handoff #{top_handoff_id} as the top contributor due to total "
                    f"accumulated degree-minutes and duration, whereas the naive baseline strictly attributes "
                    f"to handoff #{naive_result.naive_handoff_id} because the safe limit was initially breached there."
                )
        elif top_handoff_id is not None:
            naive_result.handoffguard_top_handoff_id = top_handoff_id

        rank = 1
        for exp in sorted_exposures:
            handoff = exp.handoff
            exposure_dm = exp.exposure_degree_minutes
            exposure_share_pct = (
                (exposure_dm / total_excursion_dm * 100.0)
                if total_excursion_dm > 0
                else 0.0
            )

            # Allowed excursion time consumed pct
            # Product allowed excursion minutes: product.allowed_excursion_minutes
            # degree-minutes equivalent estimate: allowed_excursion_minutes * 1.0 °C
            allowed_dm_denom = max(1.0, product.allowed_excursion_minutes)
            allowed_consumed_pct = (exposure_dm / allowed_dm_denom) * 100.0

            # Calculate confidence score
            conf = self._calculate_confidence(exp, exposure_share_pct)

            # Calculate duration outside safe range and peak temperature for this handoff
            out_readings = [
                r for r in exp.readings
                if r.reading.temperature_c < product.min_temp_c or r.reading.temperature_c > product.max_temp_c
            ]
            peak_temp = (
                max(r.reading.temperature_c for r in exp.readings)
                if exp.readings
                else None
            )

            # Sampling interval duration estimate for outside safe range
            duration_outside_min = 0.0
            if out_readings:
                duration_outside_min = len(out_readings) * (
                    (loggers[0].sampling_interval_seconds / 60.0) if loggers else 5.0
                )

            used_logger_ids = sorted(list({r.logger.logger_id for r in exp.readings}))
            skew_corrections = [
                lg.clock_skew_seconds for lg in loggers if lg.logger_id in used_logger_ids
            ]

            first_crossing_iso: Optional[str] = None
            for r in exp.readings:
                if r.reading.temperature_c < product.min_temp_c or r.reading.temperature_c > product.max_temp_c:
                    first_crossing_iso = r.corrected_at_utc.isoformat() + "Z"
                    break

            evidence_dict = {
                "rank": rank,
                "handoff_id": handoff.handoff_id,
                "handoff_label": f"{handoff.from_party} → {handoff.to_party} ({handoff.location})",
                "sequence_no": handoff.sequence_no,
                "handoff_type": handoff.handoff_type,
                "from_party": handoff.from_party,
                "to_party": handoff.to_party,
                "location": handoff.location,
                "exposure_degree_minutes": round(exposure_dm, 2),
                "exposure_share_pct": round(exposure_share_pct, 1),
                "allowed_excursion_time_consumed_pct": round(allowed_consumed_pct, 1),
                "confidence_score": round(conf.adjusted_score, 2),
                "confidence_label": conf.label,
                "duration_outside_safe_range_minutes": round(duration_outside_min, 1),
                "peak_temp_c": round(peak_temp, 2) if peak_temp is not None else round(product.max_temp_c, 2),
                "reading_count": exp.reading_count,
                "logger_ids": [str(lid) for lid in used_logger_ids],
                "clock_skew_corrections": skew_corrections,
                "has_missing_gaps": exp.coverage_ratio < 0.8,
                "has_overlapping_windows": exp.ambiguous_reading_count > 0,
                "first_threshold_crossing_utc": first_crossing_iso,
                "evidence_notes": self._build_evidence_notes(exp, conf, handoff),
                "matches_naive_baseline": (
                    naive_result.naive_handoff_id == handoff.handoff_id
                    if naive_result.naive_handoff_id is not None
                    else False
                ),
            }

            ranked_evidence_list.append(evidence_dict)

            attr_row = AttributionResult(
                excursion_id=excursion.excursion_id,
                handoff_id=handoff.handoff_id,
                exposure_degree_minutes=round(exposure_dm, 4),
                exposure_share_pct=round(exposure_share_pct, 4),
                confidence_score=round(conf.adjusted_score, 4),
                confidence_label=conf.label,
                evidence_json=json.dumps(evidence_dict),
            )
            attribution_results.append(attr_row)
            rank += 1

        return attribution_results, naive_result, ranked_evidence_list

    def _calculate_confidence(
        self, exp: HandoffExposure, exposure_share_pct: float
    ) -> ConfidenceAssessment:
        """
        Explainable scoring:
          Base score = normalized exposure share (0.0 to 1.0)
          Adjusted by:
            + coverage ratio * COVERAGE_WEIGHT
            + quality ratio * QUALITY_WEIGHT
            - clock skew penalty if |clock_skew| > 300s
            - ambiguity penalty for overlapping windows
        """
        base_score = min(1.0, max(0.0, exposure_share_pct / 100.0))
        coverage = exp.coverage_ratio
        quality = exp.quality_ratio

        # Skew penalty
        max_skew = max(
            [abs(r.logger.clock_skew_seconds) for r in exp.readings],
            default=0.0,
        )
        skew_penalty_applied = max_skew > CLOCK_SKEW_PENALTY_THRESHOLD_SECONDS
        skew_penalty = CLOCK_SKEW_CONFIDENCE_PENALTY if skew_penalty_applied else 0.0

        # Ambiguity penalty
        ambiguity_penalty = min(
            MAX_AMBIGUITY_PENALTY,
            exp.ambiguous_reading_count * AMBIGUITY_CONFIDENCE_PENALTY_PER_READING,
        )
        ambiguity_penalty_applied = ambiguity_penalty > 0

        # Composite score
        adjusted = (
            base_score * 0.5
            + (coverage * COVERAGE_WEIGHT)
            + (quality * QUALITY_WEIGHT)
            - skew_penalty
            - ambiguity_penalty
        )
        final_score = max(0.05, min(0.99, adjusted))
        label = ConfidenceAssessment.label_for_score(final_score)

        return ConfidenceAssessment(
            raw_score=base_score,
            adjusted_score=final_score,
            label=label,
            coverage_ratio=coverage,
            quality_ratio=quality,
            clock_skew_penalty_applied=skew_penalty_applied,
            ambiguity_penalty_applied=ambiguity_penalty_applied,
        )

    def _compute_naive_baseline(
        self,
        product: Product,
        handoffs: list[Handoff],
        loggers: list[Logger],
        readings_by_logger: dict[int, list[TemperatureReading]],
        skew_tolerance_seconds: Optional[int] = None,
    ) -> NaiveBaselineResult:
        """
        Find the handoff during which the product threshold was first crossed.
        """
        logger_map = {lg.logger_id: lg for lg in loggers}
        tolerance = skew_tolerance_seconds or 120

        # Collect all corrected readings sorted chronologically
        all_readings: list[ReadingWithCorrection] = []
        for logger in loggers:
            for r in readings_by_logger.get(logger.logger_id, []):
                corrected_ts = _correct_timestamp(r, logger)
                all_readings.append(
                    ReadingWithCorrection(
                        reading=r,
                        corrected_at_utc=corrected_ts,
                        logger=logger,
                    )
                )

        all_readings.sort(key=lambda x: x.corrected_at_utc)

        first_excursion_reading: Optional[ReadingWithCorrection] = None
        for r in all_readings:
            if (
                r.reading.temperature_c < product.min_temp_c
                or r.reading.temperature_c > product.max_temp_c
            ):
                first_excursion_reading = r
                break

        if not first_excursion_reading:
            return NaiveBaselineResult(
                naive_handoff_id=None,
                naive_handoff_label="None (no threshold crossing detected)",
                handoffguard_top_handoff_id=None,
                agree=True,
                explanation="No temperature readings exceeded the defined safe boundaries.",
            )

        # Identify which handoff window contains this first crossing
        from datetime import timedelta
        tol = timedelta(seconds=tolerance)
        first_ts = first_excursion_reading.corrected_at_utc
        matched_handoff: Optional[Handoff] = None

        for h in handoffs:
            if (h.window_start_utc - tol) <= first_ts <= (h.window_end_utc + tol):
                matched_handoff = h
                break

        if matched_handoff:
            label = f"{matched_handoff.from_party} → {matched_handoff.to_party} ({matched_handoff.location})"
            return NaiveBaselineResult(
                naive_handoff_id=matched_handoff.handoff_id,
                naive_handoff_label=label,
                handoffguard_top_handoff_id=None,
                agree=False,
                explanation="",
            )

        return NaiveBaselineResult(
            naive_handoff_id=None,
            naive_handoff_label="In-transit gap / unassigned",
            handoffguard_top_handoff_id=None,
            agree=False,
            explanation="The initial temperature excursion occurred during an unassigned transfer window.",
        )

    def _build_evidence_notes(
        self, exp: HandoffExposure, conf: ConfidenceAssessment, handoff: Handoff
    ) -> list[str]:
        notes: list[str] = []
        if exp.exposure_degree_minutes > 0:
            notes.append(
                f"Accumulated {round(exp.exposure_degree_minutes, 1)} °C·min of thermal exposure."
            )
        else:
            notes.append("No thermal excursion observed during this custody period.")

        if exp.reading_count > 0:
            notes.append(
                f"Observed {exp.reading_count} logger temperature readings (data coverage: {int(conf.coverage_ratio * 100)}%)."
            )

        if conf.clock_skew_penalty_applied:
            notes.append(
                "Clock skew uncertainty penalty applied (>300s skew on logger)."
            )

        if conf.ambiguity_penalty_applied:
            notes.append(
                f"{exp.ambiguous_reading_count} reading(s) fell into overlapping handoff windows and were split proportionally."
            )

        if handoff.dwell_minutes > 30:
            notes.append(
                f"Extended dwell time of {int(handoff.dwell_minutes)} minutes recorded at {handoff.location}."
            )

        return notes
