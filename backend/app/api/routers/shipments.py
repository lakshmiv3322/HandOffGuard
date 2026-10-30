"""Shipment management, custody timeline, and summary endpoints."""

from __future__ import annotations

import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_attribution_repo,
    get_attribution_service,
    get_excursion_repo,
    get_exposure_service,
    get_handoff_repo,
    get_logger_repo,
    get_product_repo,
    get_reading_repo,
    get_shipment_repo,
    get_timeline_service,
)
from app.api.schemas.attribution import AttributionSummaryItem
from app.api.schemas.common import PaginatedResponse
from app.api.schemas.excursion import ExcursionResponse
from app.api.schemas.handoff import HandoffResponse
from app.api.schemas.logger import LoggerResponse
from app.api.schemas.shipment import ProductResponse, ShipmentDetail, ShipmentListItem
from app.api.schemas.timeline import CustodyTimelineResponse
from app.core.services.attribution_service import AttributionService
from app.core.services.exposure_service import ExposureService
from app.core.services.timeline_service import TimelineService
from app.infrastructure.repositories.base import (
    AbstractAttributionRepository,
    AbstractExcursionRepository,
    AbstractHandoffRepository,
    AbstractLoggerRepository,
    AbstractProductRepository,
    AbstractReadingRepository,
    AbstractShipmentRepository,
)

router = APIRouter(prefix="/api/shipments", tags=["Shipments"])


@router.get("", response_model=PaginatedResponse[ShipmentListItem])
async def list_shipments(
    status_filter: Optional[str] = Query(None, alias="status"),
    has_excursion: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    shipment_repo: AbstractShipmentRepository = Depends(get_shipment_repo),
    excursion_repo: AbstractExcursionRepository = Depends(get_excursion_repo),
    reading_repo: AbstractReadingRepository = Depends(get_reading_repo),
    logger_repo: AbstractLoggerRepository = Depends(get_logger_repo),
    exposure_service: ExposureService = Depends(get_exposure_service),
):
    """
    Returns a paginated list of shipments with excursion flags, total exposure degree-minutes,
    and worst severity.
    """
    shipments, total = await shipment_repo.get_all(
        status=status_filter,
        has_excursion=has_excursion,
        search=search,
        page=page,
        page_size=page_size,
    )

    items: list[ShipmentListItem] = []
    for s in shipments:
        excursions = await excursion_repo.get_by_shipment(s.shipment_id)
        has_exc = len(excursions) > 0

        # Worst severity
        worst_sev: Optional[str] = None
        severity_order = {"critical": 4, "severe": 3, "high": 3, "moderate": 2, "medium": 2, "minor": 1, "low": 1}
        for ex in excursions:
            sev_norm = ex.severity.lower()
            if worst_sev is None or severity_order.get(sev_norm, 0) > severity_order.get(worst_sev.lower(), 0):
                worst_sev = ex.severity

        # Compute total exposure degree-minutes if product and readings exist
        total_dm = 0.0
        if s.product:
            loggers = await logger_repo.get_by_shipment(s.shipment_id)
            readings_by_lg = {}
            for lg in loggers:
                readings_by_lg[lg.logger_id] = await reading_repo.get_by_logger(lg.logger_id)

            # Quick degree-minute sum
            for lg in loggers:
                raw_r = readings_by_lg.get(lg.logger_id, [])
                for i, r in enumerate(raw_r):
                    if r.temperature_c < s.product.min_temp_c:
                        dist = s.product.min_temp_c - r.temperature_c
                    elif r.temperature_c > s.product.max_temp_c:
                        dist = r.temperature_c - s.product.max_temp_c
                    else:
                        continue
                    interval_min = (
                        (lg.sampling_interval_seconds / 60.0)
                        if i == 0
                        else max(0.0, (r.recorded_at_utc - raw_r[i - 1].recorded_at_utc).total_seconds() / 60.0)
                    )
                    total_dm += dist * interval_min

        items.append(
            ShipmentListItem(
                id=s.shipment_id,
                shipment_id=s.shipment_id,
                shipment_code=s.shipment_code,
                product_name=s.product.name if s.product else "Standard Pharmaceutical",
                origin=s.origin,
                destination=s.destination,
                dispatched_at=s.dispatched_at,
                expected_delivery_at=s.expected_delivery_at,
                status=s.status,
                has_excursion=has_exc,
                total_exposure_degree_minutes=round(total_dm, 2),
                worst_severity=worst_sev,
            )
        )

    return PaginatedResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{shipment_id}", response_model=ShipmentDetail)
async def get_shipment_detail(
    shipment_id: str,
    shipment_repo: AbstractShipmentRepository = Depends(get_shipment_repo),
    handoff_repo: AbstractHandoffRepository = Depends(get_handoff_repo),
    logger_repo: AbstractLoggerRepository = Depends(get_logger_repo),
    excursion_repo: AbstractExcursionRepository = Depends(get_excursion_repo),
    attribution_repo: AbstractAttributionRepository = Depends(get_attribution_repo),
):
    """
    Returns shipment summary, product limits, logger summary, handoff count,
    excursion summary, and attribution status.
    """
    shipment = await shipment_repo.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )

    handoffs = await handoff_repo.get_by_shipment(shipment_id)
    loggers = await logger_repo.get_by_shipment(shipment_id)
    excursions = await excursion_repo.get_by_shipment(shipment_id)

    # Attribution status
    attribution_status = "none"
    if excursions:
        # Check if first excursion has attribution results
        attrs = await attribution_repo.get_by_excursion(excursions[0].excursion_id)
        attribution_status = "computed" if attrs else "pending"

    prod_res = (
        ProductResponse.model_validate(shipment.product)
        if shipment.product
        else ProductResponse(
            product_id="0",
            name="General Biologic",
            min_temp_c=2.0,
            max_temp_c=8.0,
            allowed_excursion_minutes=120.0,
            thermal_mass_class="Medium",
        )
    )

    return ShipmentDetail(
        id=shipment.shipment_id,
        shipment_id=shipment.shipment_id,
        shipment_code=shipment.shipment_code,
        product=prod_res,
        origin=shipment.origin,
        destination=shipment.destination,
        dispatched_at=shipment.dispatched_at,
        expected_delivery_at=shipment.expected_delivery_at,
        status=shipment.status,
        handoff_count=len(handoffs),
        logger_count=len(loggers),
        excursion_count=len(excursions),
        has_excursion=len(excursions) > 0,
        attribution_status=attribution_status,
    )


@router.get("/{shipment_id}/custody-timeline", response_model=CustodyTimelineResponse)
async def get_custody_timeline(
    shipment_id: str,
    shipment_repo: AbstractShipmentRepository = Depends(get_shipment_repo),
    handoff_repo: AbstractHandoffRepository = Depends(get_handoff_repo),
    logger_repo: AbstractLoggerRepository = Depends(get_logger_repo),
    reading_repo: AbstractReadingRepository = Depends(get_reading_repo),
    excursion_repo: AbstractExcursionRepository = Depends(get_excursion_repo),
    attribution_repo: AbstractAttributionRepository = Depends(get_attribution_repo),
    timeline_service: TimelineService = Depends(get_timeline_service),
):
    """
    Returns the comprehensive custody timeline payload with product safe band,
    handoffs in sequence order, downsampled temperature readings, excursion shading,
    and suspected handoff ID.
    """
    shipment = await shipment_repo.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )

    handoffs = await handoff_repo.get_by_shipment(shipment_id)
    loggers = await logger_repo.get_by_shipment(shipment_id)
    excursions = await excursion_repo.get_by_shipment(shipment_id)

    readings_by_lg: dict[int, list] = {}
    for lg in loggers:
        readings_by_lg[lg.logger_id] = await reading_repo.get_by_logger(lg.logger_id)

    suspected_id: Optional[int] = None
    if excursions:
        attrs = await attribution_repo.get_by_excursion(excursions[0].excursion_id)
        if attrs:
            suspected_id = attrs[0].handoff_id
        elif excursions[0].ground_truth_handoff_id:
            suspected_id = excursions[0].ground_truth_handoff_id

    prod = shipment.product
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipment does not have associated product limits",
        )

    timeline_data = timeline_service.build_timeline(
        shipment=shipment,
        product=prod,
        handoffs=handoffs,
        loggers=loggers,
        readings_by_logger=readings_by_lg,
        excursions=excursions,
        suspected_handoff_id=suspected_id,
    )

    detail_obj = ShipmentDetail(
        shipment_id=shipment.shipment_id,
        shipment_code=shipment.shipment_code,
        product=ProductResponse.model_validate(prod),
        origin=shipment.origin,
        destination=shipment.destination,
        dispatched_at=shipment.dispatched_at,
        expected_delivery_at=shipment.expected_delivery_at,
        status=shipment.status,
        handoff_count=len(handoffs),
        logger_count=len(loggers),
        excursion_count=len(excursions),
        has_excursion=len(excursions) > 0,
        attribution_status="computed" if suspected_id else "pending",
    )

    return CustodyTimelineResponse(
        shipment=detail_obj,
        product=ProductResponse.model_validate(prod),
        handoffs=[HandoffResponse.model_validate(h) for h in timeline_data["handoffs"]],
        loggers=[LoggerResponse.model_validate(lg) for lg in timeline_data["loggers"]],
        readings=timeline_data["readings"],
        excursion_intervals=[
            ExcursionResponse.model_validate(ex) for ex in timeline_data["excursion_intervals"]
        ],
        suspected_handoff_id=timeline_data["suspected_handoff_id"],
        data_quality_summary=timeline_data["data_quality_summary"],
        clock_skew_corrections=timeline_data["clock_skew_corrections"],
        unassigned_intervals=timeline_data["unassigned_intervals"],
    )


@router.get("/{shipment_id}/handoffs", response_model=list[HandoffResponse])
async def list_shipment_handoffs(
    shipment_id: str,
    handoff_repo: AbstractHandoffRepository = Depends(get_handoff_repo),
):
    """Returns handoffs for a shipment ordered by sequence_no."""
    handoffs = await handoff_repo.get_by_shipment(shipment_id)
    return [HandoffResponse.model_validate(h) for h in handoffs]


@router.get("/{shipment_id}/attribution-summary", response_model=list[AttributionSummaryItem])
async def get_shipment_attribution_summary(
    shipment_id: str,
    excursion_repo: AbstractExcursionRepository = Depends(get_excursion_repo),
    attribution_repo: AbstractAttributionRepository = Depends(get_attribution_repo),
    handoff_repo: AbstractHandoffRepository = Depends(get_handoff_repo),
):
    """Returns the latest attribution summary for each excursion on the shipment."""
    excursions = await excursion_repo.get_by_shipment(shipment_id)
    summary_items: list[AttributionSummaryItem] = []

    for ex in excursions:
        attrs = await attribution_repo.get_by_excursion(ex.excursion_id)
        if not attrs:
            summary_items.append(
                AttributionSummaryItem(
                    excursion_id=ex.excursion_id,
                    severity=ex.severity,
                    duration_minutes=ex.duration_minutes,
                    peak_temp_c=ex.peak_temp_c,
                    top_handoff_id=None,
                    top_handoff_label="Attribution pending",
                    top_exposure_share_pct=0.0,
                    confidence_label="Pending",
                    naive_agrees=False,
                )
            )
            continue

        top_attr = attrs[0]
        h = await handoff_repo.get_by_id(top_attr.handoff_id)
        label = f"{h.from_party} → {h.to_party} ({h.location})" if h else f"Handoff #{top_attr.handoff_id}"

        # Parse evidence_json if available
        naive_agrees = False
        if top_attr.evidence_json:
            try:
                ev = json.loads(top_attr.evidence_json)
                naive_agrees = ev.get("matches_naive_baseline", False)
            except Exception:
                pass

        summary_items.append(
            AttributionSummaryItem(
                excursion_id=ex.excursion_id,
                severity=ex.severity,
                duration_minutes=ex.duration_minutes,
                peak_temp_c=ex.peak_temp_c,
                top_handoff_id=top_attr.handoff_id,
                top_handoff_label=label,
                top_exposure_share_pct=top_attr.exposure_share_pct,
                confidence_label=top_attr.confidence_label,
                naive_agrees=naive_agrees,
            )
        )

    return summary_items
