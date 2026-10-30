"""Unit tests for multi-format logger ingestion service."""

import pytest
from app.core.services.ingestion_service import IngestionService


def test_format_a_detection_and_parsing():
    content = """device_code,timestamp,temp_c,battery,timezone
TT-ULTRA-001,2026-10-20T06:00:00,4.5,94,UTC
TT-ULTRA-001,2026-10-20T06:05:00,4.8,93,UTC
"""
    report = IngestionService.parse_csv(content)
    assert report["detected_format"] == "Format A (Warehouse)"
    assert report["rows_received"] == 2
    assert report["rows_accepted"] == 2
    assert report["rows_rejected"] == 0
    assert len(report["readings"]) == 2
    r0 = report["readings"][0]
    assert r0["device_code"] == "TT-ULTRA-001"
    assert r0["temperature_c"] == 4.5
    assert r0["battery_pct"] == 94.0
    assert "handoff_id" not in r0  # CRITICAL INVARIANT


def test_format_b_reefer_timezone_normalization():
    content = """logger_id,reading_time,temperature,battery_pct,timezone
CS-COLD-002,2026-10-20 11:30:00,4.8,88%,Asia/Kolkata
"""
    report = IngestionService.parse_csv(content)
    assert report["detected_format"] == "Format B (Reefer Operator)"
    assert report["rows_accepted"] == 1
    r = report["readings"][0]
    # 11:30 IST is 06:00 UTC
    assert r["reading_at_utc"].hour == 6
    assert r["reading_at_utc"].minute == 0
    assert r["temperature_c"] == 4.8
    assert r["battery_pct"] == 88.0
    assert "handoff_id" not in r  # CRITICAL INVARIANT


def test_format_c_lastmile_date_time_split():
    content = """Device,Date,Time,Temp,Battery,Timezone
TT-GEO-004,20-10-2026,17:00:00,5.1,98%,+05:30
"""
    report = IngestionService.parse_csv(content)
    assert report["detected_format"] == "Format C (Last-Mile Agent)"
    assert report["rows_accepted"] == 1
    r = report["readings"][0]
    # 17:00 +05:30 is 11:30 UTC
    assert r["reading_at_utc"].hour == 11
    assert r["reading_at_utc"].minute == 30
    assert r["temperature_c"] == 5.1
    assert r["battery_pct"] == 98.0
    assert "handoff_id" not in r  # CRITICAL INVARIANT


def test_rejection_of_malformed_temperature_and_missing_fields():
    content = """device_code,timestamp,temp_c,battery,timezone
TT-01,2026-10-20T06:00:00,INVALID_TEMP,94,UTC
TT-01,2026-10-20T06:05:00,5.0,200%,UTC
,2026-10-20T06:10:00,5.0,90,UTC
"""
    report = IngestionService.parse_csv(content)
    assert report["rows_received"] == 3
    assert report["rows_accepted"] == 0
    assert report["rows_rejected"] == 3
    assert len(report["rejection_reasons"]) == 3
