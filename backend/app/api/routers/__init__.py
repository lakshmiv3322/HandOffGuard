"""API routers package."""

from app.api.routers.health import router as health_router
from app.api.routers.meta import router as meta_router
from app.api.routers.shipments import router as shipments_router
from app.api.routers.attribution import router as attribution_router
from app.api.routers.evidence import router as evidence_router
from app.api.routers.prevention import router as prevention_router
from app.api.routers.ingest import router as ingest_router
from app.api.routers.membership import router as membership_router
from app.api.routers.exposure import router as exposure_router

__all__ = [
    "health_router",
    "meta_router",
    "shipments_router",
    "attribution_router",
    "evidence_router",
    "prevention_router",
    "ingest_router",
    "membership_router",
    "exposure_router",
]
