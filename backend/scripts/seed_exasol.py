"""
Idempotent seed script for HandoffGuard Exasol database.

Populates HANDOFFGUARD schema with realistic synthetic pharmaceutical
cold-chain data. Safe to rerun — clears existing data first.

Usage (from backend/ directory):
    python scripts/seed_exasol.py

Environment variables required:
    DATABASE_ENGINE=exasol
    EXASOL_HOST, EXASOL_PORT, EXASOL_USER, EXASOL_PASSWORD, EXASOL_SCHEMA

Or run with defaults (Exasol Personal via Docker):
    EXASOL_HOST=localhost EXASOL_PORT=8563 EXASOL_USER=sys EXASOL_PASSWORD=exasol \\
        python scripts/seed_exasol.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.infrastructure.db.exasol_pool import ExasolPool

# ---------------------------------------------------------------------------
# Connect using env vars (bypass app settings if DATABASE_ENGINE != exasol)
# ---------------------------------------------------------------------------

HOST = os.environ.get("EXASOL_HOST", settings.exasol_host or "localhost")
PORT = int(os.environ.get("EXASOL_PORT", settings.exasol_port or 8563))
USER = os.environ.get("EXASOL_USER", settings.exasol_user or "sys")
PASSWORD = os.environ.get("EXASOL_PASSWORD", settings.exasol_password or "exasol")
SCHEMA = os.environ.get("EXASOL_SCHEMA", settings.exasol_schema or "HANDOFFGUARD")


def base_t() -> datetime:
    return datetime(2026, 10, 20, 6, 0, 0)  # naive UTC


def now_t() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Synchronous seed logic (runs in asyncio.to_thread)
# ---------------------------------------------------------------------------

def seed_sync(pool: ExasolPool) -> None:
    conn = pool._connect_sync()
    print(f"Connected to Exasol at {HOST}:{PORT} / schema {SCHEMA}")

    def run(sql: str, params=None):
        return conn.execute(sql, params or {}).fetchall()

    # ------------------------------------------------------------------
    # Utility: sequential ID generator
    # ------------------------------------------------------------------
    _id_counter = [1]

    def next_id() -> int:
        val = _id_counter[0]
        _id_counter[0] += 1
        return val

    def ts(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    # ------------------------------------------------------------------
    # Clear existing data (reverse FK order)
    # ------------------------------------------------------------------
    print("Clearing existing data...")
    for table in [
        "prevention_suggestions",
        "attribution_results",
        "excursions",
        "logger_readings",
        "logger_devices",
        "handoffs",
        "shipments",
        "products",
    ]:
        try:
            conn.execute(f"DELETE FROM HANDOFFGUARD.{table}")
        except Exception as e:
            print(f"  Skipped clearing {table}: {e}")

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------
    print("Seeding products...")
    VACCINE_ID, BLOOD_ID, INSULIN_ID = next_id(), next_id(), next_id()

    for pid, name, mn, mx, excl, tmc in [
        (VACCINE_ID, "VaxPro mRNA Booster (2C-8C)", 2.0, 8.0, 120, "Low"),
        (BLOOD_ID,   "CryoPlasma Fresh Frozen (-20C to -15C)", -20.0, -15.0, 60, "Medium"),
        (INSULIN_ID, "NovoInsulin Glargine (2C-8C)", 2.0, 8.0, 180, "Low"),
    ]:
        conn.execute(
            "INSERT INTO HANDOFFGUARD.products "
            "(product_id, name, min_temp_c, max_temp_c, allowed_excursion_minutes, thermal_mass_class) "
            "VALUES ({pid!d}, {name}, {mn}, {mx}, {excl!d}, {tmc})",
            {"pid": pid, "name": name, "mn": mn, "mx": mx, "excl": excl, "tmc": tmc},
        )

    # ------------------------------------------------------------------
    # Shipment 1: SHP-2026-0881 — mRNA Vaccine, major dock-dwell excursion
    # ------------------------------------------------------------------
    print("Seeding shipment 1 (SHP-2026-0881)...")
    SHP1_ID = next_id()
    B = base_t()
    conn.execute(
        "INSERT INTO HANDOFFGUARD.shipments "
        "(shipment_id, shipment_code, product_id, origin, destination, "
        " dispatched_at, expected_delivery_at, status) "
        "VALUES ({sid!d}, {code}, {pid!d}, {orig}, {dest}, {da}, {eda}, {stat})",
        {
            "sid": SHP1_ID, "code": "SHP-2026-0881", "pid": VACCINE_ID,
            "orig": "Hyderabad Pharma Hub", "dest": "Bengaluru Apollo Hospital",
            "da": ts(B), "eda": ts(B + timedelta(hours=14)), "stat": "delivered",
        },
    )

    # 5 Handoffs for Shipment 1
    H1_IDS = [next_id() for _ in range(5)]
    handoff_data = [
        (H1_IDS[0], SHP1_ID, 1, "pickup",   "Pharma Hub Warehouse",   "ColdFleet Reefer Truck A1",
         B,                    B + timedelta(hours=2),
         B + timedelta(minutes=5), B + timedelta(hours=1, minutes=55), 0.0, 25.0),
        (H1_IDS[1], SHP1_ID, 2, "transit",  "ColdFleet Reefer Truck A1", "Central Cross-Dock",
         B + timedelta(hours=2),  B + timedelta(hours=5),
         B + timedelta(hours=2),  B + timedelta(hours=5), 15.0, 0.0),
        # Overlaps H1_2 by 15 minutes
        (H1_IDS[2], SHP1_ID, 3, "transfer", "Central Cross-Dock",     "Kurnool Hub Staging",
         B + timedelta(hours=4, minutes=45), B + timedelta(hours=7),
         B + timedelta(hours=4, minutes=50), B + timedelta(hours=6, minutes=50), 0.0, 40.0),
        (H1_IDS[3], SHP1_ID, 4, "storage",  "Kurnool Hub Staging",    "Express Van Route 9",
         B + timedelta(hours=7),  B + timedelta(hours=11),
         B + timedelta(hours=7, minutes=10), B + timedelta(hours=10, minutes=55), -30.0, 85.0),
        (H1_IDS[4], SHP1_ID, 5, "delivery", "Express Van Route 9",    "Apollo Hospital Pharmacy",
         B + timedelta(hours=11), B + timedelta(hours=14),
         B + timedelta(hours=11, minutes=5), B + timedelta(hours=13, minutes=45), 0.0, 20.0),
    ]
    for (hid, sid, seq, htype, fp, tp, ws, we, rs, re, skew, dwell) in handoff_data:
        loc_map = {1: "Hyderabad Logistics Park", 2: "NH-44 Highway Transit",
                   3: "Kurnool Airport Terminal", 4: "Bengaluru Urban Depot Dock",
                   5: "Bengaluru Bannerghatta"}
        conn.execute(
            "INSERT INTO HANDOFFGUARD.handoffs "
            "(handoff_id, shipment_id, sequence_no, handoff_type, from_party, to_party, location, "
            " window_start_utc, window_end_utc, reported_start_utc, reported_end_utc, "
            " clock_skew_seconds, dwell_minutes) "
            "VALUES ({hid!d},{sid!d},{seq!d},{htype},{fp},{tp},{loc},"
            "        {ws},{we},{rs},{re},{skew},{dwell})",
            {
                "hid": hid, "sid": sid, "seq": seq, "htype": htype, "fp": fp, "tp": tp,
                "loc": loc_map[seq],
                "ws": ts(ws), "we": ts(we), "rs": ts(rs), "re": ts(re),
                "skew": skew, "dwell": dwell,
            },
        )

    # 2 Logger devices for Shipment 1
    LG1_ID, LG2_ID = next_id(), next_id()
    for lid, code, model, skew in [
        (LG1_ID, "TT-ULTRA-001", "TempTale Ultra BLE", 0.0),
        (LG2_ID, "CS-COLD-002",  "Sensitech ColdStream", 180.0),
    ]:
        conn.execute(
            "INSERT INTO HANDOFFGUARD.logger_devices "
            "(logger_id, device_code, model, firmware, assigned_shipment_id, clock_skew_seconds) "
            "VALUES ({lid!d},{code},{model},{fw},{sid!d},{skew})",
            {"lid": lid, "code": code, "model": model, "fw": "v2.3.1",
             "sid": SHP1_ID, "skew": skew},
        )

    # Temperature readings for Shipment 1 (every 5 min, 14 hours = 168 intervals)
    print("  Generating readings for shipment 1 (~340 rows)...")
    reading_id = next_id()
    curr = B
    end = B + timedelta(hours=14)
    readings_batch = []
    while curr <= end:
        h = (curr - B).total_seconds() / 3600.0
        temp1, temp2 = 4.5, 4.7
        if 3.0 <= h <= 3.3:
            temp1, temp2 = 8.4, 8.5          # Brief naive-baseline breach
        elif 8.0 <= h <= 10.0:
            temp1 = 14.2 + (0.6 if h > 8.5 else 0.0)
            temp2 = 14.5 + (0.5 if h > 8.5 else 0.0)
        elif 10.0 < h <= 10.8:
            temp1 = 10.5 - (h - 10.0) * 5.0
            temp2 = 10.7 - (h - 10.0) * 5.0

        is_gap = 5.2 <= h <= 6.5
        if not is_gap:
            conn.execute(
                "INSERT INTO HANDOFFGUARD.logger_readings "
                "(reading_id, logger_id, reading_at_utc, temperature_c, battery_pct) "
                "VALUES ({rid!d},{lid!d},{rat},{tc},{bp})",
                {"rid": reading_id, "lid": LG1_ID, "rat": ts(curr),
                 "tc": round(temp1, 2), "bp": 94.0},
            )
            reading_id += 1

        # Logger 2: clock is 180 s ahead → raw timestamp is curr - 180 s
        conn.execute(
            "INSERT INTO HANDOFFGUARD.logger_readings "
            "(reading_id, logger_id, reading_at_utc, temperature_c, battery_pct) "
            "VALUES ({rid!d},{lid!d},{rat},{tc},{bp})",
            {"rid": reading_id, "lid": LG2_ID,
             "rat": ts(curr - timedelta(seconds=180)),
             "tc": round(temp2, 2), "bp": 88.0},
        )
        reading_id += 1
        curr += timedelta(minutes=5)

    # Excursion for Shipment 1
    EXC1_ID = next_id()
    conn.execute(
        "INSERT INTO HANDOFFGUARD.excursions "
        "(excursion_id, shipment_id, product_id, started_at_utc, ended_at_utc, "
        " min_temp_c, max_temp_c, peak_temp_c, duration_minutes, severity, "
        " detected_by, ground_truth_handoff_id, ground_truth_cause) "
        "VALUES ({eid!d},{sid!d},{pid!d},{sa},{ea},{mn},{mx},{pk},{dm},{sev},{db},{gt},{gc})",
        {
            "eid": EXC1_ID, "sid": SHP1_ID, "pid": VACCINE_ID,
            "sa": ts(B + timedelta(hours=3)), "ea": ts(B + timedelta(hours=10, minutes=45)),
            "mn": 8.1, "mx": 14.8, "pk": 14.8, "dm": 465.0, "sev": "critical",
            "db": "system",
            "gt": H1_IDS[3],
            "gc": "Reefer truck refrigeration unit shut down on depot apron during shift turnover.",
        },
    )

    # ------------------------------------------------------------------
    # Shipment 2: SHP-2026-0904 — CryoPlasma, two excursion events
    # ------------------------------------------------------------------
    print("Seeding shipment 2 (SHP-2026-0904)...")
    SHP2_ID = next_id()
    B2 = B + timedelta(days=1)
    conn.execute(
        "INSERT INTO HANDOFFGUARD.shipments "
        "(shipment_id, shipment_code, product_id, origin, destination, "
        " dispatched_at, expected_delivery_at, status) "
        "VALUES ({sid!d},{code},{pid!d},{orig},{dest},{da},{eda},{stat})",
        {
            "sid": SHP2_ID, "code": "SHP-2026-0904", "pid": BLOOD_ID,
            "orig": "Mumbai Blood Bank Central", "dest": "Pune Ruby Hall Clinic",
            "da": ts(B2), "eda": ts(B2 + timedelta(hours=8)), "stat": "delivered",
        },
    )
    H2_IDS = [next_id() for _ in range(5)]
    for seq, (htype, fp, tp, loc, ws_delta, we_delta, skew, dwell) in enumerate([
        ("pickup",   "Mumbai Blood Bank",        "CryoExpress Logistics",       "Parel Central Mumbai",         timedelta(), timedelta(hours=1, minutes=30), 0.0, 15.0),
        ("transit",  "CryoExpress Logistics",    "Expressway Checkpost",         "Mumbai-Pune Expressway",       timedelta(hours=1, minutes=30), timedelta(hours=4), 0.0, 0.0),
        ("transfer", "Expressway Checkpost",     "Pune City Feeder",             "Toll Plaza Intermediate Dock", timedelta(hours=4), timedelta(hours=5), 0.0, 30.0),
        ("delivery", "Pune City Feeder",         "Ruby Hall Transfusion Center", "Pune Dhole Patil Rd",          timedelta(hours=5), timedelta(hours=7), 0.0, 15.0),
        ("storage",  "Ruby Hall Transfusion Center", "Hospital Deep-Freeze",    "Hospital Basement Vault",      timedelta(hours=7), timedelta(hours=8), 0.0, 10.0),
    ], start=1):
        conn.execute(
            "INSERT INTO HANDOFFGUARD.handoffs "
            "(handoff_id, shipment_id, sequence_no, handoff_type, from_party, to_party, location, "
            " window_start_utc, window_end_utc, reported_start_utc, reported_end_utc, "
            " clock_skew_seconds, dwell_minutes) "
            "VALUES ({hid!d},{sid!d},{seq!d},{htype},{fp},{tp},{loc},"
            "        {ws},{we},{rs},{re},{skew},{dwell})",
            {
                "hid": H2_IDS[seq-1], "sid": SHP2_ID, "seq": seq,
                "htype": htype, "fp": fp, "tp": tp, "loc": loc,
                "ws": ts(B2 + ws_delta), "we": ts(B2 + we_delta),
                "rs": ts(B2 + ws_delta), "re": ts(B2 + we_delta),
                "skew": skew, "dwell": dwell,
            },
        )
    LG3_ID = next_id()
    conn.execute(
        "INSERT INTO HANDOFFGUARD.logger_devices "
        "(logger_id, device_code, model, firmware, assigned_shipment_id, clock_skew_seconds) "
        "VALUES ({lid!d},{code},{model},{fw},{sid!d},{skew})",
        {"lid": LG3_ID, "code": "CT-ULTRA-003", "model": "CryoTag Ultra",
         "fw": "v1.8.0", "sid": SHP2_ID, "skew": 0.0},
    )
    curr = B2
    end = B2 + timedelta(hours=8)
    while curr <= end:
        h = (curr - B2).total_seconds() / 3600.0
        temp = -18.5
        if 2.0 <= h <= 2.8:  temp = -12.0
        elif 4.2 <= h <= 4.7: temp = -11.5
        conn.execute(
            "INSERT INTO HANDOFFGUARD.logger_readings "
            "(reading_id, logger_id, reading_at_utc, temperature_c, battery_pct) "
            "VALUES ({rid!d},{lid!d},{rat},{tc},{bp})",
            {"rid": reading_id, "lid": LG3_ID, "rat": ts(curr), "tc": temp, "bp": 98.0},
        )
        reading_id += 1
        curr += timedelta(minutes=5)

    for eid_offset, (exc_start, exc_end, pk, dur, sev, gt_h, gc) in enumerate([
        (B2 + timedelta(hours=2),       B2 + timedelta(hours=2, minutes=48),
         -12.0, 48.0, "medium", H2_IDS[1],
         "Dry ice sublimation accelerated due to compromised secondary seal."),
        (B2 + timedelta(hours=4, minutes=12), B2 + timedelta(hours=4, minutes=42),
         -11.5, 30.0, "medium", H2_IDS[2],
         "Uninsulated transfer on open dock during vehicle change."),
    ]):
        conn.execute(
            "INSERT INTO HANDOFFGUARD.excursions "
            "(excursion_id, shipment_id, product_id, started_at_utc, ended_at_utc, "
            " min_temp_c, max_temp_c, peak_temp_c, duration_minutes, severity, "
            " detected_by, ground_truth_handoff_id, ground_truth_cause) "
            "VALUES ({eid!d},{sid!d},{pid!d},{sa},{ea},{mn},{mx},{pk},{dm},{sev},{db},{gt},{gc})",
            {
                "eid": next_id(), "sid": SHP2_ID, "pid": BLOOD_ID,
                "sa": ts(exc_start), "ea": ts(exc_end),
                "mn": -20.0, "mx": pk, "pk": pk, "dm": dur, "sev": sev,
                "db": "system", "gt": gt_h, "gc": gc,
            },
        )

    # ------------------------------------------------------------------
    # Shipment 3: SHP-2026-1042 — Insulin, in-transit (prevention screen)
    # ------------------------------------------------------------------
    print("Seeding shipment 3 (SHP-2026-1042 — in_transit)...")
    SHP3_ID = next_id()
    N = now_t()
    conn.execute(
        "INSERT INTO HANDOFFGUARD.shipments "
        "(shipment_id, shipment_code, product_id, origin, destination, "
        " dispatched_at, expected_delivery_at, status) "
        "VALUES ({sid!d},{code},{pid!d},{orig},{dest},{da},{eda},{stat})",
        {
            "sid": SHP3_ID, "code": "SHP-2026-1042", "pid": INSULIN_ID,
            "orig": "Ahmedabad Manufacturing SEZ", "dest": "Jaipur SMS Medical College",
            "da": ts(N - timedelta(hours=2)),
            "eda": ts(N + timedelta(hours=10)),
            "stat": "in_transit",
        },
    )
    H3_IDS = [next_id() for _ in range(5)]
    for seq, (htype, fp, tp, loc, ws_delta, we_delta, skew, dwell) in enumerate([
        ("pickup",   "Ahmedabad SEZ Plant",      "NorthLine Express Truck 4", "Ahmedabad Cargo Terminal",             timedelta(hours=-2), timedelta(hours=-1),  0.0,  20.0),
        ("transit",  "NorthLine Express Truck 4","Udaipur Cross-Dock",        "Rajasthan Corridor",                   timedelta(hours=-1), timedelta(hours=3),   0.0,   0.0),
        ("storage",  "Udaipur Cross-Dock",       "Jaipur Route Van",          "Udaipur Distribution Center Apron",    timedelta(hours=3),  timedelta(hours=5),   0.0,  75.0),
        ("transit",  "Jaipur Route Van",         "Jaipur City Hub",           "Jaipur Bypass",                        timedelta(hours=5),  timedelta(hours=8),   0.0,   0.0),
        ("delivery", "Jaipur City Hub",          "SMS Medical College Pharmacy","Jaipur Central",                     timedelta(hours=8),  timedelta(hours=10),  0.0,  15.0),
    ], start=1):
        conn.execute(
            "INSERT INTO HANDOFFGUARD.handoffs "
            "(handoff_id, shipment_id, sequence_no, handoff_type, from_party, to_party, location, "
            " window_start_utc, window_end_utc, reported_start_utc, reported_end_utc, "
            " clock_skew_seconds, dwell_minutes) "
            "VALUES ({hid!d},{sid!d},{seq!d},{htype},{fp},{tp},{loc},"
            "        {ws},{we},{rs},{re},{skew},{dwell})",
            {
                "hid": H3_IDS[seq-1], "sid": SHP3_ID, "seq": seq,
                "htype": htype, "fp": fp, "tp": tp, "loc": loc,
                "ws": ts(N + ws_delta), "we": ts(N + we_delta),
                "rs": ts(N + ws_delta), "re": ts(N + we_delta),
                "skew": skew, "dwell": dwell,
            },
        )
    LG4_ID = next_id()
    conn.execute(
        "INSERT INTO HANDOFFGUARD.logger_devices "
        "(logger_id, device_code, model, firmware, assigned_shipment_id, clock_skew_seconds) "
        "VALUES ({lid!d},{code},{model},{fw},{sid!d},{skew})",
        {"lid": LG4_ID, "code": "TT-GEO-004", "model": "TempTale GEO LTE",
         "fw": "v3.1.0", "sid": SHP3_ID, "skew": 45.0},
    )
    curr = N - timedelta(hours=2)
    while curr <= N:
        conn.execute(
            "INSERT INTO HANDOFFGUARD.logger_readings "
            "(reading_id, logger_id, reading_at_utc, temperature_c, battery_pct) "
            "VALUES ({rid!d},{lid!d},{rat},{tc},{bp})",
            {"rid": reading_id, "lid": LG4_ID, "rat": ts(curr), "tc": 4.8, "bp": 99.0},
        )
        reading_id += 1
        curr += timedelta(minutes=5)

    print("Committing...")
    conn.commit()
    conn.close()
    print("\n✅ Seed complete!")
    print(f"   Products  : 3")
    print(f"   Shipments : 3")
    print(f"   Handoffs  : 15")
    print(f"   Loggers   : 4")
    print(f"   Readings  : ~{reading_id} rows")
    print(f"   Excursions: 3")


async def seed():
    pool = ExasolPool(
        host=HOST, port=PORT, user=USER, password=PASSWORD, schema=SCHEMA,
        encryption=False,
    )
    print(f"Connecting to Exasol Personal at {HOST}:{PORT} ...")
    await asyncio.to_thread(seed_sync, pool)


if __name__ == "__main__":
    asyncio.run(seed())
