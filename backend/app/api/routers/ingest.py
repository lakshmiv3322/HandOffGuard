"""
Logger File Ingestion Router.

Accepts CSV uploads from disparate cold-chain participants, normalizes
them to standard UTC telemetry, and persists them into the database.
Handles raw CSV, text/csv, multipart/form-data, or JSON payloads without
requiring external binary multipart drivers.
"""

from __future__ import annotations

import re
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import is_exasol
from app.core.services.ingestion_service import IngestionService

router = APIRouter(prefix="/api/ingest", tags=["Ingestion"])


def _extract_csv_text(content_type: str, body: bytes) -> tuple[str, str]:
    """Extract filename and raw text from request body."""
    filename = "upload.csv"

    if "multipart/form-data" in content_type and "boundary=" in content_type:
        boundary_str = content_type.split("boundary=")[-1].split(";")[0].strip('"\'')
        boundary = boundary_str.encode("utf-8")
        parts = body.split(b"--" + boundary)
        for part in parts:
            if b"filename=" in part:
                headers_data, _, file_data = part.partition(b"\r\n\r\n")
                # Extract filename if present
                m = re.search(r'filename=["\']?([^"\';\r\n]+)', headers_data.decode("utf-8", errors="ignore"))
                if m:
                    filename = m.group(1).strip()
                clean_body = file_data.rstrip(b"\r\n--")
                return filename, clean_body.decode("utf-8-sig", errors="replace")

    # If raw CSV, text/plain, or json
    text = body.decode("utf-8-sig", errors="replace").strip()
    if text.startswith("{") and "csv" in text:
        import json
        try:
            payload = json.loads(text)
            return payload.get("filename", filename), payload.get("csv", payload.get("content", text))
        except Exception:
            pass

    return filename, text


@router.post("/logger-file")
async def ingest_logger_file(request: Request) -> Dict[str, Any]:
    """
    Ingest multi-format CSV logger files from warehouse, reefer, or last-mile couriers.

    Automatically detects format, parses and normalizes timestamps to UTC,
    converts temperatures to Celsius, validates limits, and stores readings.

    IMPORTANT: Readings are stored without handoff IDs. Association to custody
    windows is derived dynamically via Exasol interval join.
    """
    content_type = request.headers.get("content-type", "")
    body = await request.body()

    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body is empty.",
        )

    filename, content_str = _extract_csv_text(content_type, body)
    report = IngestionService.parse_csv(content_str)

    if report["rows_accepted"] == 0:
        return {
            "status": "failed",
            "filename": filename,
            "detected_format": report["detected_format"],
            "rows_received": report["rows_received"],
            "rows_accepted": 0,
            "rows_rejected": report["rows_rejected"],
            "rejection_reasons": report["rejection_reasons"],
            "logger_ids_updated": [],
            "readings_inserted": 0,
        }

    readings_to_insert = report["readings"]
    inserted_count = 0
    updated_loggers = []

    if is_exasol():
        from app.infrastructure.db.exasol_pool import get_pool
        pool = get_pool()

        for device_code in report["logger_codes"]:
            chk = await pool.execute(
                "SELECT logger_id FROM HANDOFFGUARD.logger_devices WHERE device_code = {code}",
                {"code": device_code},
            )
            if chk:
                lid = int(chk[0].get("LOGGER_ID") or chk[0].get("logger_id"))
            else:
                max_row = await pool.execute("SELECT COALESCE(MAX(logger_id), 0) + 1 AS next_id FROM HANDOFFGUARD.logger_devices")
                lid = int(max_row[0].get("NEXT_ID") or max_row[0].get("next_id"))
                await pool.execute(
                    "INSERT INTO HANDOFFGUARD.logger_devices (logger_id, device_code, model, assigned_shipment_id) "
                    "VALUES ({lid!d}, {code}, {model}, 1)",
                    {"lid": lid, "code": device_code, "model": "Ingested Device"},
                )
            updated_loggers.append(lid)

            dev_readings = [r for r in readings_to_insert if r["device_code"] == device_code]
            for r in dev_readings:
                max_r = await pool.execute("SELECT COALESCE(MAX(reading_id), 0) + 1 AS next_id FROM HANDOFFGUARD.logger_readings")
                rid = int(max_r[0].get("NEXT_ID") or max_r[0].get("next_id"))
                await pool.execute(
                    "INSERT INTO HANDOFFGUARD.logger_readings (reading_id, logger_id, reading_at_utc, temperature_c, battery_pct) "
                    "VALUES ({rid!d}, {lid!d}, {ts}, {tc}, {bp})",
                    {
                        "rid": rid,
                        "lid": lid,
                        "ts": r["reading_at_utc"].strftime("%Y-%m-%d %H:%M:%S"),
                        "tc": r["temperature_c"],
                        "bp": r["battery_pct"],
                    },
                )
                inserted_count += 1
    else:
        # SQLite storage (fallback)
        from app.api.deps import get_db_backend
        from app.infrastructure.db.dev_db import DevDatabaseBackend, LoggerORM, TemperatureReadingORM
        from sqlalchemy import select

        backend = get_db_backend()
        if isinstance(backend, DevDatabaseBackend):
            async with backend.get_session() as session:
                for device_code in report["logger_codes"]:
                    res = await session.execute(
                        select(LoggerORM).where(LoggerORM.device_type == device_code)
                    )
                    logger_obj = res.scalar_one_or_none()
                    if not logger_obj:
                        logger_obj = LoggerORM(
                            device_type=device_code,
                            assigned_shipment_id=1,
                            sampling_interval_seconds=300,
                            clock_skew_seconds=0.0,
                            data_quality_flag="good",
                        )
                        session.add(logger_obj)
                        await session.flush()
                    updated_loggers.append(logger_obj.logger_id)

                    dev_readings = [r for r in readings_to_insert if r["device_code"] == device_code]
                    for r in dev_readings:
                        session.add(
                            TemperatureReadingORM(
                                logger_id=logger_obj.logger_id,
                                recorded_at_utc=r["reading_at_utc"],
                                temperature_c=r["temperature_c"],
                                battery_pct=r["battery_pct"],
                                quality_flag="good",
                            )
                        )
                        inserted_count += 1
                await session.commit()

    return {
        "status": "success",
        "filename": filename,
        "detected_format": report["detected_format"],
        "rows_received": report["rows_received"],
        "rows_accepted": report["rows_accepted"],
        "rows_rejected": report["rows_rejected"],
        "rejection_reasons": report["rejection_reasons"],
        "logger_ids_updated": updated_loggers,
        "readings_inserted": inserted_count,
        "contract_verified": "NO handoff_id assigned",
    }
