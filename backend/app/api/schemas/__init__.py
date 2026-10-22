"""API schemas package."""

from app.api.schemas.common import ErrorResponse, PaginatedResponse
from app.api.schemas.shipment import ProductResponse, ShipmentDetail, ShipmentListItem
from app.api.schemas.handoff import HandoffResponse
from app.api.schemas.logger import LoggerResponse
from app.api.schemas.reading import TemperatureReadingResponse
from app.api.schemas.excursion import ExcursionResponse
from app.api.schemas.attribution import (
    AttributionHandoffItem,
    AttributionResponse,
    AttributionSummaryItem,
    NaiveBaselineComparison,
)
from app.api.schemas.timeline import (
    ClockSkewCorrection,
    CustodyTimelineResponse,
    DataQualitySummary,
    UnassignedIntervalResponse,
)
from app.api.schemas.prevention import PreventionResponse, PreventionSuggestionResponse

__all__ = [
    "ErrorResponse",
    "PaginatedResponse",
    "ProductResponse",
    "ShipmentDetail",
    "ShipmentListItem",
    "HandoffResponse",
    "LoggerResponse",
    "TemperatureReadingResponse",
    "ExcursionResponse",
    "AttributionHandoffItem",
    "AttributionResponse",
    "AttributionSummaryItem",
    "NaiveBaselineComparison",
    "ClockSkewCorrection",
    "CustodyTimelineResponse",
    "DataQualitySummary",
    "UnassignedIntervalResponse",
    "PreventionResponse",
    "PreventionSuggestionResponse",
]
