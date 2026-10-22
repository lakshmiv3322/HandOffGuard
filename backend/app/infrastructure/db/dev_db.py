"""
SQLite / SQLAlchemy development database backend.

Uses async SQLAlchemy with aiosqlite. Suitable for local development and
automated tests. The ORM table definitions mirror the Exasol schema contract
exactly — same column names, same nullable constraints.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import text

from app.infrastructure.db.base import DatabaseBackend


class Base(DeclarativeBase):
    """SQLAlchemy declarative base shared by all ORM models."""


# ---------------------------------------------------------------------------
# ORM table models — column names must match the Exasol schema contract
# ---------------------------------------------------------------------------


class ProductORM(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    min_temp_c = Column(Float, nullable=False)
    max_temp_c = Column(Float, nullable=False)
    allowed_excursion_minutes = Column(Float, nullable=False)
    thermal_mass_class = Column(String(50), nullable=False)

    shipments = relationship("ShipmentORM", back_populates="product")


class ShipmentORM(Base):
    __tablename__ = "shipments"

    shipment_id = Column(Integer, primary_key=True, autoincrement=True)
    shipment_code = Column(String(100), nullable=False, unique=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    origin = Column(String(200), nullable=False)
    destination = Column(String(200), nullable=False)
    dispatched_at = Column(DateTime, nullable=False)
    expected_delivery_at = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False)

    product = relationship("ProductORM", back_populates="shipments")
    handoffs = relationship("HandoffORM", back_populates="shipment")
    loggers = relationship("LoggerORM", back_populates="shipment")
    excursions = relationship("ExcursionEventORM", back_populates="shipment")
    prevention_suggestions = relationship("PreventionSuggestionORM", back_populates="shipment")


class HandoffORM(Base):
    __tablename__ = "handoffs"

    handoff_id = Column(Integer, primary_key=True, autoincrement=True)
    shipment_id = Column(Integer, ForeignKey("shipments.shipment_id"), nullable=False)
    sequence_no = Column(Integer, nullable=False)
    handoff_type = Column(String(50), nullable=False)
    from_party = Column(String(200), nullable=False)
    to_party = Column(String(200), nullable=False)
    location = Column(String(200), nullable=False)
    window_start_utc = Column(DateTime, nullable=False)
    window_end_utc = Column(DateTime, nullable=False)
    reported_start_utc = Column(DateTime, nullable=True)
    reported_end_utc = Column(DateTime, nullable=True)
    clock_skew_seconds = Column(Float, nullable=False, default=0.0)
    dwell_minutes = Column(Float, nullable=False, default=0.0)

    shipment = relationship("ShipmentORM", back_populates="handoffs")
    excursions_ground_truth = relationship(
        "ExcursionEventORM", back_populates="ground_truth_handoff"
    )
    attribution_results = relationship("AttributionResultORM", back_populates="handoff")
    prevention_suggestions = relationship("PreventionSuggestionORM", back_populates="handoff")


class LoggerORM(Base):
    __tablename__ = "loggers"

    logger_id = Column(Integer, primary_key=True, autoincrement=True)
    device_type = Column(String(100), nullable=False)
    assigned_shipment_id = Column(Integer, ForeignKey("shipments.shipment_id"), nullable=False)
    sampling_interval_seconds = Column(Integer, nullable=False)
    clock_skew_seconds = Column(Float, nullable=False, default=0.0)
    data_quality_flag = Column(String(50), nullable=False, default="good")

    shipment = relationship("ShipmentORM", back_populates="loggers")
    readings = relationship("TemperatureReadingORM", back_populates="logger")


class TemperatureReadingORM(Base):
    """
    IMPORTANT: No handoff_id column.
    Reading-to-handoff assignment is done by time-interval overlap in code.
    """

    __tablename__ = "temperature_readings"

    reading_id = Column(Integer, primary_key=True, autoincrement=True)
    logger_id = Column(Integer, ForeignKey("loggers.logger_id"), nullable=False)
    recorded_at_utc = Column(DateTime, nullable=False)
    temperature_c = Column(Float, nullable=False)
    humidity_pct = Column(Float, nullable=True)
    battery_pct = Column(Float, nullable=True)
    quality_flag = Column(String(50), nullable=False, default="good")

    logger = relationship("LoggerORM", back_populates="readings")


class ExcursionEventORM(Base):
    __tablename__ = "excursion_events"

    excursion_id = Column(Integer, primary_key=True, autoincrement=True)
    shipment_id = Column(Integer, ForeignKey("shipments.shipment_id"), nullable=False)
    started_at_utc = Column(DateTime, nullable=False)
    ended_at_utc = Column(DateTime, nullable=False)
    duration_minutes = Column(Float, nullable=False)
    peak_temp_c = Column(Float, nullable=False)
    severity = Column(String(50), nullable=False)
    ground_truth_handoff_id = Column(
        Integer, ForeignKey("handoffs.handoff_id"), nullable=True
    )
    ground_truth_cause = Column(String(500), nullable=True)

    shipment = relationship("ShipmentORM", back_populates="excursions")
    ground_truth_handoff = relationship(
        "HandoffORM", back_populates="excursions_ground_truth"
    )
    attribution_results = relationship(
        "AttributionResultORM", back_populates="excursion"
    )


class AttributionResultORM(Base):
    __tablename__ = "attribution_results"

    excursion_id = Column(
        Integer, ForeignKey("excursion_events.excursion_id"), primary_key=True
    )
    handoff_id = Column(
        Integer, ForeignKey("handoffs.handoff_id"), primary_key=True
    )
    exposure_degree_minutes = Column(Float, nullable=False)
    exposure_share_pct = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    confidence_label = Column(String(50), nullable=False)
    evidence_json = Column(Text, nullable=False)

    excursion = relationship("ExcursionEventORM", back_populates="attribution_results")
    handoff = relationship("HandoffORM", back_populates="attribution_results")


class PreventionSuggestionORM(Base):
    __tablename__ = "prevention_suggestions"

    shipment_id = Column(
        Integer, ForeignKey("shipments.shipment_id"), primary_key=True
    )
    handoff_id = Column(
        Integer, ForeignKey("handoffs.handoff_id"), primary_key=True
    )
    risk_score = Column(Float, nullable=False)
    suggestion = Column(String(1000), nullable=False)
    rationale = Column(String(1000), nullable=False)
    prototype_flag = Column(Boolean, nullable=False, default=True)

    shipment = relationship("ShipmentORM", back_populates="prevention_suggestions")
    handoff = relationship("HandoffORM", back_populates="prevention_suggestions")


# ---------------------------------------------------------------------------
# Backend implementation
# ---------------------------------------------------------------------------


class DevDatabaseBackend(DatabaseBackend):
    """
    Async SQLAlchemy backend backed by SQLite (dev/test) or PostgreSQL.

    Pass any SQLAlchemy async-compatible URL. For SQLite use
    ``sqlite+aiosqlite:///path/to/db.db``; for PostgreSQL use
    ``postgresql+asyncpg://user:pass@host/db``.
    """

    def __init__(self, db_url: str) -> None:
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        self._engine = create_async_engine(
            db_url,
            echo=False,
            connect_args=connect_args,
        )
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:  # type: ignore[override]
        """Yield a transactional async session."""
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def health_check(self) -> dict:
        """Ping the database and return health status."""
        try:
            async with self._session_factory() as session:
                await session.execute(text("SELECT 1"))
            engine_name = "sqlite" if "sqlite" in str(self._engine.url) else "postgres"
            return {"db_status": "ok", "db_engine": engine_name, "detail": "Connected"}
        except Exception as exc:
            return {
                "db_status": "error",
                "db_engine": "unknown",
                "detail": str(exc),
            }

    async def create_tables(self) -> None:
        """Create all ORM-mapped tables (idempotent DDL)."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
