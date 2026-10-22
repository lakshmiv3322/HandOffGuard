"""API endpoint integration tests."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from scripts.seed_data import seed


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    import asyncio
    asyncio.run(seed())


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "database_connection_status" in data
        assert "database_engine_name" in data


@pytest.mark.asyncio
async def test_meta_product_limits():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/meta/product-limits")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 2


@pytest.mark.asyncio
async def test_shipments_list_pagination():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/shipments?page=1&page_size=10")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "page" in data
        assert "page_size" in data
        assert "total" in data
        assert data["page"] == 1
        assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_shipment_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/shipments/999999")
        assert res.status_code == 404
        data = res.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_prevention_upcoming():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/prevention/upcoming")
        assert res.status_code == 200
        data = res.json()
        assert "shipment" in data
        assert "riskiest_handoff" in data
        assert "suggestion" in data
        assert data["suggestion"]["prototype_flag"] is True
        assert "disclaimer" in data


@pytest.mark.asyncio
async def test_exasol_docs():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/docs/exasol")
        assert res.status_code == 200
        assert "Exasol" in res.text
