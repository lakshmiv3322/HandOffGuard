"""Evidence report endpoint for print-friendly document generation."""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_attribution_service,
    get_excursion_repo,
    get_handoff_repo,
    get_logger_repo,
    get_reading_repo,
    get_shipment_repo,
    get_timeline_service,
)
from app.core.services.attribution_service import AttributionService
from app.core.services.timeline_service import TimelineService
from app.infrastructure.repositories.base import (
    AbstractExcursionRepository,
    AbstractHandoffRepository,
    AbstractLoggerRepository,
    AbstractReadingRepository,
    AbstractShipmentRepository,
)

router = APIRouter(prefix="/api/excursions", tags=["Evidence Report"])


@router.get("/{excursion_id}/evidence-report")
async def get_evidence_report(
    excursion_id: int,
    excursion_repo: AbstractExcursionRepository = Depends(get_excursion_repo),
    shipment_repo: AbstractShipmentRepository = Depends(get_shipment_repo),
    handoff_repo: AbstractHandoffRepository = Depends(get_handoff_repo),
    logger_repo: AbstractLoggerRepository = Depends(get_logger_repo),
    reading_repo: AbstractReadingRepository = Depends(get_reading_repo),
    attribution_service: AttributionService = Depends(get_attribution_service),
    timeline_service: TimelineService = Depends(get_timeline_service),
):
    """
    Returns structured JSON for print-friendly HTML report rendering.
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
            detail="Shipment or product record missing",
        )

    handoffs = await handoff_repo.get_by_shipment(shipment.shipment_id)
    loggers = await logger_repo.get_by_shipment(shipment.shipment_id)
    readings_by_lg: dict[int, list] = {}
    for lg in loggers:
        readings_by_lg[lg.logger_id] = await reading_repo.get_by_logger(lg.logger_id)

    # Compute attribution and evidence
    _, naive_res, evidence_list = attribution_service.compute_attribution(
        shipment=shipment,
        product=shipment.product,
        excursion=excursion,
        handoffs=handoffs,
        loggers=loggers,
        readings_by_logger=readings_by_lg,
    )

    timeline_data = timeline_service.build_timeline(
        shipment=shipment,
        product=shipment.product,
        handoffs=handoffs,
        loggers=loggers,
        readings_by_logger=readings_by_lg,
        excursions=[excursion],
    )

    now_utc = datetime.now(timezone.utc).isoformat()

    return {
        "report_title": "Cold-Chain Custody Attribution Report",
        "generated_at": now_utc,
        "shipment_details": {
            "shipment_id": shipment.shipment_id,
            "shipment_code": shipment.shipment_code,
            "origin": shipment.origin,
            "destination": shipment.destination,
            "dispatched_at": shipment.dispatched_at.isoformat() + "Z",
            "expected_delivery_at": shipment.expected_delivery_at.isoformat() + "Z",
            "status": shipment.status,
        },
        "product_details": {
            "name": shipment.product.name,
            "min_temp_c": shipment.product.min_temp_c,
            "max_temp_c": shipment.product.max_temp_c,
            "allowed_excursion_minutes": shipment.product.allowed_excursion_minutes,
            "thermal_mass_class": shipment.product.thermal_mass_class,
        },
        "excursion_details": {
            "excursion_id": excursion.excursion_id,
            "started_at_utc": excursion.started_at_utc.isoformat() + "Z",
            "ended_at_utc": excursion.ended_at_utc.isoformat() + "Z",
            "duration_minutes": excursion.duration_minutes,
            "peak_temp_c": excursion.peak_temp_c,
            "severity": excursion.severity,
            "ground_truth_cause": excursion.ground_truth_cause,
        },
        "custody_timeline_summary": {
            "total_handoffs": len(handoffs),
            "total_loggers": len(loggers),
            "total_readings": timeline_data["data_quality_summary"]["total_readings"],
            "missing_gaps_count": timeline_data["data_quality_summary"]["missing_gaps"],
        },
        "ranked_handoffs": evidence_list,
        "naive_baseline_comparison": {
            "handoff_id": naive_res.naive_handoff_id,
            "handoff_label": naive_res.naive_handoff_label,
            "naive_handoff_id": naive_res.naive_handoff_id,
            "naive_handoff_label": naive_res.naive_handoff_label,
            "agrees_with_top_ranked": naive_res.agree,
            "explanation": naive_res.explanation,
        },
        "data_quality_notes": [
            f"Evaluated {timeline_data['data_quality_summary']['total_readings']} temperature records across {len(loggers)} monitoring device(s).",
            f"Flagged {timeline_data['data_quality_summary']['flagged_readings']} readings for quality/transmission variance.",
            f"Applied static clock-skew adjustments for {timeline_data['data_quality_summary']['loggers_with_skew']} logger(s).",
        ],
        "limitations": [
            "Exposure is estimated from ambient/logger temperature and time. It is not a direct measurement of product-core temperature; thermal mass, packaging, and product-specific heat transfer are not modelled in this prototype.",
            "This prototype assessment provides probabilistic evidence of thermal breach, not a legal or regulatory determination of liability.",
        ],
    }
