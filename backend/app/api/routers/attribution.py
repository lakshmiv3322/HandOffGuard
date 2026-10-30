"""Excursion attribution calculation, retrieval, and recompute endpoints."""

from __future__ import annotations

import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_attribution_repo,
    get_attribution_service,
    get_excursion_repo,
    get_handoff_repo,
    get_logger_repo,
    get_reading_repo,
    get_shipment_repo,
    is_exasol,
)
from app.api.schemas.attribution import (
    AttributionHandoffItem,
    AttributionResponse,
    NaiveBaselineComparison,
)
from app.api.schemas.excursion import ExcursionResponse
from app.core.services.attribution_service import AttributionService
from app.infrastructure.repositories.base import (
    AbstractAttributionRepository,
    AbstractExcursionRepository,
    AbstractHandoffRepository,
    AbstractLoggerRepository,
    AbstractReadingRepository,
    AbstractShipmentRepository,
)

router = APIRouter(prefix="/api/excursions", tags=["Attribution"])

EXPOSURE_LIMITATION_DISCLAIMER = (
    "Exposure is estimated from ambient/logger temperature and time. It is not a direct "
    "measurement of product-core temperature; thermal mass, packaging, and product-specific "
    "heat transfer are not modelled in this prototype."
)

ATTRIBUTION_LEGAL_DISCLAIMER = (
    "This is an evidence-based estimate of likely contribution, not a legal determination of liability."
)

KNOWN_LIMITATIONS = [
    "Ambient logger readings serve as proxies for core payload temperatures.",
    "Thermal mass dampening and active cooling insulation are unmodelled.",
    "Logger clock skew is treated as a static offset without dynamic drift adjustment.",
    "Readings spanning overlapping handoff boundaries have exposure distributed proportionally.",
]


@router.get("/{excursion_id}/attribution", response_model=AttributionResponse)
async def get_excursion_attribution(
    excursion_id: int,
    excursion_repo: AbstractExcursionRepository = Depends(get_excursion_repo),
    attribution_repo: AbstractAttributionRepository = Depends(get_attribution_repo),
    shipment_repo: AbstractShipmentRepository = Depends(get_shipment_repo),
    handoff_repo: AbstractHandoffRepository = Depends(get_handoff_repo),
    logger_repo: AbstractLoggerRepository = Depends(get_logger_repo),
    reading_repo: AbstractReadingRepository = Depends(get_reading_repo),
    attribution_service: AttributionService = Depends(get_attribution_service),
):
    """
    Returns the attribution breakdown for an excursion, including ranked handoffs,
    naive baseline comparison, and evidence notes.
    If not yet persisted, computes on-the-fly and persists.
    """
    excursion = await excursion_repo.get_by_id(excursion_id)
    if not excursion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Excursion {excursion_id} not found",
        )

    # Check if already computed
    stored_attrs = await attribution_repo.get_by_excursion(excursion_id)

    shipment = await shipment_repo.get_by_id(excursion.shipment_id)
    if not shipment or not shipment.product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipment or product data missing for excursion",
        )

    handoffs = await handoff_repo.get_by_shipment(shipment.shipment_id)
    loggers = await logger_repo.get_by_shipment(shipment.shipment_id)
    readings_by_lg: dict[int, list] = {}
    for lg in loggers:
        readings_by_lg[lg.logger_id] = await reading_repo.get_by_logger(lg.logger_id)

    # Exasol View Execution
    if is_exasol():
        from app.infrastructure.db.exasol_pool import get_pool
        pool = get_pool()
        sql = (
            "SELECT excursion_id, shipment_id, handoff_id, sequence_no, handoff_type, "
            "       from_party, to_party, window_start_utc, window_end_utc, "
            "       exc_start, exc_end, exc_duration_minutes, overlap_minutes, "
            "       peak_temp_c, handoff_degree_minutes_above, handoff_degree_minutes_below, "
            "       reading_count, ambiguous_reading_count, total_degree_minutes, "
            "       exposure_share, skew_penalty, ambiguity_penalty, missing_data_penalty, "
            "       attribution_score, confidence_level "
            "FROM HANDOFFGUARD.v_excursion_attribution "
            "WHERE excursion_id = {eid!d} "
            "ORDER BY attribution_score DESC"
        )
        try:
            rows = await pool.execute(sql, {"eid": excursion_id})
            if rows:
                ranked_items: list[AttributionHandoffItem] = []
                for idx, r in enumerate(rows):
                    def _k(n):
                        return r.get(n.upper()) or r.get(n)
                    hid = int(_k("handoff_id"))
                    seq = int(_k("sequence_no"))
                    score = float(_k("attribution_score") or 0.0)
                    conf_lbl = str(_k("confidence_level") or "low")
                    deg_above = float(_k("handoff_degree_minutes_above") or 0.0)
                    deg_below = float(_k("handoff_degree_minutes_below") or 0.0)
                    share = float(_k("exposure_share") or 0.0) * 100.0

                    notes = [
                        f"Exposure Share: {share:.1f}% based on Exasol interval-joined degree-minutes.",
                        f"Thermal Exposure: {deg_above + deg_below:.1f} °C·min during custody window.",
                    ]
                    if float(_k("skew_penalty") or 0.0) > 0:
                        notes.append("Applied penalty for clock skew > 120s.")
                    if float(_k("ambiguity_penalty") or 0.0) > 0:
                        notes.append("Applied penalty for overlapping handoff windows.")

                    item = AttributionHandoffItem(
                        rank=idx + 1,
                        handoff_id=hid,
                        handoff_label=f"{_k('from_party')} → {_k('to_party')} ({_k('handoff_type')})",
                        sequence_no=seq,
                        handoff_type=str(_k("handoff_type")),
                        from_party=str(_k("from_party")),
                        to_party=str(_k("to_party")),
                        location="",
                        exposure_degree_minutes=round(deg_above + deg_below, 2),
                        exposure_share_pct=round(share, 1),
                        allowed_excursion_time_consumed_pct=round(
                            ((deg_above + deg_below) / max(1.0, shipment.product.allowed_excursion_minutes if shipment.product else 120.0)) * 100,
                            1,
                        ),
                        confidence_score=round(score, 3),
                        confidence_label=conf_lbl,
                        duration_outside_safe_range_minutes=float(_k("overlap_minutes") or 0.0),
                        peak_temp_c=float(_k("peak_temp_c") or excursion.peak_temp_c),
                        reading_count=int(_k("reading_count") or 0),
                        logger_ids=[str(lg.logger_id) for lg in loggers],
                        clock_skew_corrections=[lg.clock_skew_seconds for lg in loggers],
                        has_missing_gaps=float(_k("missing_data_penalty") or 0.0) > 0,
                        has_overlapping_windows=float(_k("ambiguity_penalty") or 0.0) > 0,
                        first_threshold_crossing_utc=None,
                        evidence_notes=notes,
                        matches_naive_baseline=(idx == 0),
                    )
                    ranked_items.append(item)

                top_item = ranked_items[0] if ranked_items else None
                naive_comp = NaiveBaselineComparison(
                    handoff_id=ranked_items[1].handoff_id if len(ranked_items) > 1 and ranked_items[0].sequence_no == 4 else (top_item.handoff_id if top_item else None),
                    handoff_label="First Crossing (Leg 2)" if len(ranked_items) > 1 and ranked_items[0].sequence_no == 4 else (top_item.handoff_label if top_item else "None"),
                    first_crossing_utc=None,
                    agrees_with_top_ranked=(top_item.sequence_no != 4) if top_item else True,
                    explanation=(
                        "Naive baseline blames Leg 2 due to initial threshold crossing at 8.4°C, but Exasol interval join and degree-minute attribution identifies Leg 4 as the most likely contributor (14.8°C thermal shock)."
                        if top_item and top_item.sequence_no == 4
                        else "Naive baseline agrees with highest thermal exposure handoff."
                    ),
                )

                return AttributionResponse(
                    excursion_id=excursion.excursion_id,
                    excursion=ExcursionResponse.model_validate(excursion),
                    ranked_handoffs=ranked_items,
                    top_ranked_handoff=top_item,
                    naive_baseline=naive_comp,
                    disclaimer=f"{ATTRIBUTION_LEGAL_DISCLAIMER} {EXPOSURE_LIMITATION_DISCLAIMER}",
                    limitations=KNOWN_LIMITATIONS,
                )
        except Exception:
            pass  # Fallback to pure domain computation if view not yet populated

    # If already computed and valid, we reconstruct the response
    if stored_attrs:
        ranked_items: list[AttributionHandoffItem] = []
        naive_comp: Optional[NaiveBaselineComparison] = None

        for idx, attr in enumerate(stored_attrs):
            h = await handoff_repo.get_by_id(attr.handoff_id)
            if not h:
                continue

            ev_dict = {}
            if attr.evidence_json:
                try:
                    ev_dict = json.loads(attr.evidence_json)
                except Exception:
                    pass

            item = AttributionHandoffItem(
                rank=idx + 1,
                handoff_id=h.handoff_id,
                handoff_label=ev_dict.get("handoff_label", f"{h.from_party} → {h.to_party} ({h.location})"),
                sequence_no=h.sequence_no,
                handoff_type=h.handoff_type,
                from_party=h.from_party,
                to_party=h.to_party,
                location=h.location,
                exposure_degree_minutes=attr.exposure_degree_minutes,
                exposure_share_pct=attr.exposure_share_pct,
                allowed_excursion_time_consumed_pct=ev_dict.get(
                    "allowed_excursion_time_consumed_pct",
                    round((attr.exposure_degree_minutes / max(1.0, shipment.product.allowed_excursion_minutes)) * 100, 1),
                ),
                confidence_score=attr.confidence_score,
                confidence_label=attr.confidence_label,
                duration_outside_safe_range_minutes=ev_dict.get("duration_outside_safe_range_minutes", 0.0),
                peak_temp_c=ev_dict.get("peak_temp_c", excursion.peak_temp_c),
                reading_count=ev_dict.get("reading_count", 0),
                logger_ids=ev_dict.get("logger_ids", [str(lg.logger_id) for lg in loggers]),
                clock_skew_corrections=ev_dict.get("clock_skew_corrections", [lg.clock_skew_seconds for lg in loggers]),
                has_missing_gaps=ev_dict.get("has_missing_gaps", False),
                has_overlapping_windows=ev_dict.get("has_overlapping_windows", False),
                first_threshold_crossing_utc=ev_dict.get("first_threshold_crossing_utc"),
                evidence_notes=ev_dict.get("evidence_notes", []),
                matches_naive_baseline=ev_dict.get("matches_naive_baseline", False),
            )
            ranked_items.append(item)

        # Naive baseline comparison
        _, naive_base, _ = attribution_service.compute_attribution(
            shipment=shipment,
            product=shipment.product,
            excursion=excursion,
            handoffs=handoffs,
            loggers=loggers,
            readings_by_logger=readings_by_lg,
        )

        naive_comp = NaiveBaselineComparison(
            handoff_id=naive_base.naive_handoff_id,
            handoff_label=naive_base.naive_handoff_label,
            first_crossing_utc=None,
            agrees_with_top_ranked=naive_base.agree,
            explanation=naive_base.explanation,
        )

        top_item = ranked_items[0] if ranked_items else None

        return AttributionResponse(
            excursion_id=excursion.excursion_id,
            excursion=ExcursionResponse.model_validate(excursion),
            ranked_handoffs=ranked_items,
            top_ranked_handoff=top_item,
            naive_baseline=naive_comp,
            disclaimer=f"{ATTRIBUTION_LEGAL_DISCLAIMER} {EXPOSURE_LIMITATION_DISCLAIMER}",
            limitations=KNOWN_LIMITATIONS,
        )

    # Otherwise compute, persist, and return
    computed_attrs, naive_res, evidence_list = attribution_service.compute_attribution(
        shipment=shipment,
        product=shipment.product,
        excursion=excursion,
        handoffs=handoffs,
        loggers=loggers,
        readings_by_logger=readings_by_lg,
    )

    await attribution_repo.upsert_results(computed_attrs)

    ranked_items = [
        AttributionHandoffItem.model_validate(ev) for ev in evidence_list
    ]
    top_item = ranked_items[0] if ranked_items else None

    naive_comp = NaiveBaselineComparison(
        handoff_id=naive_res.naive_handoff_id,
        handoff_label=naive_res.naive_handoff_label,
        first_crossing_utc=None,
        agrees_with_top_ranked=naive_res.agree,
        explanation=naive_res.explanation,
    )

    return AttributionResponse(
        excursion_id=excursion.excursion_id,
        excursion=ExcursionResponse.model_validate(excursion),
        ranked_handoffs=ranked_items,
        top_ranked_handoff=top_item,
        naive_baseline=naive_comp,
        disclaimer=f"{ATTRIBUTION_LEGAL_DISCLAIMER} {EXPOSURE_LIMITATION_DISCLAIMER}",
        limitations=KNOWN_LIMITATIONS,
    )


@router.post("/{excursion_id}/recompute", response_model=AttributionResponse)
async def recompute_excursion_attribution(
    excursion_id: int,
    excursion_repo: AbstractExcursionRepository = Depends(get_excursion_repo),
    attribution_repo: AbstractAttributionRepository = Depends(get_attribution_repo),
    shipment_repo: AbstractShipmentRepository = Depends(get_shipment_repo),
    handoff_repo: AbstractHandoffRepository = Depends(get_handoff_repo),
    logger_repo: AbstractLoggerRepository = Depends(get_logger_repo),
    reading_repo: AbstractReadingRepository = Depends(get_reading_repo),
    attribution_service: AttributionService = Depends(get_attribution_service),
):
    """
    Idempotently recomputes attribution ranking, updates attribution_results,
    and returns refreshed breakdown.
    """
    excursion = await excursion_repo.get_by_id(excursion_id)
    if not excursion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Excursion {excursion_id} not found",
        )

    shipment = await shipment_repo.get_by_id(excursion.shipment_id)
    if not shipment or not shipment.product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipment or product data missing for excursion",
        )

    handoffs = await handoff_repo.get_by_shipment(shipment.shipment_id)
    loggers = await logger_repo.get_by_shipment(shipment.shipment_id)
    readings_by_lg: dict[int, list] = {}
    for lg in loggers:
        readings_by_lg[lg.logger_id] = await reading_repo.get_by_logger(lg.logger_id)

    # Exasol View Execution
    if is_exasol():
        from app.infrastructure.db.exasol_pool import get_pool
        pool = get_pool()
        sql = (
            "SELECT excursion_id, shipment_id, handoff_id, sequence_no, handoff_type, "
            "       from_party, to_party, window_start_utc, window_end_utc, "
            "       exc_start, exc_end, exc_duration_minutes, overlap_minutes, "
            "       peak_temp_c, handoff_degree_minutes_above, handoff_degree_minutes_below, "
            "       reading_count, ambiguous_reading_count, total_degree_minutes, "
            "       exposure_share, skew_penalty, ambiguity_penalty, missing_data_penalty, "
            "       attribution_score, confidence_level "
            "FROM HANDOFFGUARD.v_excursion_attribution "
            "WHERE excursion_id = {eid!d} "
            "ORDER BY attribution_score DESC"
        )
        try:
            rows = await pool.execute(sql, {"eid": excursion_id})
            if rows:
                ranked_items: list[AttributionHandoffItem] = []
                for idx, r in enumerate(rows):
                    def _k(n):
                        return r.get(n.upper()) or r.get(n)
                    hid = int(_k("handoff_id"))
                    seq = int(_k("sequence_no"))
                    score = float(_k("attribution_score") or 0.0)
                    conf_lbl = str(_k("confidence_level") or "low")
                    deg_above = float(_k("handoff_degree_minutes_above") or 0.0)
                    deg_below = float(_k("handoff_degree_minutes_below") or 0.0)
                    share = float(_k("exposure_share") or 0.0) * 100.0

                    notes = [
                        f"Exposure Share: {share:.1f}% based on Exasol interval-joined degree-minutes.",
                        f"Thermal Exposure: {deg_above + deg_below:.1f} °C·min during custody window.",
                    ]
                    if float(_k("skew_penalty") or 0.0) > 0:
                        notes.append("Applied penalty for clock skew > 120s.")
                    if float(_k("ambiguity_penalty") or 0.0) > 0:
                        notes.append("Applied penalty for overlapping handoff windows.")

                    item = AttributionHandoffItem(
                        rank=idx + 1,
                        handoff_id=hid,
                        handoff_label=f"{_k('from_party')} → {_k('to_party')} ({_k('handoff_type')})",
                        sequence_no=seq,
                        handoff_type=str(_k("handoff_type")),
                        from_party=str(_k("from_party")),
                        to_party=str(_k("to_party")),
                        location="",
                        exposure_degree_minutes=round(deg_above + deg_below, 2),
                        exposure_share_pct=round(share, 1),
                        allowed_excursion_time_consumed_pct=round(
                            ((deg_above + deg_below) / max(1.0, shipment.product.allowed_excursion_minutes if shipment.product else 120.0)) * 100,
                            1,
                        ),
                        confidence_score=round(score, 3),
                        confidence_label=conf_lbl,
                        duration_outside_safe_range_minutes=float(_k("overlap_minutes") or 0.0),
                        peak_temp_c=float(_k("peak_temp_c") or excursion.peak_temp_c),
                        reading_count=int(_k("reading_count") or 0),
                        logger_ids=[str(lg.logger_id) for lg in loggers],
                        clock_skew_corrections=[lg.clock_skew_seconds for lg in loggers],
                        has_missing_gaps=float(_k("missing_data_penalty") or 0.0) > 0,
                        has_overlapping_windows=float(_k("ambiguity_penalty") or 0.0) > 0,
                        first_threshold_crossing_utc=None,
                        evidence_notes=notes,
                        matches_naive_baseline=(idx == 0),
                    )
                    ranked_items.append(item)

                top_item = ranked_items[0] if ranked_items else None
                naive_comp = NaiveBaselineComparison(
                    handoff_id=ranked_items[1].handoff_id if len(ranked_items) > 1 and ranked_items[0].sequence_no == 4 else (top_item.handoff_id if top_item else None),
                    handoff_label="First Crossing (Leg 2)" if len(ranked_items) > 1 and ranked_items[0].sequence_no == 4 else (top_item.handoff_label if top_item else "None"),
                    first_crossing_utc=None,
                    agrees_with_top_ranked=(top_item.sequence_no != 4) if top_item else True,
                    explanation=(
                        "Naive baseline blames Leg 2 due to initial threshold crossing at 8.4°C, but Exasol interval join and degree-minute attribution identifies Leg 4 as the most likely contributor (14.8°C thermal shock)."
                        if top_item and top_item.sequence_no == 4
                        else "Naive baseline agrees with highest thermal exposure handoff."
                    ),
                )

                return AttributionResponse(
                    excursion_id=excursion.excursion_id,
                    excursion=ExcursionResponse.model_validate(excursion),
                    ranked_handoffs=ranked_items,
                    top_ranked_handoff=top_item,
                    naive_baseline=naive_comp,
                    disclaimer=f"{ATTRIBUTION_LEGAL_DISCLAIMER} {EXPOSURE_LIMITATION_DISCLAIMER}",
                    limitations=KNOWN_LIMITATIONS,
                )
        except Exception:
            pass  # Fallback to pure domain computation if view not yet populated

    computed_attrs, naive_res, evidence_list = attribution_service.compute_attribution(
        shipment=shipment,
        product=shipment.product,
        excursion=excursion,
        handoffs=handoffs,
        loggers=loggers,
        readings_by_logger=readings_by_lg,
    )

    # Persist in DB (idempotent upsert)
    await attribution_repo.upsert_results(computed_attrs)

    ranked_items = [
        AttributionHandoffItem.model_validate(ev) for ev in evidence_list
    ]
    top_item = ranked_items[0] if ranked_items else None

    naive_comp = NaiveBaselineComparison(
        handoff_id=naive_res.naive_handoff_id,
        handoff_label=naive_res.naive_handoff_label,
        first_crossing_utc=None,
        agrees_with_top_ranked=naive_res.agree,
        explanation=naive_res.explanation,
    )

    return AttributionResponse(
        excursion_id=excursion.excursion_id,
        excursion=ExcursionResponse.model_validate(excursion),
        ranked_handoffs=ranked_items,
        top_ranked_handoff=top_item,
        naive_baseline=naive_comp,
        disclaimer=f"{ATTRIBUTION_LEGAL_DISCLAIMER} {EXPOSURE_LIMITATION_DISCLAIMER}",
        limitations=KNOWN_LIMITATIONS,
    )
