"""Prevention prototype schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from app.api.schemas.handoff import HandoffResponse
from app.api.schemas.shipment import ShipmentListItem


class PreventionSuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shipment_id: int
    handoff_id: int
    risk_score: float
    suggestion: str
    rationale: str
    prototype_flag: bool = True


class PreventionResponse(BaseModel):
    shipment: ShipmentListItem
    handoffs: list[HandoffResponse]
    riskiest_handoff: HandoffResponse
    suggestion: PreventionSuggestionResponse
    disclaimer: str
