"""
Telemetry Drilldown Router for HandoffGuard.

Provides detailed time-series telemetry data from Exasol (or SQLite dev backend),
including raw and clock-skew-adjusted timestamps, product safe bands,
excursion zones, handoff window memberships, telemetry gaps, and per-handoff
evidence diagnostics.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_attribution_repo,
    get_attribution_service,
    get_excursion_repo,
    get_exposure_service,
    get_handoff_repo,
    get_logger_repo,
    get_product_repo,
    get_reading_repo,
    get_shipment_repo,
    is_exasol,
)
from app.config import settings
from app.core.domain.constants import GOOD_QUALITY_FLAGS
from app.core.services.attribution_service import AttributionService
from app.core.services.exposure_service import ExposureService

router = APIRouter(prefix="/api/shipments", tags=["Telemetry Drilldown"])


@router.get("/{shipment_id}/telemetry-drilldown")
async def get_telemetry_drilldown(
    shipment_id: int,
    shipment_repo=Depends(get_shipment_repo),
    product_repo=Depends(get_product_repo),
    handoff_repo=Depends(get_handoff_repo),
    logger_repo=Depends(get_logger_repo),
    reading_repo=Depends(get_reading_repo),
    excursion_repo=Depends(get_excursion_repo),
    attribution_repo=Depends(get_attribution_repo),
    exposure_service: ExposureService = Depends(get_exposure_service),
    attribution_service: AttributionService = Depends(get_attribution_service),
) -> Dict[str, Any]:
    """
    Returns full time-series readings with clock-skew adjustments,
    product safe temperature limits, handoff membership overlays,
    telemetry gap intervals, and detailed handoff diagnostics.
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

    min_safe = product.min_temp_c if product else 2.0
    max_safe = product.max_temp_c if product else 8.0

    handoffs = await handoff_repo.get_by_shipment(shipment_id)
    handoffs.sort(key=lambda h: h.sequence_no)

    loggers = await logger_repo.get_by_shipment(shipment_id)
    logger_map = {lg.logger_id: lg for lg in loggers}

    excursions = await excursion_repo.get_by_shipment(shipment_id)

    # 1. Gather all readings & calculate membership
    readings_data: List[Dict[str, Any]] = []
    readings_by_lg: Dict[int, list] = {}

    if is_exasol():
        from app.infrastructure.db.exasol_pool import get_pool
        pool = get_pool()

        # Query all readings with logger device info
        readings_sql = (
            "SELECT r.reading_id, r.logger_id, ld.device_code, r.reading_at_utc, "
            "       r.temperature_c, r.humidity_pct, r.battery_pct, r.quality_flag, "
            "       ld.clock_skew_seconds "
            "FROM HANDOFFGUARD.logger_readings r "
            "JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id "
            "WHERE ld.assigned_shipment_id = {sid!d} "
            "ORDER BY r.reading_at_utc"
        )
        raw_rows = await pool.execute(readings_sql, {"sid": shipment_id})

        # Query interval membership view
        membership_sql = (
            "SELECT reading_id, handoff_id, handoff_type, membership_status "
            "FROM HANDOFFGUARD.v_reading_handoff_membership "
            "WHERE shipment_id = {sid!d}"
        )
        membership_rows = await pool.execute(membership_sql, {"sid": shipment_id})
        membership_map: Dict[int, Dict[str, Any]] = {}
        for mr in membership_rows:
            def _mk(n):
                return mr.get(n.upper()) or mr.get(n)
            rid = int(_mk("reading_id"))
            membership_map[rid] = {
                "handoff_id": int(_mk("handoff_id")) if _mk("handoff_id") is not None else None,
                "handoff_type": str(_mk("handoff_type")) if _mk("handoff_type") else None,
                "membership_status": str(_mk("membership_status")),
            }

        for r in raw_rows:
            def _k(n):
                return r.get(n.upper()) or r.get(n)

            rid = int(_k("reading_id"))
            lg_id = int(_k("logger_id"))
            temp_c = float(_k("temperature_c"))
            skew = int(_k("clock_skew_seconds") or 0)
            raw_ts = str(_k("reading_at_utc"))

            # Parse timestamp to calculate adjusted timestamp
            dt_raw = None
            if "T" in raw_ts:
                dt_raw = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            else:
                try:
                    dt_raw = datetime.strptime(raw_ts[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                except Exception:
                    dt_raw = datetime.now(timezone.utc)

            dt_adj = dt_raw + timedelta(seconds=skew)
            mem_info = membership_map.get(rid, {})

            readings_data.append({
                "reading_id": rid,
                "logger_id": lg_id,
                "device_code": str(_k("device_code")),
                "reading_at_utc": dt_raw.isoformat(),
                "adjusted_reading_at_utc": dt_adj.isoformat(),
                "temperature_c": temp_c,
                "clock_skew_seconds": skew,
                "quality_flag": str(_k("quality_flag") or "valid"),
                "membership_status": mem_info.get("membership_status", "unmatched"),
                "handoff_id": mem_info.get("handoff_id"),
                "handoff_type": mem_info.get("handoff_type"),
                "is_above_safe": temp_c > max_safe,
                "is_below_safe": temp_c < min_safe,
            })
    else:
        # SQLite / Dev repository path
        all_readings = await reading_repo.get_by_shipment(shipment_id)
        skew_tolerance = settings.skew_tolerance_seconds

        for rd in all_readings:
            lg = logger_map.get(rd.logger_id)
            skew = lg.clock_skew_seconds if lg else 0
            raw_dt = rd.recorded_at_utc
            adj_dt = raw_dt + timedelta(seconds=skew)

            # Match against handoffs
            matches = []
            for h in handoffs:
                w_start = h.window_start_utc
                w_end = h.window_end_utc
                tol_start = w_start - timedelta(seconds=skew_tolerance)
                tol_end = w_end + timedelta(seconds=skew_tolerance)

                if tol_start <= adj_dt <= tol_end:
                    is_skew_bound = not (w_start <= adj_dt <= w_end)
                    matches.append((h, is_skew_bound))

            if len(matches) == 0:
                mem_status = "unmatched"
                matched_h = None
            elif len(matches) > 1:
                mem_status = "ambiguous"
                matched_h = matches[0][0]
            else:
                matched_h, is_skew_bound = matches[0]
                mem_status = "matched_with_skew" if is_skew_bound else "matched"

            readings_data.append({
                "reading_id": rd.reading_id,
                "logger_id": rd.logger_id,
                "device_code": lg.device_type if lg else f"LOG-{rd.logger_id:03d}",
                "reading_at_utc": raw_dt.isoformat(),
                "adjusted_reading_at_utc": adj_dt.isoformat(),
                "temperature_c": rd.temperature_c,
                "clock_skew_seconds": skew,
                "quality_flag": rd.quality_flag,
                "membership_status": mem_status,
                "handoff_id": matched_h.handoff_id if matched_h else None,
                "handoff_type": matched_h.handoff_type if matched_h else None,
                "is_above_safe": rd.temperature_c > max_safe,
                "is_below_safe": rd.temperature_c < min_safe,
            })

    # Sort readings chronologically
    readings_data.sort(key=lambda r: r["reading_at_utc"])

    # 2. Detect missing data gaps (> 2.5x sampling interval)
    gaps: List[Dict[str, Any]] = []
    for lg in loggers:
        lg_readings = [r for r in readings_data if r["logger_id"] == lg.logger_id]
        if len(lg_readings) < 2:
            continue
        interval_sec = max(60, lg.sampling_interval_seconds)
        gap_limit = interval_sec * 2.5

        for i in range(1, len(lg_readings)):
            t_prev = datetime.fromisoformat(lg_readings[i - 1]["reading_at_utc"])
            t_curr = datetime.fromisoformat(lg_readings[i]["reading_at_utc"])
            diff_sec = (t_curr - t_prev).total_seconds()
            if diff_sec > gap_limit:
                gaps.append({
                    "logger_id": lg.logger_id,
                    "device_code": lg.device_type,
                    "gap_start_utc": t_prev.isoformat(),
                    "gap_end_utc": t_curr.isoformat(),
                    "duration_minutes": round(diff_sec / 60.0, 1),
                })

    # 3. Compute per-handoff exposures & attribution confidence
    handoff_map: Dict[int, Dict[str, Any]] = {}
    for h in handoffs:
        dwell_min = round((h.window_end_utc - h.window_start_utc).total_seconds() / 60.0, 1)
        handoff_readings = [r for r in readings_data if r["handoff_id"] == h.handoff_id]
        handoff_map[h.handoff_id] = {
            "handoff_id": h.handoff_id,
            "sequence_no": h.sequence_no,
            "handoff_type": h.handoff_type,
            "from_party": h.from_party,
            "to_party": h.to_party,
            "location": h.location,
            "window_start_utc": h.window_start_utc.isoformat(),
            "window_end_utc": h.window_end_utc.isoformat(),
            "dwell_minutes": dwell_min,
            "reading_count": len(handoff_readings),
            "exposure_degree_minutes": 0.0,
            "exposure_share_pct": 0.0,
            "attribution_confidence": "low",
            "confidence_score": 0.5,
            "evidence_notes": [],
        }

    # Fetch attribution scores if an excursion exists
    if excursions:
        exc = excursions[0]
        # Build readings_by_lg for domain engine
        for lg in loggers:
            readings_by_lg[lg.logger_id] = await reading_repo.get_by_logger(lg.logger_id)

        _, _, evidence_items = attribution_service.compute_attribution(
            shipment=shipment,
            product=product,
            excursion=exc,
            handoffs=handoffs,
            loggers=loggers,
            readings_by_logger=readings_by_lg,
        )

        for ev in evidence_items:
            hid = ev["handoff_id"]
            if hid in handoff_map:
                handoff_map[hid]["exposure_degree_minutes"] = round(ev["exposure_degree_minutes"], 2)
                handoff_map[hid]["exposure_share_pct"] = round(ev["exposure_share_pct"], 1)
                handoff_map[hid]["attribution_confidence"] = ev["confidence_label"]
                handoff_map[hid]["confidence_score"] = round(ev["confidence_score"], 2)
                handoff_map[hid]["evidence_notes"] = ev["evidence_notes"]
    else:
        # If no explicit excursion, compute pure degree-minutes from exposure_service
        for lg in loggers:
            readings_by_lg[lg.logger_id] = await reading_repo.get_by_logger(lg.logger_id)
        exp_list, _, total_dm = exposure_service.compute_handoff_exposures(
            handoffs=handoffs,
            loggers=loggers,
            readings_by_logger=readings_by_lg,
            min_temp_c=min_safe,
            max_temp_c=max_safe,
        )
        for exp in exp_list:
            hid = exp.handoff.handoff_id
            if hid in handoff_map:
                handoff_map[hid]["exposure_degree_minutes"] = round(exp.exposure_degree_minutes, 2)
                share = (exp.exposure_degree_minutes / total_dm * 100.0) if total_dm > 0 else 0.0
                handoff_map[hid]["exposure_share_pct"] = round(share, 1)
                handoff_map[hid]["evidence_notes"] = [
                    f"Measured {round(exp.exposure_degree_minutes, 1)} °C·min exposure during {exp.handoff.handoff_type}.",
                ]

    return {
        "shipment_id": shipment_id,
        "shipment_code": shipment.shipment_code,
        "engine": "exasol" if is_exasol() else "sqlite",
        "product": {
            "product_id": product.product_id if product else 0,
            "name": product.name if product else "Unknown Product",
            "min_temp_c": min_safe,
            "max_temp_c": max_safe,
            "allowed_excursion_minutes": product.allowed_excursion_minutes if product else 120,
            "thermal_mass_class": product.thermal_mass_class if product else "Medium",
        },
        "readings": readings_data,
        "handoffs": list(handoff_map.values()),
        "gaps": gaps,
        "excursions": [
            {
                "excursion_id": ex.excursion_id,
                "started_at_utc": ex.started_at_utc.isoformat(),
                "ended_at_utc": ex.ended_at_utc.isoformat(),
                "duration_minutes": ex.duration_minutes,
                "peak_temp_c": ex.peak_temp_c,
                "severity": ex.severity,
            }
            for ex in excursions
        ],
        "disclaimer": "All telemetry is retrieved from Exasol/database tables. Exposure is estimated from ambient/logger data; thermal mass and packaging are not modelled.",
    }
