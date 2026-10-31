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
    shipment_id: str,
    status_filter: Optional[str] = Query(None, description="Filter by: matched, ambiguous, unmatched"),
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

        view_sql = (
            "SELECT reading_id, logger_id, reading_at_utc, corrected_at_utc, "
            "       temperature_c, battery_pct, shipment_id, handoff_id, "
            "       sequence_no, handoff_type, from_party, to_party, "
            "       window_start_utc, window_end_utc, window_source, "
            "       clock_skew_seconds, candidate_count, membership_status, ambiguity_flag "
            "FROM HANDOFFGUARD.v_reading_handoff_membership "
            "WHERE shipment_id = {sid} "
            "ORDER BY reading_at_utc"
        )
        all_rows = await pool.execute(view_sql, {"sid": str(shipment_id)})

        for r in all_rows:
            def _k(n: str):
                return r.get(n.upper()) or r.get(n)

            mem_status = str(_k("membership_status") or "unmatched").lower()
            if status_filter and mem_status != status_filter.lower():
                continue

            items.append({
                "reading_id": _k("reading_id"),
                "logger_id": _k("logger_id"),
                "reading_at_utc": str(_k("reading_at_utc") or ""),
                "corrected_at_utc": str(_k("corrected_at_utc") or ""),
                "temperature_c": float(_k("temperature_c") or 0.0),
                "battery_pct": float(_k("battery_pct")) if _k("battery_pct") is not None else None,
                "shipment_id": str(_k("shipment_id")),
                "handoff_id": _k("handoff_id"),
                "sequence_no": _k("sequence_no"),
                "handoff_type": str(_k("handoff_type")) if _k("handoff_type") else None,
                "from_party": str(_k("from_party")) if _k("from_party") else None,
                "to_party": str(_k("to_party")) if _k("to_party") else None,
                "window_start_utc": str(_k("window_start_utc") or "") if _k("window_start_utc") else None,
                "window_end_utc": str(_k("window_end_utc") or "") if _k("window_end_utc") else None,
                "window_source": str(_k("window_source") or "UNKNOWN"),
                "candidate_count": int(_k("candidate_count") or 0),
                "membership_status": mem_status,
                "skew_seconds": float(_k("clock_skew_seconds") or 0.0),
                "clock_skew_seconds": float(_k("clock_skew_seconds") or 0.0),
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

            # Check matches across handoffs using half-open intervals
            matches = []
            for h in handoffs:
                w_start = h.window_start_utc
                w_end = h.window_end_utc
                if w_start <= corrected_dt < w_end:
                    matches.append(h)

            if len(matches) == 0:
                mem_status = "unmatched"
                h_match = None
                ambiguity = False
            elif len(matches) > 1:
                mem_status = "ambiguous"
                h_match = matches[0]  # First candidate
                ambiguity = True
            else:
                h_match = matches[0]
                mem_status = "matched"
                ambiguity = False

            if status_filter and mem_status != status_filter.lower():
                continue

            items.append({
                "reading_id": rd.reading_id,
                "logger_id": rd.logger_id,
                "reading_at_utc": rd.recorded_at_utc.isoformat(),
                "corrected_at_utc": corrected_dt.isoformat(),
                "temperature_c": rd.temperature_c,
                "battery_pct": rd.battery_pct,
                "shipment_id": str(shipment_id),
                "handoff_id": h_match.handoff_id if h_match else None,
                "sequence_no": h_match.sequence_no if h_match else None,
                "handoff_type": h_match.handoff_type if h_match else None,
                "from_party": h_match.from_party if h_match else None,
                "to_party": h_match.to_party if h_match else None,
                "window_start_utc": h_match.window_start_utc.isoformat() if h_match else None,
                "window_end_utc": h_match.window_end_utc.isoformat() if h_match else None,
                "window_source": "ACTUAL" if h_match else "UNKNOWN",
                "candidate_count": len(matches),
                "membership_status": mem_status,
                "skew_seconds": skew,
                "clock_skew_seconds": skew,
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
        "shipment_id": str(shipment_id),
        "shipment_code": shipment.shipment_code,
        "engine": "exasol" if is_exasol() else "sqlite",
        "counts": counts,
        "items": items,
        "disclaimer": "Membership is derived dynamically via half-open time-window overlap and clock-skew correction. No handoff_id is stored in raw logger readings.",
    }
