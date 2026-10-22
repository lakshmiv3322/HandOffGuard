"""Pytest fixtures for HandoffGuard backend tests."""

from datetime import datetime, timedelta, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.domain.models import Handoff, Logger, Product, Shipment, TemperatureReading
from app.main import app


@pytest.fixture
def sample_product() -> Product:
    return Product(
        product_id=1,
        name="Vaccine Alpha (2-8°C)",
        min_temp_c=2.0,
        max_temp_c=8.0,
        allowed_excursion_minutes=120.0,
        thermal_mass_class="Low",
    )


@pytest.fixture
def sample_shipment(sample_product: Product) -> Shipment:
    base_t = datetime(2026, 10, 20, 8, 0, 0)
    return Shipment(
        shipment_id=1,
        shipment_code="SHP-TEST-001",
        product_id=sample_product.product_id,
        origin="Origin Plant",
        destination="Destination Hospital",
        dispatched_at=base_t,
        expected_delivery_at=base_t + timedelta(hours=8),
        status="delivered",
        product=sample_product,
    )


@pytest.fixture
def sample_handoffs(sample_shipment: Shipment) -> list[Handoff]:
    base_t = sample_shipment.dispatched_at
    h1 = Handoff(
        handoff_id=101,
        shipment_id=sample_shipment.shipment_id,
        sequence_no=1,
        handoff_type="pickup",
        from_party="Plant Warehouse",
        to_party="Carrier A",
        location="Dock 1",
        window_start_utc=base_t,
        window_end_utc=base_t + timedelta(hours=2),
        reported_start_utc=None,
        reported_end_utc=None,
        clock_skew_seconds=0,
        dwell_minutes=15,
    )
    # H2 overlaps with H1 by 10 minutes
    h2 = Handoff(
        handoff_id=102,
        shipment_id=sample_shipment.shipment_id,
        sequence_no=2,
        handoff_type="transit",
        from_party="Carrier A",
        to_party="Transit Hub",
        location="Cross-dock",
        window_start_utc=base_t + timedelta(hours=1, minutes=50),
        window_end_utc=base_t + timedelta(hours=5),
        reported_start_utc=None,
        reported_end_utc=None,
        clock_skew_seconds=0,
        dwell_minutes=0,
    )
    # H3 has a gap after H2 (starts at hour 6, gap between 5 and 6)
    h3 = Handoff(
        handoff_id=103,
        shipment_id=sample_shipment.shipment_id,
        sequence_no=3,
        handoff_type="delivery",
        from_party="Transit Hub",
        to_party="Clinic",
        location="Hospital Ward",
        window_start_utc=base_t + timedelta(hours=6),
        window_end_utc=base_t + timedelta(hours=8),
        reported_start_utc=None,
        reported_end_utc=None,
        clock_skew_seconds=0,
        dwell_minutes=10,
    )
    return [h1, h2, h3]


@pytest.fixture
def sample_loggers(sample_shipment: Shipment) -> list[Logger]:
    return [
        Logger(
            logger_id=1,
            device_type="Probe A",
            assigned_shipment_id=sample_shipment.shipment_id,
            sampling_interval_seconds=300,
            clock_skew_seconds=0,
            data_quality_flag="good",
        ),
        Logger(
            logger_id=2,
            device_type="Probe B (Skewed)",
            assigned_shipment_id=sample_shipment.shipment_id,
            sampling_interval_seconds=300,
            clock_skew_seconds=360,  # 6 min clock skew
            data_quality_flag="good",
        ),
    ]


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
