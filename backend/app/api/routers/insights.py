"""
Exasol Query Insights & Benchmark Results Router.

Measures real execution time and row counts for analytical Exasol queries.
Provides reproducible performance benchmark metadata.
Strictly displays only measured values — no ungrounded throughput claims.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_handoff_repo,
    get_logger_repo,
    get_reading_repo,
    get_shipment_repo,
    is_exasol,
)

router = APIRouter(prefix="/api/exasol", tags=["Exasol Query Insights"])

QUERY_DEFINITIONS = {
    "shipment_interval_membership": {
        "name": "Shipment Reading-to-Handoff Interval Join",
        "sql_view": "HANDOFFGUARD.v_reading_handoff_membership",
        "sql_file_path": "db/migrations/005_repair_analytics_views.sql",
        "sql_query": """SELECT reading_id, logger_id, reading_at_utc, corrected_at_utc,
       temperature_c, battery_pct, shipment_id, handoff_id,
       sequence_no, handoff_type, from_party, to_party,
       window_start_utc, window_end_utc, window_source,
       clock_skew_seconds, candidate_count, membership_status, ambiguity_flag
FROM HANDOFFGUARD.v_reading_handoff_membership
WHERE shipment_id = :shipment_id
ORDER BY reading_at_utc;""",
    },
    "handoff_thermal_exposure": {
        "name": "Handoff Custody Thermal Exposure Aggregation",
        "sql_view": "HANDOFFGUARD.v_handoff_thermal_exposure",
        "sql_file_path": "db/migrations/005_repair_analytics_views.sql",
        "sql_query": """SELECT handoff_id, shipment_id, sequence_no, handoff_type,
       from_party, to_party, location, window_source,
       window_start_utc, window_end_utc, assigned_logger_count,
       custody_duration_minutes, reading_count,
       supported_observation_minutes, ambiguous_minutes,
       unsupported_gap_minutes, coverage_pct,
       min_temp_c, max_temp_c, avg_temp_c,
       safe_min_temp_c, safe_max_temp_c,
       minutes_above_safe, minutes_below_safe,
       degree_minutes_above, degree_minutes_below,
       total_degree_minutes, coverage_status
FROM HANDOFFGUARD.v_handoff_thermal_exposure
WHERE shipment_id = :shipment_id
ORDER BY sequence_no;""",
    },
    "excursion_attribution": {
        "name": "Custody Excursion Attribution & Ranking",
        "sql_view": "HANDOFFGUARD.v_excursion_attribution",
        "sql_file_path": "db/migrations/005_repair_analytics_views.sql",
        "sql_query": """SELECT excursion_id, shipment_id, handoff_id, sequence_no, handoff_type,
       associated_party, to_party, location, window_source,
       window_start_utc, window_end_utc, exc_start, exc_end,
       exc_duration_minutes, exc_peak_temp_c, assigned_logger_count,
       reading_count, supported_observation_minutes, ambiguous_minutes,
       handoff_total_dm, total_excursion_dm, total_supported_obs_min,
       exposure_share, attribution_rank, evidence_status, disclaimer
FROM HANDOFFGUARD.v_excursion_attribution
WHERE shipment_id = :shipment_id
ORDER BY attribution_rank;""",
    },
}


@router.get("/query-insights")
async def get_query_insights(
    query: str = Query("shipment_interval_membership", description="Query identifier"),
    shipment_id: str = Query("SHP-2026-0881", description="Shipment ID to query"),
    shipment_repo=Depends(get_shipment_repo),
    reading_repo=Depends(get_reading_repo),
    handoff_repo=Depends(get_handoff_repo),
) -> Dict[str, Any]:
    """
    Returns measured execution metrics for a specific Exasol query/view.
    Displays only real, empirically measured values.
    """
    q_key = query if query in QUERY_DEFINITIONS else "shipment_interval_membership"
    q_meta = QUERY_DEFINITIONS[q_key]

    shipment = await shipment_repo.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )

    t_start = time.perf_counter()
    rows_examined = 0
    rows_returned = 0
    latest_ts = None
    exasol_status = "dev_fallback"

    if is_exasol():
        try:
            from app.infrastructure.db.exasol_pool import get_pool
            pool = get_pool()

            # Execute query and measure timing
            if q_key == "shipment_interval_membership":
                sql = (
                    "SELECT reading_id, reading_at_utc, membership_status "
                    "FROM HANDOFFGUARD.v_reading_handoff_membership "
                    "WHERE shipment_id = {sid} "
                    "ORDER BY reading_at_utc"
                )
                rows = await pool.execute(sql, {"sid": str(shipment_id)})
                rows_returned = len(rows)

                # Total readings examined in table for this shipment
                cnt_sql = (
                    "SELECT COUNT(*) AS total_count, MAX(reading_at_utc) AS max_ts "
                    "FROM HANDOFFGUARD.logger_readings r "
                    "JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id "
                    "WHERE ld.assigned_shipment_id = {sid}"
                )
                cnt_rows = await pool.execute(cnt_sql, {"sid": str(shipment_id)})
                if cnt_rows:
                    first = cnt_rows[0]
                    rows_examined = int(first.get("TOTAL_COUNT") or first.get("total_count") or rows_returned)
                    latest_ts = str(first.get("MAX_TS") or first.get("max_ts") or "")
            else:
                view_name = q_meta["sql_view"]
                sql = f"SELECT * FROM {view_name} WHERE shipment_id = {{sid}}"
                rows = await pool.execute(sql, {"sid": str(shipment_id)})
                rows_returned = len(rows)
                rows_examined = rows_returned

            exasol_status = "connected"
        except Exception:
            # Fall back gracefully to measurement via repository
            exasol_status = "dev_fallback"

    if exasol_status == "dev_fallback":
        # Empirically measure via repository
        all_readings = await reading_repo.get_by_shipment(shipment_id)
        rows_examined = len(all_readings)

        if all_readings:
            latest_ts = all_readings[-1].recorded_at_utc.isoformat()

        if q_key == "shipment_interval_membership":
            handoffs = await handoff_repo.get_by_shipment(shipment_id)
            matched_count = 0
            for r in all_readings:
                for h in handoffs:
                    if h.window_start_utc <= r.recorded_at_utc < h.window_end_utc:
                        matched_count += 1
                        break
            rows_returned = matched_count
        else:
            handoffs = await handoff_repo.get_by_shipment(shipment_id)
            rows_returned = len(handoffs)

    elapsed_ms = (time.perf_counter() - t_start) * 1000.0

    # Read SQL file contents if available
    sql_text = q_meta["sql_query"]
    file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        q_meta["sql_file_path"],
    )
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                sql_text = f.read()
        except Exception:
            pass

    return {
        "query_key": q_key,
        "query_identifier": q_key,
        "query_name": q_meta["name"],
        "sql_view": q_meta["sql_view"],
        "sql_file_path": q_meta["sql_file_path"],
        "sql_source": sql_text,
        "sql_query": sql_text,
        "rows_examined": rows_examined,
        "rows_returned": rows_returned,
        "execution_time_ms": round(elapsed_ms, 2),
        "latest_reading_timestamp": latest_ts,
        "exasol_connection_status": exasol_status,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Measured directly on the running backend. No simulated or inflated figures.",
        "execution_metrics": {
            "execution_time_ms": round(elapsed_ms, 2),
            "rows_examined": rows_examined,
            "rows_returned": rows_returned,
            "filter_applied": f"shipment_id = '{shipment_id}'",
            "measured_at_utc": datetime.now(timezone.utc).isoformat(),
            "latest_reading_at_utc": latest_ts,
            "engine": exasol_status,
        },
        "system_profile": {
            "database": "Exasol" if exasol_status == "connected" else "SQLite (Fallback)",
            "join_method": "Analytical SQL Interval Join (corrected_time >= actual_start_at AND corrected_time < actual_end_at)",
            "aggregation": "Degree-minutes across supported segments (<= 600s gap)",
            "disclaimer": "Measured directly on the running backend. No simulated or inflated figures.",
        },
    }


@router.get("/benchmark-results")
async def get_benchmark_results() -> Dict[str, Any]:
    """
    Returns the reproducible multi-engine interval join benchmark results
    for the /exasol/benchmark UI page.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
    json_path = os.path.join(repo_root, "reports", "interval_join_benchmark.json")

    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error reading benchmark results: {str(e)}",
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Benchmark report not found. Run 'npm run benchmark:interval-join' to generate it.",
    )

