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
        "sql_file_path": "db/migrations/004_create_views.sql",
        "sql_query": """SELECT reading_id, logger_id, reading_at_utc, temperature_c, battery_pct,
       shipment_id, handoff_id, handoff_type, from_party, to_party,
       window_start_utc, window_end_utc, skew_seconds, boundary_skew_seconds,
       membership_status, ambiguity_flag
FROM HANDOFFGUARD.v_reading_handoff_membership
WHERE shipment_id = :shipment_id
ORDER BY reading_at_utc;""",
    },
    "handoff_thermal_exposure": {
        "name": "Handoff Custody Thermal Exposure Aggregation",
        "sql_view": "HANDOFFGUARD.v_handoff_thermal_exposure",
        "sql_file_path": "db/migrations/004_create_views.sql",
        "sql_query": """SELECT handoff_id, shipment_id, sequence_no, handoff_type,
       from_party, to_party, location, window_start_utc, window_end_utc,
       window_duration_minutes, reading_count,
       min_temp_c, max_temp_c, avg_temp_c,
       minutes_above_safe, minutes_below_safe,
       degree_minutes_above, degree_minutes_below,
       exposure_severity
FROM HANDOFFGUARD.v_handoff_thermal_exposure
WHERE shipment_id = :shipment_id
ORDER BY sequence_no;""",
    },
    "excursion_attribution": {
        "name": "Custody Excursion Attribution & Ranking",
        "sql_view": "HANDOFFGUARD.v_excursion_attribution",
        "sql_file_path": "db/migrations/004_create_views.sql",
        "sql_query": """SELECT handoff_id, shipment_id, sequence_no, handoff_type,
       from_party, to_party, handoff_degree_minutes_above,
       exposure_share, skew_penalty, ambiguity_penalty,
       attribution_score, confidence_level, attribution_rank
FROM HANDOFFGUARD.v_excursion_attribution
WHERE shipment_id = :shipment_id
ORDER BY attribution_rank;""",
    },
}


@router.get("/query-insights")
async def get_query_insights(
    query: str = Query("shipment_interval_membership", description="Query identifier"),
    shipment_id: int = Query(1, description="Shipment ID to query"),
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
                    "WHERE shipment_id = {sid!d} "
                    "ORDER BY reading_at_utc"
                )
                rows = await pool.execute(sql, {"sid": shipment_id})
                rows_returned = len(rows)

                # Total readings examined in table for this shipment
                cnt_sql = (
                    "SELECT COUNT(*) AS total_count, MAX(reading_at_utc) AS max_ts "
                    "FROM HANDOFFGUARD.logger_readings r "
                    "JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id "
                    "WHERE ld.assigned_shipment_id = {sid!d}"
                )
                cnt_rows = await pool.execute(cnt_sql, {"sid": shipment_id})
                if cnt_rows:
                    first = cnt_rows[0]
                    rows_examined = int(first.get("TOTAL_COUNT") or first.get("total_count") or rows_returned)
                    latest_ts = str(first.get("MAX_TS") or first.get("max_ts") or "")
            else:
                view_name = q_meta["sql_view"]
                sql = f"SELECT * FROM {view_name} WHERE shipment_id = {{sid!d}}"
                rows = await pool.execute(sql, {"sid": shipment_id})
                rows_returned = len(rows)
                rows_examined = rows_returned

            exasol_status = "connected"
        except Exception:
            # Fall back gracefully to measurement via repository
            exasol_status = "dev_fallback"

    if exasol_status == "dev_fallback":
        # Empirically measure via SQLite repository
        all_readings = await reading_repo.get_by_shipment(shipment_id)
        rows_examined = len(all_readings)

        if all_readings:
            latest_ts = all_readings[-1].recorded_at_utc.isoformat()

        if q_key == "shipment_interval_membership":
            handoffs = await handoff_repo.get_by_shipment(shipment_id)
            # Count matches
            matched_count = 0
            for r in all_readings:
                for h in handoffs:
                    if h.window_start_utc <= r.recorded_at_utc <= h.window_end_utc:
                        matched_count += 1
                        break
            rows_returned = matched_count
        else:
            handoffs = await handoff_repo.get_by_shipment(shipment_id)
            rows_returned = len(handoffs)

    t_end = time.perf_counter()
    measured_ms = round((t_end - t_start) * 1000.0, 2)

    return {
        "query_identifier": q_key,
        "query_name": q_meta["name"],
        "sql_view": q_meta["sql_view"],
        "rows_examined": rows_examined,
        "rows_returned": rows_returned,
        "execution_time_ms": measured_ms,
        "latest_reading_timestamp": latest_ts,
        "exasol_connection_status": exasol_status,
        "sql_file_path": q_meta["sql_file_path"],
        "sql_query": q_meta["sql_query"].replace(":shipment_id", str(shipment_id)),
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Metrics represent real measured execution data. No synthetic throughput extrapolations.",
    }


@router.get("/benchmark-results")
async def get_benchmark_results() -> Dict[str, Any]:
    """
    Returns the reproducible multi-engine interval join benchmark results
    generated by `npm run benchmark:interval-join`.
    """
    # Look for reports/interval_join_benchmark.json in repo root
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
    json_path = os.path.join(repo_root, "reports", "interval_join_benchmark.json")

    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error reading benchmark results: {str(e)}",
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Benchmark report not found. Run 'npm run benchmark:interval-join' to generate it.",
    )
