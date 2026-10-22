"""Prevention prototype endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_handoff_repo,
    get_logger_repo,
    get_prevention_service,
    get_shipment_repo,
)
from app.api.schemas.handoff import HandoffResponse
from app.api.schemas.prevention import PreventionResponse, PreventionSuggestionResponse
from app.api.schemas.shipment import ShipmentListItem
from app.core.services.prevention_service import (
    PROTOTYPE_DISCLAIMER,
    PreventionService,
)
from app.infrastructure.repositories.base import (
    AbstractHandoffRepository,
    AbstractLoggerRepository,
    AbstractShipmentRepository,
)

router = APIRouter(prefix="/api/prevention", tags=["Prevention Prototype"])


@router.get("/upcoming", response_model=PreventionResponse)
async def get_upcoming_prevention(
    shipment_repo: AbstractShipmentRepository = Depends(get_shipment_repo),
    handoff_repo: AbstractHandoffRepository = Depends(get_handoff_repo),
    logger_repo: AbstractLoggerRepository = Depends(get_logger_repo),
    prevention_service: PreventionService = Depends(get_prevention_service),
):
    """
    Returns one upcoming in-transit shipment with risk scoring and rule-based
    prevention recommendations.
    """
    upcoming_shipments = await shipment_repo.get_upcoming()
    if not upcoming_shipments:
        # Fallback to any shipment if no 'in_transit' shipments exist
        shipments, _ = await shipment_repo.get_all(page=1, page_size=1)
        if not shipments:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No shipments available for prevention evaluation",
            )
        target_shipment = shipments[0]
    else:
        target_shipment = upcoming_shipments[0]

    handoffs = await handoff_repo.get_by_shipment(target_shipment.shipment_id)
    loggers = await logger_repo.get_by_shipment(target_shipment.shipment_id)

    prod = target_shipment.product
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipment missing product specifications",
        )

    riskiest_h, suggestion = prevention_service.evaluate_shipment_risk(
        shipment=target_shipment,
        product=prod,
        handoffs=handoffs,
        loggers=loggers,
    )

    shipment_item = ShipmentListItem(
        shipment_id=target_shipment.shipment_id,
        shipment_code=target_shipment.shipment_code,
        product_name=prod.name,
        origin=target_shipment.origin,
        destination=target_shipment.destination,
        dispatched_at=target_shipment.dispatched_at,
        expected_delivery_at=target_shipment.expected_delivery_at,
        status=target_shipment.status,
        has_excursion=False,
        total_exposure_degree_minutes=0.0,
        worst_severity=None,
    )

    return PreventionResponse(
        shipment=shipment_item,
        handoffs=[HandoffResponse.model_validate(h) for h in handoffs],
        riskiest_handoff=HandoffResponse.model_validate(riskiest_h),
        suggestion=PreventionSuggestionResponse.model_validate(suggestion),
        disclaimer=PROTOTYPE_DISCLAIMER,
    )


@router.get("/shipments/{shipment_id}", response_model=PreventionResponse)
async def get_shipment_prevention(
    shipment_id: int,
    shipment_repo: AbstractShipmentRepository = Depends(get_shipment_repo),
    handoff_repo: AbstractHandoffRepository = Depends(get_handoff_repo),
    logger_repo: AbstractLoggerRepository = Depends(get_logger_repo),
    prevention_service: PreventionService = Depends(get_prevention_service),
):
    """
    Returns prevention risk evaluation for a specific shipment.
    """
    shipment = await shipment_repo.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )

    handoffs = await handoff_repo.get_by_shipment(shipment.shipment_id)
    loggers = await logger_repo.get_by_shipment(shipment.shipment_id)

    prod = shipment.product
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipment missing product specifications",
        )

    riskiest_h, suggestion = prevention_service.evaluate_shipment_risk(
        shipment=shipment,
        product=prod,
        handoffs=handoffs,
        loggers=loggers,
    )

    shipment_item = ShipmentListItem(
        shipment_id=shipment.shipment_id,
        shipment_code=shipment.shipment_code,
        product_name=prod.name,
        origin=shipment.origin,
        destination=shipment.destination,
        dispatched_at=shipment.dispatched_at,
        expected_delivery_at=shipment.expected_delivery_at,
        status=shipment.status,
        has_excursion=False,
        total_exposure_degree_minutes=0.0,
        worst_severity=None,
    )

    return PreventionResponse(
        shipment=shipment_item,
        handoffs=[HandoffResponse.model_validate(h) for h in handoffs],
        riskiest_handoff=HandoffResponse.model_validate(riskiest_h),
        suggestion=PreventionSuggestionResponse.model_validate(suggestion),
        disclaimer=PROTOTYPE_DISCLAIMER,
    )
