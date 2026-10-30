"""
Reading-to-Handoff Membership Router.

Core Technical Differentiator:
Derives reading-to-handoff association strictly via time-interval join.
Temperature readings contain NO handoff_id.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_handoff_repo,
    get_logger_repo,
    get_reading_repo,
    get_shipment_repo,
    is_exasol,
)
from app.config import settings

router = APIRouter(prefix="/api/shipments", tags=["Membership"])


@router.get("/{shipment_id}/membership")
async def get_shipment_membership(
    shipment_id: int,
    status_filter: Optional[str] = Query(None, description="Filter by: matched, matched_with_skew, ambiguous, unmatched"),
    limit: int = Query(500, description="Max readings to return"),
    shipment_repo=Depends(get_shipment_repo),
    handoff_repo=Depends(get_handoff_repo),
    logger_repo=Depends(get_logger_repo),
    reading_repo=Depends(get_reading_repo),
) -> Dict[str, Any]:
    """
    Retrieve reading-to-handoff interval join membership results for a shipment.

    Derived dynamically via time-window overlap with clock-skew correction.
    Labels each reading as:
    - 'matched': Cleanly inside a single handoff window
    - 'matched_with_skew': Within clock-skew tolerance window boundary
    - 'ambiguous': Falls into overlapping handoff windows (>1 matching handoffs)
    - 'unmatched': Falls into transit gaps or outside all handoff windows
    """
    shipment = await shipment_repo.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )

    items: List[Dict[str, Any]] = []

    if is_exasol():
        from app.infrastructure.db.exasol_pool import get_pool
        pool = get_pool()

        # Query matched / ambiguous / matched_with_skew from view
        view_sql = (
            "SELECT reading_id, logger_id, reading_at_utc, temperature_c, battery_pct, "
            "       shipment_id, handoff_id, handoff_type, from_party, to_party, "
            "       window_start_utc, window_end_utc, skew_seconds, boundary_skew_seconds, "
            "       membership_status, ambiguity_flag "
            "FROM HANDOFFGUARD.v_reading_handoff_membership "
            "WHERE shipment_id = {sid!d} "
            "ORDER BY reading_at_utc"
        )
        matched_rows = await pool.execute(view_sql, {"sid": shipment_id})

        # Query unmatched readings
        unmatched_sql = (
            "SELECT r.reading_id, r.logger_id, r.reading_at_utc, r.temperature_c, r.battery_pct, "
            "       ld.assigned_shipment_id AS shipment_id, "
            "       NULL AS handoff_id, NULL AS handoff_type, NULL AS from_party, NULL AS to_party, "
            "       NULL AS window_start_utc, NULL AS window_end_utc, "
            "       ld.clock_skew_seconds AS skew_seconds, 0 AS boundary_skew_seconds, "
            "       'unmatched' AS membership_status, FALSE AS ambiguity_flag "
            "FROM HANDOFFGUARD.logger_readings r "
            "JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id "
            "WHERE ld.assigned_shipment_id = {sid!d} "
            "  AND r.reading_id NOT IN ( "
            "      SELECT reading_id FROM HANDOFFGUARD.v_reading_handoff_membership "
            "  ) "
            "ORDER BY r.reading_at_utc"
        )
        unmatched_rows = await pool.execute(unmatched_sql, {"sid": shipment_id})

        all_rows = matched_rows + unmatched_rows
        all_rows.sort(key=lambda x: str(x.get("READING_AT_UTC") or x.get("reading_at_utc")))

        for r in all_rows:
            def _k(n):
                return r.get(n.upper()) or r.get(n)

            mem_status = str(_k("membership_status"))
            if status_filter and mem_status != status_filter:
                continue

            items.append({
                "reading_id": int(_k("reading_id")),
                "logger_id": int(_k("logger_id")),
                "reading_at_utc": str(_k("reading_at_utc")),
                "temperature_c": float(_k("temperature_c")),
                "battery_pct": float(_k("battery_pct")) if _k("battery_pct") is not None else None,
                "shipment_id": int(_k("shipment_id")),
                "handoff_id": int(_k("handoff_id")) if _k("handoff_id") is not None else None,
                "handoff_type": str(_k("handoff_type")) if _k("handoff_type") else None,
                "from_party": str(_k("from_party")) if _k("from_party") else None,
                "to_party": str(_k("to_party")) if _k("to_party") else None,
                "membership_status": mem_status,
                "skew_seconds": float(_k("skew_seconds") or 0.0),
                "ambiguity_flag": bool(_k("ambiguity_flag")),
            })
            if len(items) >= limit:
                break
    else:
        # Dev (SQLite / In-Memory interval join calculation)
        handoffs = await handoff_repo.get_by_shipment(shipment_id)
        loggers = await logger_repo.get_by_shipment(shipment_id)
        logger_map = {lg.logger_id: lg for lg in loggers}
        readings = await reading_repo.get_by_shipment(shipment_id)
        skew_tolerance = settings.skew_tolerance_seconds

        for rd in readings:
            lg = logger_map.get(rd.logger_id)
            skew = lg.clock_skew_seconds if lg else 0.0
            corrected_dt = rd.recorded_at_utc - timedelta(seconds=skew)

            # Check matches across handoffs
            matches = []
            for h in handoffs:
                w_start = h.window_start_utc
                w_end = h.window_end_utc
                tol_start = w_start - timedelta(seconds=skew_tolerance)
                tol_end = w_end + timedelta(seconds=skew_tolerance)

                if tol_start <= corrected_dt <= tol_end:
                    is_skew_boundary = not (w_start <= corrected_dt <= w_end)
                    matches.append((h, is_skew_boundary))

            if len(matches) == 0:
                mem_status = "unmatched"
                h_match = None
                ambiguity = False
            elif len(matches) > 1:
                mem_status = "ambiguous"
                h_match = matches[0][0]  # Primary match
                ambiguity = True
            else:
                h_match, is_skew_boundary = matches[0]
                mem_status = "matched_with_skew" if is_skew_boundary else "matched"
                ambiguity = False

            if status_filter and mem_status != status_filter:
                continue

            items.append({
                "reading_id": rd.reading_id,
                "logger_id": rd.logger_id,
                "reading_at_utc": rd.recorded_at_utc.isoformat(),
                "temperature_c": rd.temperature_c,
                "battery_pct": rd.battery_pct,
                "shipment_id": shipment_id,
                "handoff_id": h_match.handoff_id if h_match else None,
                "handoff_type": h_match.handoff_type if h_match else None,
                "from_party": h_match.from_party if h_match else None,
                "to_party": h_match.to_party if h_match else None,
                "membership_status": mem_status,
                "skew_seconds": skew,
                "ambiguity_flag": ambiguity,
            })
            if len(items) >= limit:
                break

    # Summary statistics
    counts = {
        "total": len(items),
        "matched": sum(1 for i in items if i["membership_status"] == "matched"),
        "matched_with_skew": sum(1 for i in items if i["membership_status"] == "matched_with_skew"),
        "ambiguous": sum(1 for i in items if i["membership_status"] == "ambiguous"),
        "unmatched": sum(1 for i in items if i["membership_status"] == "unmatched"),
    }

    return {
        "shipment_id": shipment_id,
        "shipment_code": shipment.shipment_code,
        "engine": "exasol" if is_exasol() else "sqlite",
        "counts": counts,
        "items": items,
        "disclaimer": "Membership is derived dynamically via time-window overlap and clock-skew correction. No handoff_id is stored in raw logger readings.",
    }
