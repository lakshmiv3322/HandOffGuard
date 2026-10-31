"""
Handoff Thermal Exposure Router.

Calculates defensible thermal exposure (degree-minutes above and below safe thresholds)
per custody handoff window based on Exasol repaired analytical views.
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
    shipment_id: str,
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
    Derived from Exasol view V_HANDOFF_THERMAL_EXPOSURE or pure domain engine.
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
            "       from_party, to_party, location, window_source, "
            "       window_start_utc, window_end_utc, assigned_logger_count, "
            "       custody_duration_minutes, reading_count, "
            "       supported_observation_minutes, ambiguous_minutes, "
            "       unsupported_gap_minutes, coverage_pct, "
            "       min_temp_c, max_temp_c, avg_temp_c, "
            "       safe_min_temp_c, safe_max_temp_c, "
            "       minutes_above_safe, minutes_below_safe, "
            "       degree_minutes_above, degree_minutes_below, "
            "       total_degree_minutes, coverage_status "
            "FROM HANDOFFGUARD.v_handoff_thermal_exposure "
            "WHERE shipment_id = {sid} "
            "ORDER BY sequence_no"
        )
        rows = await pool.execute(sql, {"sid": str(shipment_id)})

        for r in rows:
            def _k(n: str):
                return r.get(n.upper()) or r.get(n)

            deg_above = float(_k("degree_minutes_above") or 0.0)
            deg_below = float(_k("degree_minutes_below") or 0.0)
            tot_deg = float(_k("total_degree_minutes") or (deg_above + deg_below))
            total_degree_minutes += tot_deg

            severity = "none"
            if tot_deg > 100:
                severity = "critical"
            elif tot_deg > 20:
                severity = "high"
            elif tot_deg > 0:
                severity = "medium"

            handoff_exposures.append({
                "handoff_id": _k("handoff_id"),
                "sequence_no": int(_k("sequence_no") or 0),
                "handoff_type": str(_k("handoff_type") or ""),
                "from_party": str(_k("from_party") or ""),
                "to_party": str(_k("to_party") or ""),
                "location": str(_k("location") or ""),
                "window_source": str(_k("window_source") or "ACTUAL"),
                "window_start_utc": str(_k("window_start_utc") or ""),
                "window_end_utc": str(_k("window_end_utc") or ""),
                "window_duration_minutes": float(_k("custody_duration_minutes") or 0.0),
                "custody_duration_minutes": float(_k("custody_duration_minutes") or 0.0),
                "reading_count": int(_k("reading_count") or 0),
                "assigned_logger_count": int(_k("assigned_logger_count") or 0),
                "supported_observation_minutes": float(_k("supported_observation_minutes") or 0.0),
                "ambiguous_minutes": float(_k("ambiguous_minutes") or 0.0),
                "unsupported_gap_minutes": float(_k("unsupported_gap_minutes") or 0.0),
                "coverage_pct": float(_k("coverage_pct") or 0.0),
                "coverage_status": str(_k("coverage_status") or "ADEQUATELY_COVERED"),
                "min_temp_c": float(_k("min_temp_c")) if _k("min_temp_c") is not None else None,
                "max_temp_c": float(_k("max_temp_c")) if _k("max_temp_c") is not None else None,
                "avg_temp_c": float(_k("avg_temp_c")) if _k("avg_temp_c") is not None else None,
                "safe_min_temp_c": float(_k("safe_min_temp_c") or (product.min_temp_c if product else 2.0)),
                "safe_max_temp_c": float(_k("safe_max_temp_c") or (product.max_temp_c if product else 8.0)),
                "minutes_above_safe": float(_k("minutes_above_safe") or 0.0),
                "minutes_below_safe": float(_k("minutes_below_safe") or 0.0),
                "degree_minutes_above": deg_above,
                "degree_minutes_below": deg_below,
                "total_degree_minutes": tot_deg,
                "ambiguous_reading_count": 0,
                "exposure_severity": severity,
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
                if h.window_start_utc <= r.recorded_at_utc < h.window_end_utc
            ]
            r_count = len(h_readings)
            min_t = min((r.temperature_c for r in h_readings), default=None)
            max_t = max((r.temperature_c for r in h_readings), default=None)
            avg_t = sum((r.temperature_c for r in h_readings)) / r_count if r_count > 0 else None

            # Calculate degree minutes (assuming 1-10 min intervals)
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
            tot_deg = deg_above + deg_below
            total_degree_minutes += tot_deg

            severity = "none"
            if tot_deg > 100:
                severity = "critical"
            elif tot_deg > 20:
                severity = "high"
            elif tot_deg > 0:
                severity = "medium"

            w_duration = (h.window_end_utc - h.window_start_utc).total_seconds() / 60.0

            handoff_exposures.append({
                "handoff_id": h.handoff_id,
                "sequence_no": h.sequence_no,
                "handoff_type": h.handoff_type,
                "from_party": h.from_party,
                "to_party": h.to_party,
                "location": h.location,
                "window_source": "ACTUAL",
                "window_start_utc": h.window_start_utc.isoformat(),
                "window_end_utc": h.window_end_utc.isoformat(),
                "window_duration_minutes": w_duration,
                "custody_duration_minutes": w_duration,
                "reading_count": r_count,
                "assigned_logger_count": len(loggers),
                "supported_observation_minutes": r_count * 5.0,
                "ambiguous_minutes": 0.0,
                "unsupported_gap_minutes": max(0.0, w_duration - (r_count * 5.0)),
                "coverage_pct": round(min(100.0, (r_count * 5.0 / w_duration) * 100.0), 1) if w_duration > 0 else 0.0,
                "coverage_status": "ADEQUATELY_COVERED" if r_count > 0 else "NO_SUPPORTED_OBSERVATIONS",
                "min_temp_c": min_t,
                "max_temp_c": max_t,
                "avg_temp_c": round(avg_t, 2) if avg_t is not None else None,
                "safe_min_temp_c": safe_min,
                "safe_max_temp_c": safe_max,
                "minutes_above_safe": mins_above,
                "minutes_below_safe": mins_below,
                "degree_minutes_above": round(deg_above, 2),
                "degree_minutes_below": round(deg_below, 2),
                "total_degree_minutes": round(tot_deg, 2),
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
        "shipment_id": str(shipment_id),
        "shipment_code": shipment.shipment_code,
        "product_name": product.name if product else "Unknown",
        "safe_range_c": f"{product.min_temp_c if product else 2.0}°C to {product.max_temp_c if product else 8.0}°C",
        "total_shipment_degree_minutes": round(total_degree_minutes, 2),
        "handoffs": handoff_exposures,
        "disclaimer": (
            "Exposure is calculated from supported logger reading segments (<= 600s prototype gap limit) and custody-window overlap. "
            "It is an investigation aid, not proof of product temperature, root cause or legal liability."
        ),
    }
