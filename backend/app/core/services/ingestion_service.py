"""
Multi-Format Logger Ingestion Service.

Parses heterogeneous logger data formats submitted by different supply-chain partners:
- Format A: Warehouse format (device_code, timestamp, temp_c, battery, timezone)
- Format B: Reefer operator format (logger_id, reading_time, temperature, battery_pct, timezone)
- Format C: Last-mile courier format (Device, Date, Time, Temp, Battery, Timezone)

Normalizes:
- Timestamps to UTC
- Temperatures to Celsius (numeric float)
- Battery levels (percentage float 0-100)
Validates ranges and rejects malformed rows with clear explanations.

CRITICAL INVARIANT:
- NO handoff_id is assigned or stored.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple


class IngestionService:

    @staticmethod
    def detect_format(headers: List[str]) -> str:
        clean_headers = [h.strip().lower() for h in headers]
        header_set = set(clean_headers)

        if {"device_code", "timestamp", "temp_c"}.issubset(header_set):
            return "Format A (Warehouse)"
        if {"logger_id", "reading_time", "temperature"}.issubset(header_set):
            return "Format B (Reefer Operator)"
        if {"device", "date", "time", "temp"}.issubset(header_set):
            return "Format C (Last-Mile Agent)"

        # Fuzzy detection
        if any("device_code" in h for h in clean_headers):
            return "Format A (Warehouse)"
        if any("reading_time" in h for h in clean_headers):
            return "Format B (Reefer Operator)"
        if any(h in ["device", "date"] for h in clean_headers) and "time" in clean_headers:
            return "Format C (Last-Mile Agent)"

        return "Unknown Format"

    @classmethod
    def parse_csv(cls, file_content: str) -> Dict[str, Any]:
        reader = csv.reader(io.StringIO(file_content.strip()))
        rows = list(reader)

        if not rows:
            return {
                "detected_format": "Empty File",
                "rows_received": 0,
                "rows_accepted": 0,
                "rows_rejected": 0,
                "rejection_reasons": ["The uploaded file is empty."],
                "logger_codes": [],
                "readings": [],
            }

        headers = [h.strip() for h in rows[0]]
        detected_format = cls.detect_format(headers)

        if detected_format == "Unknown Format":
            return {
                "detected_format": detected_format,
                "rows_received": len(rows) - 1,
                "rows_accepted": 0,
                "rows_rejected": len(rows) - 1,
                "rejection_reasons": [
                    f"Unrecognized CSV header format: {', '.join(headers)}. "
                    "Expected Format A (device_code, timestamp, temp_c), "
                    "Format B (logger_id, reading_time, temperature), or "
                    "Format C (Device, Date, Time, Temp)."
                ],
                "logger_codes": [],
                "readings": [],
            }

        header_indices = {h.lower(): idx for idx, h in enumerate(headers)}
        rows_accepted = 0
        rows_rejected = 0
        rejection_reasons = []
        readings: List[Dict[str, Any]] = []
        logger_codes = set()

        for line_num, row in enumerate(rows[1:], start=2):
            if not row or all(not col.strip() for col in row):
                continue  # skip empty lines

            try:
                device, dt_utc, temp_c, battery_pct = cls._parse_row(
                    row, header_indices, detected_format
                )

                # Validation checks
                if temp_c < -273.15 or temp_c > 100.0:
                    raise ValueError(f"Temperature {temp_c}°C is outside realistic physical limits (-273.15°C to 100°C).")
                if battery_pct is not None and (battery_pct < 0 or battery_pct > 100):
                    raise ValueError(f"Battery level {battery_pct}% is invalid (must be 0-100%).")

                readings.append({
                    "device_code": device,
                    "reading_at_utc": dt_utc,
                    "temperature_c": temp_c,
                    "battery_pct": battery_pct,
                })
                logger_codes.add(device)
                rows_accepted += 1

            except Exception as e:
                rows_rejected += 1
                rejection_reasons.append(f"Row {line_num}: {str(e)}")

        return {
            "detected_format": detected_format,
            "rows_received": len(rows) - 1,
            "rows_accepted": rows_accepted,
            "rows_rejected": rows_rejected,
            "rejection_reasons": rejection_reasons,
            "logger_codes": sorted(list(logger_codes)),
            "readings": readings,
        }

    @classmethod
    def _parse_row(
        cls, row: List[str], h_idx: Dict[str, int], fmt: str
    ) -> Tuple[str, datetime, float, float | None]:
        def get_val(key_candidates: List[str]) -> str | None:
            for k in key_candidates:
                if k.lower() in h_idx:
                    idx = h_idx[k.lower()]
                    if idx < len(row):
                        return row[idx].strip()
            return None

        # 1. Device Code
        device = get_val(["device_code", "logger_id", "device"])
        if not device:
            raise ValueError("Missing device/logger identifier column value.")

        # 2. Timezone
        tz_str = get_val(["timezone", "tz"]) or "UTC"

        # 3. Timestamp parsing
        dt_utc: datetime
        if fmt == "Format C (Last-Mile Agent)":
            d_val = get_val(["date"])
            t_val = get_val(["time"])
            if not d_val or not t_val:
                raise ValueError("Missing Date or Time value in last-mile format.")
            dt_str = f"{d_val} {t_val}"
            dt_utc = cls._parse_datetime(dt_str, tz_str)
        else:
            ts_val = get_val(["timestamp", "reading_time"])
            if not ts_val:
                raise ValueError("Missing timestamp value.")
            dt_utc = cls._parse_datetime(ts_val, tz_str)

        # 4. Temperature parsing
        temp_val = get_val(["temp_c", "temperature", "temp"])
        if not temp_val:
            raise ValueError("Missing temperature value.")
        temp_c = cls._parse_temperature(temp_val)

        # 5. Battery parsing
        bat_val = get_val(["battery", "battery_pct"])
        battery_pct = cls._parse_battery(bat_val) if bat_val else None

        return device, dt_utc, temp_c, battery_pct

    @classmethod
    def _parse_datetime(cls, dt_str: str, tz_str: str) -> datetime:
        dt_str = dt_str.replace("T", " ").strip()
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%Y/%m/%d %H:%M:%S",
        ]
        parsed_dt: datetime | None = None
        for f in formats:
            try:
                parsed_dt = datetime.strptime(dt_str, f)
                break
            except ValueError:
                continue

        if not parsed_dt:
            raise ValueError(f"Unparseable datetime string: '{dt_str}'.")

        # Normalize timezone to UTC
        tz_norm = tz_str.upper().strip()
        if tz_norm in ["UTC", "GMT", "Z"]:
            return parsed_dt.replace(tzinfo=None)
        elif tz_norm in ["ASIA/KOLKATA", "IST", "+05:30", "+0530"]:
            return parsed_dt - timedelta(hours=5, minutes=30)
        elif re.match(r"^[+-]\d{2}:?\d{2}$", tz_str.strip()):
            sign = 1 if tz_str.startswith("+") else -1
            clean_tz = tz_str.strip().lstrip("+-").replace(":", "")
            hours = int(clean_tz[:2])
            mins = int(clean_tz[2:]) if len(clean_tz) >= 4 else 0
            offset = timedelta(hours=sign * hours, minutes=sign * mins)
            return parsed_dt - offset

        # Default naive UTC assumption
        return parsed_dt

    @staticmethod
    def _parse_temperature(temp_str: str) -> float:
        clean = re.sub(r"[^\d.-]", "", temp_str)
        try:
            return float(clean)
        except ValueError:
            raise ValueError(f"Unparseable temperature value: '{temp_str}'.")

    @staticmethod
    def _parse_battery(bat_str: str) -> float | None:
        if not bat_str:
            return None
        clean = re.sub(r"[^\d.]", "", bat_str)
        try:
            return float(clean)
        except ValueError:
            return None
