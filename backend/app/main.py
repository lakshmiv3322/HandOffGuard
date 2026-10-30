"""
FastAPI application entry point for HandoffGuard.

Hackathon prototype for ExaThon India 2026.
Pharmaceutical cold-chain custody-attribution application.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.deps import get_db_backend
from app.api.routers import (
    attribution_router,
    evidence_router,
    exposure_router,
    health_router,
    ingest_router,
    membership_router,
    meta_router,
    prevention_router,
    shipments_router,
    telemetry_router,
    insights_router,
)
from app.config import settings
from app.infrastructure.db.dev_db import DevDatabaseBackend


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle handler."""
    backend = get_db_backend()
    if isinstance(backend, DevDatabaseBackend):
        # SQLite / Postgres: create tables via SQLAlchemy ORM
        await backend.create_tables()
    else:
        # Exasol: initialise the connection pool on startup
        # Tables are created via db/migrations/ SQL scripts run separately.
        try:
            from app.infrastructure.db.exasol_db import ExasolDatabaseBackend
            if isinstance(backend, ExasolDatabaseBackend):
                await backend.initialise()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Exasol pool initialisation failed at startup: %s. "
                "The app will start but Exasol endpoints will return errors.", exc
            )

    yield


app = FastAPI(
    title="HandoffGuard API",
    description=(
        "Pharmaceutical cold-chain custody-attribution prototype for ExaThon India 2026. "
        "Provides custody timeline reconstruction, interval-join temperature attribution, "
        "and explainable thermal exposure scoring."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(meta_router)
app.include_router(shipments_router)
app.include_router(attribution_router)
app.include_router(evidence_router)
app.include_router(prevention_router)
app.include_router(ingest_router)
app.include_router(membership_router)
app.include_router(exposure_router)
app.include_router(telemetry_router)
app.include_router(insights_router)


# Custom documentation endpoint for future Exasol integration
@app.get("/docs/exasol", response_class=HTMLResponse, tags=["Metadata"])
async def exasol_integration_docs():
    """Returns documentation and migration guide for Exasol database connection."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>HandoffGuard — Exasol Database Integration Guide</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #1e293b; }
            h1 { color: #0284c7; }
            h2 { color: #334155; margin-top: 30px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }
            pre { background: #0f172a; color: #f8fafc; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 14px; }
            code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 14px; }
            .badge { display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; background: #e0f2fe; color: #0369a1; }
        </style>
    </head>
    <body>
        <span class="badge">Architecture Guide</span>
        <h1>Exasol Database Integration Architecture</h1>
        <p>HandoffGuard uses an adapter pattern that decouples pure domain calculations from database storage. The database schema strictly adheres to the 8 Exasol tables without non-standard types.</p>
        
        <h2>Exasol Interval Join Query Pattern</h2>
        <p>In Exasol, temperature readings are matched with handoffs using high-performance analytics interval joins:</p>
        <pre><code>SELECT 
    r.reading_id,
    h.handoff_id,
    r.temperature_c,
    TIMESTAMPDIFF('SECOND', h.window_start_utc, h.window_end_utc) AS handoff_duration_sec
FROM HANDOFFGUARD.temperature_readings r
JOIN HANDOFFGUARD.loggers l ON r.logger_id = l.logger_id
JOIN HANDOFFGUARD.handoffs h ON h.shipment_id = l.assigned_shipment_id
WHERE TIMESTAMPADD('SECOND', l.clock_skew_seconds, r.recorded_at_utc)
    BETWEEN TIMESTAMPADD('SECOND', -120, h.window_start_utc)
    AND TIMESTAMPADD('SECOND', 120, h.window_end_utc);</code></pre>

        <h2>Steps to Switch to Exasol</h2>
        <ol>
            <li>Set <code>DATABASE_ENGINE=exasol</code> in <code>.env</code></li>
            <li>Configure <code>EXASOL_HOST</code>, <code>EXASOL_PORT</code>, <code>EXASOL_USER</code>, <code>EXASOL_PASSWORD</code>, <code>EXASOL_SCHEMA</code></li>
            <li>Install pyexasol: <code>pip install pyexasol</code></li>
            <li>Implement the repository interfaces defined in <code>app.infrastructure.repositories.base</code></li>
        </ol>
    </body>
    </html>
    """


# Consistent error response format
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": str(exc) if settings.debug else "An unexpected error occurred.",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )
