"""
Handoff Thermal Exposure Router.

Calculates defensible thermal exposure (degree-minutes above and below safe thresholds)
per custody handoff window.
"""

from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_exposure_service,
    get_handoff_repo,
    get_logger_repo,
    get_product_repo,
    get_reading_repo,
    get_shipment_repo,
    is_exasol,
)
from app.core.services.exposure_service import ExposureService

router = APIRouter(prefix="/api/shipments", tags=["Exposure"])


@router.get("/{shipment_id}/exposure")
async def get_shipment_exposure(
    shipment_id: int,
    shipment_repo=Depends(get_shipment_repo),
    product_repo=Depends(get_product_repo),
    handoff_repo=Depends(get_handoff_repo),
    logger_repo=Depends(get_logger_repo),
    reading_repo=Depends(get_reading_repo),
    exposure_service: ExposureService = Depends(get_exposure_service),
) -> Dict[str, Any]:
    """
    Calculate and return thermal exposure metrics by handoff leg.

    degree_minutes = (temperature_c - safe_threshold_c) × minutes_at_that_temperature
    Calculated from Exasol view v_handoff_thermal_exposure or pure domain engine.
    """
    shipment = await shipment_repo.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )

    product = shipment.product
    if not product:
        product = await product_repo.get_by_id(shipment.product_id)

    handoff_exposures: List[Dict[str, Any]] = []
    total_degree_minutes = 0.0

    if is_exasol():
        from app.infrastructure.db.exasol_pool import get_pool
        pool = get_pool()

        sql = (
            "SELECT handoff_id, shipment_id, sequence_no, handoff_type, "
            "       from_party, to_party, location, window_start_utc, window_end_utc, "
            "       window_duration_minutes, reading_count, "
            "       min_temp_c, max_temp_c, avg_temp_c, "
            "       safe_min_temp_c, safe_max_temp_c, "
            "       minutes_above_safe, minutes_below_safe, "
            "       degree_minutes_above, degree_minutes_below, "
            "       ambiguous_reading_count, exposure_severity "
            "FROM HANDOFFGUARD.v_handoff_thermal_exposure "
            "WHERE shipment_id = {sid!d} "
            "ORDER BY sequence_no"
        )
        rows = await pool.execute(sql, {"sid": shipment_id})

        for r in rows:
            def _k(n):
                return r.get(n.upper()) or r.get(n)

            deg_above = float(_k("degree_minutes_above") or 0.0)
            deg_below = float(_k("degree_minutes_below") or 0.0)
            total_deg = deg_above + deg_below
            total_degree_minutes += total_deg

            handoff_exposures.append({
                "handoff_id": int(_k("handoff_id")),
                "sequence_no": int(_k("sequence_no")),
                "handoff_type": str(_k("handoff_type")),
                "from_party": str(_k("from_party")),
                "to_party": str(_k("to_party")),
                "location": str(_k("location")),
                "window_start_utc": str(_k("window_start_utc")),
                "window_end_utc": str(_k("window_end_utc")),
                "window_duration_minutes": float(_k("window_duration_minutes") or 0.0),
                "reading_count": int(_k("reading_count") or 0),
                "min_temp_c": float(_k("min_temp_c")) if _k("min_temp_c") is not None else None,
                "max_temp_c": float(_k("max_temp_c")) if _k("max_temp_c") is not None else None,
                "avg_temp_c": float(_k("avg_temp_c")) if _k("avg_temp_c") is not None else None,
                "safe_min_temp_c": float(_k("safe_min_temp_c") or (product.min_temp_c if product else 2.0)),
                "safe_max_temp_c": float(_k("safe_max_temp_c") or (product.max_temp_c if product else 8.0)),
                "minutes_above_safe": float(_k("minutes_above_safe") or 0.0),
                "minutes_below_safe": float(_k("minutes_below_safe") or 0.0),
                "degree_minutes_above": deg_above,
                "degree_minutes_below": deg_below,
                "total_degree_minutes": total_deg,
                "ambiguous_reading_count": int(_k("ambiguous_reading_count") or 0),
                "exposure_severity": str(_k("exposure_severity") or "none"),
                "share_pct": 0.0,
            })
    else:
        # Dev (SQLite calculation via ExposureService)
        handoffs = await handoff_repo.get_by_shipment(shipment_id)
        loggers = await logger_repo.get_by_shipment(shipment_id)
        readings = await reading_repo.get_by_shipment(shipment_id)

        safe_min = product.min_temp_c if product else 2.0
        safe_max = product.max_temp_c if product else 8.0

        for h in handoffs:
            h_readings = [
                r for r in readings
                if h.window_start_utc <= r.recorded_at_utc <= h.window_end_utc
            ]
            r_count = len(h_readings)
            min_t = min((r.temperature_c for r in h_readings), default=None)
            max_t = max((r.temperature_c for r in h_readings), default=None)
            avg_t = sum((r.temperature_c for r in h_readings)) / r_count if r_count > 0 else None

            # Calculate degree minutes (assuming 5 min interval)
            deg_above = sum(
                (r.temperature_c - safe_max) * 5.0
                for r in h_readings
                if r.temperature_c > safe_max
            )
            deg_below = sum(
                (safe_min - r.temperature_c) * 5.0
                for r in h_readings
                if r.temperature_c < safe_min
            )
            mins_above = sum(5.0 for r in h_readings if r.temperature_c > safe_max)
            mins_below = sum(5.0 for r in h_readings if r.temperature_c < safe_min)
            total_deg = deg_above + deg_below
            total_degree_minutes += total_deg

            severity = "none"
            if deg_above > 100 or deg_below > 100:
                severity = "critical"
            elif deg_above > 20 or deg_below > 20:
                severity = "high"
            elif deg_above > 0 or deg_below > 0:
                severity = "medium"

            w_duration = (h.window_end_utc - h.window_start_utc).total_seconds() / 60.0

            handoff_exposures.append({
                "handoff_id": h.handoff_id,
                "sequence_no": h.sequence_no,
                "handoff_type": h.handoff_type,
                "from_party": h.from_party,
                "to_party": h.to_party,
                "location": h.location,
                "window_start_utc": h.window_start_utc.isoformat(),
                "window_end_utc": h.window_end_utc.isoformat(),
                "window_duration_minutes": w_duration,
                "reading_count": r_count,
                "min_temp_c": min_t,
                "max_temp_c": max_t,
                "avg_temp_c": round(avg_t, 2) if avg_t is not None else None,
                "safe_min_temp_c": safe_min,
                "safe_max_temp_c": safe_max,
                "minutes_above_safe": mins_above,
                "minutes_below_safe": mins_below,
                "degree_minutes_above": round(deg_above, 2),
                "degree_minutes_below": round(deg_below, 2),
                "total_degree_minutes": round(total_deg, 2),
                "ambiguous_reading_count": 0,
                "exposure_severity": severity,
                "share_pct": 0.0,
            })

    # Calculate share_pct for each handoff
    for h in handoff_exposures:
        if total_degree_minutes > 0:
            h["share_pct"] = round((h["total_degree_minutes"] / total_degree_minutes) * 100.0, 1)
        else:
            h["share_pct"] = 0.0

    return {
        "shipment_id": shipment_id,
        "shipment_code": shipment.shipment_code,
        "product_name": product.name if product else "Unknown",
        "safe_range_c": f"{product.min_temp_c if product else 2.0}°C to {product.max_temp_c if product else 8.0}°C",
        "total_shipment_degree_minutes": round(total_degree_minutes, 2),
        "handoffs": handoff_exposures,
        "disclaimer": (
            "Exposure is calculated from logger readings and handoff-window overlap. "
            "It is an investigation aid, not proof of product temperature or liability."
        ),
    }
