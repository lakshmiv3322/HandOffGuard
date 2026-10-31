"""Excursion attribution calculation, retrieval, and recompute endpoints."""

from __future__ import annotations

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
    "Exposure is estimated from logger observations and stated modelling assumptions (default 600s gap limit). "
    "Not a determination of product-core temperature, root cause or legal liability. Product disposition remains with the quality team."
)

ATTRIBUTION_LEGAL_DISCLAIMER = (
    "Investigation aid only. Associated custody segments are identified for diagnostic review, not legal fault assignment."
)

KNOWN_LIMITATIONS = [
    "Ambient logger readings serve as proxies for core payload temperatures.",
    "Thermal mass dampening and active cooling insulation are unmodelled.",
    "Clock skew is corrected statically; dynamic clock drift is unmodelled.",
    "Supported segments limited to maximum 600-second gap (engineering prototype default).",
    "Overlapping custody windows are conservatively excluded from single-party attributable exposure.",
    "Shipments with multiple analytical loggers require primary-logger selection.",
]


@router.get("/{excursion_id}/attribution", response_model=AttributionResponse)
async def get_excursion_attribution(
    excursion_id: str,
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
    naive baseline comparison, evidence notes, and coverage status.
    Source of truth: Exasol V_EXCURSION_ATTRIBUTION view.
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

    # Exasol View Execution — Source of Truth
    if is_exasol():
        from app.infrastructure.db.exasol_pool import get_pool
        pool = get_pool()
        sql = (
            "SELECT excursion_id, shipment_id, handoff_id, sequence_no, handoff_type, "
            "       associated_party, to_party, location, window_source, "
            "       window_start_utc, window_end_utc, exc_start, exc_end, "
            "       exc_duration_minutes, exc_peak_temp_c, assigned_logger_count, "
            "       reading_count, supported_observation_minutes, ambiguous_minutes, "
            "       handoff_degree_minutes_above, handoff_degree_minutes_below, "
            "       handoff_total_dm, total_excursion_dm, total_supported_obs_min, "
            "       exposure_share, attribution_rank, evidence_status, disclaimer "
            "FROM HANDOFFGUARD.v_excursion_attribution "
            "WHERE excursion_id = {eid} "
            "ORDER BY attribution_rank ASC, sequence_no ASC"
        )
        rows = await pool.execute(sql, {"eid": str(excursion_id)})
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No attribution records found in Exasol for excursion {excursion_id}",
            )

        ranked_items: list[AttributionHandoffItem] = []
        for idx, r in enumerate(rows):
            def _k(n: str):
                return r.get(n.upper()) or r.get(n)

            hid = _k("handoff_id")
            seq = int(_k("sequence_no") or 0)
            assoc_party = str(_k("associated_party") or "Unknown")
            to_party = str(_k("to_party") or "Unknown")
            htype = str(_k("handoff_type") or "Transit")
            ev_status = str(_k("evidence_status") or "INCONCLUSIVE_INSUFFICIENT_DATA")
            tot_dm = float(_k("handoff_total_dm") or 0.0)
            share_pct = round(float(_k("exposure_share") or 0.0) * 100.0, 1)
            supported_obs = float(_k("supported_observation_minutes") or 0.0)
            ambiguous_min = float(_k("ambiguous_minutes") or 0.0)
            assigned_loggers = int(_k("assigned_logger_count") or 0)
            win_source = str(_k("window_source") or "ACTUAL")

            # Confidence score and label based on evidence status
            if ev_status == "Unvalidated prototype ranking":
                conf_score = 0.85
                conf_label = "Prototype Ranking"
            elif ev_status == "INCONCLUSIVE_INSUFFICIENT_DATA":
                conf_score = 0.10
                conf_label = "Inconclusive (Data Gap)"
            elif ev_status == "INCONCLUSIVE_MULTI_LOGGER":
                conf_score = 0.20
                conf_label = "Inconclusive (Multi-Logger)"
            elif ev_status == "EXCLUDED_PLANNED_ONLY":
                conf_score = 0.0
                conf_label = "Excluded (Planned Only)"
            else:
                conf_score = 0.50
                conf_label = ev_status

            notes = [
                f"Evidence status: {ev_status}.",
                f"Exposure share: {share_pct}% ({tot_dm:.1f} °C·min) restricted to excursion window.",
                f"Supported observation: {supported_obs:.1f} min | Ambiguous: {ambiguous_min:.1f} min.",
            ]
            if win_source == "PLANNED_ONLY":
                notes.append("Custody window lacks actual timestamps. Excluded from actual custody attribution.")
            if assigned_loggers > 1:
                notes.append(f"Warning: {assigned_loggers} loggers assigned. Single-logger MVP rule active.")
            if ev_status == "INCONCLUSIVE_INSUFFICIENT_DATA":
                notes.append("Warning: Sparse data or gaps > 600s. Zero exposure does not prove thermal safety.")
            if ambiguous_min > 0:
                notes.append(f"Excluded {ambiguous_min:.1f} min of ambiguous overlapping custody.")

            item = AttributionHandoffItem(
                rank=idx + 1,
                handoff_id=hid,
                handoff_label=f"{assoc_party} → {to_party} ({htype})",
                sequence_no=seq,
                handoff_type=htype,
                from_party=assoc_party,
                to_party=to_party,
                location=str(_k("location") or ""),
                exposure_degree_minutes=tot_dm,
                exposure_share_pct=share_pct,
                allowed_excursion_time_consumed_pct=round(
                    (tot_dm / max(1.0, shipment.product.allowed_excursion_minutes if shipment.product else 120.0)) * 100.0,
                    1,
                ),
                confidence_score=conf_score,
                confidence_label=conf_label,
                duration_outside_safe_range_minutes=supported_obs,
                peak_temp_c=float(_k("exc_peak_temp_c") or excursion.peak_temp_c),
                reading_count=int(_k("reading_count") or 0),
                logger_ids=[str(lg.logger_id) for lg in loggers],
                clock_skew_corrections=[lg.clock_skew_seconds for lg in loggers],
                has_missing_gaps=(ev_status == "INCONCLUSIVE_INSUFFICIENT_DATA"),
                has_overlapping_windows=(ambiguous_min > 0),
                first_threshold_crossing_utc=None,
                evidence_notes=notes,
                matches_naive_baseline=False,
            )
            ranked_items.append(item)

        top_item = ranked_items[0] if ranked_items else None

        # Determine naive baseline (first handoff whose window contains excursion start)
        first_crossing_handoff = None
        for h in handoffs:
            if h.window_start_utc <= excursion.started_at_utc < h.window_end_utc:
                first_crossing_handoff = h
                break

        agrees = False
        if top_item and first_crossing_handoff:
            agrees = str(top_item.handoff_id) == str(first_crossing_handoff.handoff_id)

        naive_comp = NaiveBaselineComparison(
            handoff_id=first_crossing_handoff.handoff_id if first_crossing_handoff else None,
            handoff_label=(
                f"{first_crossing_handoff.from_party} → {first_crossing_handoff.to_party} ({first_crossing_handoff.handoff_type})"
                if first_crossing_handoff else "Unknown"
            ),
            first_crossing_utc=excursion.started_at_utc.isoformat() if excursion.started_at_utc else None,
            agrees_with_top_ranked=agrees,
            explanation=(
                f"Naive baseline attributes to initial threshold crossing at {excursion.started_at_utc}. "
                + (
                    "Exasol degree-minute attribution agrees with first-crossing custody."
                    if agrees else
                    f"However, cumulative degree-minute attribution identifies {top_item.handoff_label if top_item else 'another leg'} as primary contributor."
                )
            ),
        )

        if top_item and agrees:
            top_item.matches_naive_baseline = True

        return AttributionResponse(
            excursion_id=excursion.excursion_id,
            excursion=ExcursionResponse.model_validate(excursion),
            ranked_handoffs=ranked_items,
            top_ranked_handoff=top_item,
            naive_baseline=naive_comp,
            disclaimer=f"{ATTRIBUTION_LEGAL_DISCLAIMER} {EXPOSURE_LIMITATION_DISCLAIMER}",
            limitations=KNOWN_LIMITATIONS,
        )

    # Dev / SQLite fallback (when not Exasol)
    readings_by_lg: dict[int, list] = {}
    for lg in loggers:
        readings_by_lg[lg.logger_id] = await reading_repo.get_by_logger(lg.logger_id)

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
    excursion_id: str,
    excursion_repo: AbstractExcursionRepository = Depends(get_excursion_repo),
    attribution_repo: AbstractAttributionRepository = Depends(get_attribution_repo),
    shipment_repo: AbstractShipmentRepository = Depends(get_shipment_repo),
    handoff_repo: AbstractHandoffRepository = Depends(get_handoff_repo),
    logger_repo: AbstractLoggerRepository = Depends(get_logger_repo),
    reading_repo: AbstractReadingRepository = Depends(get_reading_repo),
    attribution_service: AttributionService = Depends(get_attribution_service),
):
    """
    Idempotently recomputes attribution ranking against the database views.
    """
    return await get_excursion_attribution(
        excursion_id=excursion_id,
        excursion_repo=excursion_repo,
        attribution_repo=attribution_repo,
        shipment_repo=shipment_repo,
        handoff_repo=handoff_repo,
        logger_repo=logger_repo,
        reading_repo=reading_repo,
        attribution_service=attribution_service,
    )
