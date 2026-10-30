"""
Abstract repository interfaces.

Each interface defines the contract that both the dev (SQLite/Postgres) and
production (Exasol) implementations must satisfy. Services depend only on
these abstractions, never on concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from app.core.domain.models import (
    AttributionResult,
    ExcursionEvent,
    Handoff,
    Logger,
    PreventionSuggestion,
    Product,
    Shipment,
    TemperatureReading,
)


class AbstractProductRepository(ABC):
    """Repository for product catalogue access."""

    @abstractmethod
    async def get_all(self) -> list[Product]:
        """Return all products."""
        ...

    @abstractmethod
    async def get_by_id(self, product_id: str | int) -> Optional[Product]:
        """Return a product by primary key, or None if not found."""
        ...


class AbstractShipmentRepository(ABC):
    """Repository for shipment data."""

    @abstractmethod
    async def get_all(
        self,
        status: Optional[str] = None,
        has_excursion: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Shipment], int]:
        """
        Return a paginated list of shipments with the total count.

        Filters:
          status       — filter by shipment.status
          has_excursion — True: only shipments with ≥1 excursion event
          search       — case-insensitive substring in shipment_code, origin, destination
        """
        ...

    @abstractmethod
    async def get_by_id(self, shipment_id: str | int) -> Optional[Shipment]:
        """Return a shipment by primary key (with product joined), or None."""
        ...

    @abstractmethod
    async def get_upcoming(self) -> list[Shipment]:
        """Return shipments with status='in_transit', ordered by expected_delivery_at."""
        ...


class AbstractHandoffRepository(ABC):
    """Repository for custody handoff data."""

    @abstractmethod
    async def get_by_shipment(self, shipment_id: int) -> list[Handoff]:
        """Return all handoffs for a shipment, ordered by sequence_no."""
        ...

    @abstractmethod
    async def get_by_id(self, handoff_id: int) -> Optional[Handoff]:
        """Return a handoff by primary key, or None."""
        ...


class AbstractLoggerRepository(ABC):
    """Repository for temperature logger metadata."""

    @abstractmethod
    async def get_by_shipment(self, shipment_id: int) -> list[Logger]:
        """Return all loggers assigned to a shipment."""
        ...

    @abstractmethod
    async def get_by_id(self, logger_id: int) -> Optional[Logger]:
        """Return a logger by primary key, or None."""
        ...


class AbstractReadingRepository(ABC):
    """Repository for temperature readings."""

    @abstractmethod
    async def get_by_logger(
        self,
        logger_id: int,
        start_utc: Optional[datetime] = None,
        end_utc: Optional[datetime] = None,
    ) -> list[TemperatureReading]:
        """
        Return readings for a logger, optionally filtered by time window.
        Results are ordered by recorded_at_utc ascending.
        """
        ...

    @abstractmethod
    async def get_by_shipment(self, shipment_id: int) -> list[TemperatureReading]:
        """Return all readings for all loggers on a shipment, ordered by recorded_at_utc."""
        ...


class AbstractExcursionRepository(ABC):
    """Repository for excursion event data."""

    @abstractmethod
    async def get_by_shipment(self, shipment_id: int) -> list[ExcursionEvent]:
        """Return all excursion events for a shipment."""
        ...

    @abstractmethod
    async def get_by_id(self, excursion_id: int) -> Optional[ExcursionEvent]:
        """Return an excursion event by primary key, or None."""
        ...


class AbstractAttributionRepository(ABC):
    """Repository for attribution results and prevention suggestions."""

    @abstractmethod
    async def get_by_excursion(self, excursion_id: int) -> list[AttributionResult]:
        """Return all attribution rows for an excursion, ordered by exposure_share_pct desc."""
        ...

    @abstractmethod
    async def upsert_results(self, results: list[AttributionResult]) -> None:
        """Persist (insert or replace) a list of attribution results."""
        ...

    @abstractmethod
    async def get_prevention_by_shipment(
        self, shipment_id: int
    ) -> list[PreventionSuggestion]:
        """Return prevention suggestions for a shipment."""
        ...

    @abstractmethod
    async def upsert_prevention(self, suggestions: list[PreventionSuggestion]) -> None:
        """Persist (insert or replace) prevention suggestions."""
        ...
