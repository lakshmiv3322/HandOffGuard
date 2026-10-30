"""
HandoffGuard — Exasol Database Initialization & Rich Demo Seeder
ExaThon India 2026 | Pharmaceutical Cold-Chain Attribution

Connects to Exasol using 'pyexasol' with environment variables:
  EXASOL_HOST     (default: localhost)
  EXASOL_PORT     (default: 8563)
  EXASOL_USER     (default: sys)
  EXASOL_PASSWORD (default: exasol)
  EXASOL_SCHEMA   (default: HANDOFFGUARD)

Actions:
1. Executes schema, table, and view definitions (from setup_exasol.sql).
2. Seeds products, shipments, handoffs, logger devices, and excursions.
3. Automatically generates and pushes 5,000+ sample IoT temperature logs into Exasol
   so the quality manager dashboard has rich telemetry to display immediately.
4. Idempotent: Clears prior demo records cleanly before re-seeding.

IMPORTANT CONSTRAINT:
  logger_readings has NO handoff_id column.
  Handoff association is derived strictly via interval join on time.
"""

from __future__ import annotations

import os
import sys
import random
from datetime import datetime, timedelta

HOST = os.environ.get("EXASOL_HOST", "localhost")
PORT = int(os.environ.get("EXASOL_PORT", 8563))
USER = os.environ.get("EXASOL_USER", "sys")
PASSWORD = os.environ.get("EXASOL_PASSWORD", "exasol")
SCHEMA = os.environ.get("EXASOL_SCHEMA", "HANDOFFGUARD")


def get_connection():
    try:
        import pyexasol
    except ImportError:
        print("ERROR: pyexasol is not installed. Please run: pip install pyexasol")
        sys.exit(1)

    print(f"Connecting to Exasol at {HOST}:{PORT} (user: {USER}, schema: {SCHEMA})...")
    try:
        conn = pyexasol.connect(
            dsn=f"{HOST}:{PORT}",
            user=USER,
            password=PASSWORD,
            schema=SCHEMA,
            websocket_sslopt={"cert_reqs": 0},
        )
        print("Successfully connected to Exasol.")
        return conn
    except Exception as exc:
        print(f"Failed to connect to Exasol at {HOST}:{PORT}: {exc}")
        print("Please check that Exasol Docker container is running and port 8563 is forwarded.")
        sys.exit(1)


def init_schema(conn):
    sql_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup_exasol.sql")
    if not os.path.exists(sql_file):
        print(f"ERROR: Cannot find {sql_file}")
        sys.exit(1)

    print(f"Executing database setup from {sql_file}...")
    with open(sql_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into discrete statements separated by semicolons
    statements = [s.strip() for s in content.split(";") if s.strip()]
    for stmt in statements:
        # Skip pure comments or blank lines
        lines = [line for line in stmt.splitlines() if not line.strip().startswith("--")]
        clean_stmt = "\n".join(lines).strip()
        if clean_stmt:
            try:
                conn.execute(clean_stmt)
            except Exception as e:
                print(f"Notice on statement: {e}")
    print("Schema and views initialized.")


def seed_data(conn):
    print("Clearing prior demo records...")
    for tbl in [
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
            conn.execute(f"DELETE FROM HANDOFFGUARD.{tbl}")
        except Exception:
            pass

    def ts(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Products
    print("Seeding pharmaceutical products...")
    products = [
        (1, "VaxPro mRNA Booster (2C-8C)", 2.0, 8.0, 120, "Low"),
        (2, "CryoPlasma Fresh Frozen (-20C to -15C)", -20.0, -15.0, 60, "Medium"),
        (3, "NovoInsulin Glargine (2C-8C)", 2.0, 8.0, 180, "Low"),
        (4, "ImmunoGlobulin IVIG (2C-8C)", 2.0, 8.0, 90, "Low"),
    ]
    for pid, name, mn, mx, excl, tmc in products:
        conn.execute(
            "INSERT INTO HANDOFFGUARD.products "
            "(product_id, name, min_temp_c, max_temp_c, allowed_excursion_minutes, thermal_mass_class) "
            "VALUES ({pid!d}, {name}, {mn}, {mx}, {excl!d}, {tmc})",
            {"pid": pid, "name": name, "mn": mn, "mx": mx, "excl": excl, "tmc": tmc},
        )

    base_t = datetime(2026, 10, 20, 6, 0, 0)

    # 2. Shipments
    print("Seeding shipments & multi-modal handoffs...")
    shipments = [
        (1, "SHP-2026-0881", 1, "Hyderabad Pharma Hub", "Bengaluru Apollo Hospital",
         base_t, base_t + timedelta(hours=14), "delivered"),
        (2, "SHP-2026-0904", 2, "Mumbai Blood Bank Central", "Pune Ruby Hall Clinic",
         base_t + timedelta(days=1), base_t + timedelta(days=1, hours=8), "delivered"),
        (3, "SHP-2026-1042", 3, "Ahmedabad Manufacturing SEZ", "Jaipur SMS Medical College",
         datetime.utcnow() - timedelta(hours=2), datetime.utcnow() + timedelta(hours=10), "in_transit"),
        (4, "SHP-2026-1120", 4, "Chennai Biotech Park", "Kochi Aster Medcity",
         base_t + timedelta(days=2), base_t + timedelta(days=2, hours=12), "delivered"),
    ]
    for sid, code, pid, orig, dest, disp, exp, stat in shipments:
        conn.execute(
            "INSERT INTO HANDOFFGUARD.shipments "
            "(shipment_id, shipment_code, product_id, origin, destination, dispatched_at, expected_delivery_at, status) "
            "VALUES ({sid!d}, {code}, {pid!d}, {orig}, {dest}, {disp}, {exp}, {stat})",
            {"sid": sid, "code": code, "pid": pid, "orig": orig, "dest": dest,
             "disp": ts(disp), "exp": ts(exp), "stat": stat},
        )

    # 3. Handoffs for all shipments
    handoffs = [
        # Shipment 1 (Hyderabad -> Bengaluru)
        (101, 1, 1, "pickup", "Pharma Hub Warehouse", "ColdFleet Reefer Truck A1", "Hyderabad Logistics Park",
         base_t, base_t + timedelta(hours=2), base_t + timedelta(minutes=5), base_t + timedelta(hours=1, minutes=55), 0.0, 25.0),
        (102, 1, 2, "transit", "ColdFleet Reefer Truck A1", "Central Cross-Dock", "NH-44 Highway Transit",
         base_t + timedelta(hours=2), base_t + timedelta(hours=5), base_t + timedelta(hours=2), base_t + timedelta(hours=5), 15.0, 0.0),
        (103, 1, 3, "transfer", "Central Cross-Dock", "Kurnool Hub Staging", "Kurnool Airport Terminal",
         base_t + timedelta(hours=4, minutes=45), base_t + timedelta(hours=7), base_t + timedelta(hours=4, minutes=50), base_t + timedelta(hours=6, minutes=50), 0.0, 40.0),
        (104, 1, 4, "storage", "Kurnool Hub Staging", "Express Van Route 9", "Bengaluru Urban Depot Dock",
         base_t + timedelta(hours=7), base_t + timedelta(hours=11), base_t + timedelta(hours=7, minutes=10), base_t + timedelta(hours=10, minutes=55), -30.0, 85.0),
        (105, 1, 5, "delivery", "Express Van Route 9", "Apollo Hospital Pharmacy", "Bengaluru Bannerghatta",
         base_t + timedelta(hours=11), base_t + timedelta(hours=14), base_t + timedelta(hours=11, minutes=5), base_t + timedelta(hours=13, minutes=45), 0.0, 20.0),

        # Shipment 2 (Mumbai -> Pune)
        (201, 2, 1, "pickup", "Mumbai Blood Bank", "CryoExpress Logistics", "Parel Central Mumbai",
         base_t + timedelta(days=1), base_t + timedelta(days=1, hours=1, minutes=30), None, None, 0.0, 15.0),
        (202, 2, 2, "transit", "CryoExpress Logistics", "Expressway Checkpost", "Mumbai-Pune Expressway",
         base_t + timedelta(days=1, hours=1, minutes=30), base_t + timedelta(days=1, hours=4), None, None, 0.0, 0.0),
        (203, 2, 3, "transfer", "Expressway Checkpost", "Pune City Feeder", "Toll Plaza Intermediate Dock",
         base_t + timedelta(days=1, hours=4), base_t + timedelta(days=1, hours=5), None, None, 0.0, 30.0),
        (204, 2, 4, "delivery", "Pune City Feeder", "Ruby Hall Transfusion Center", "Pune Dhole Patil Rd",
         base_t + timedelta(days=1, hours=5), base_t + timedelta(days=1, hours=7), None, None, 0.0, 15.0),
        (205, 2, 5, "storage", "Ruby Hall Transfusion Center", "Hospital Deep-Freeze", "Hospital Basement Vault",
         base_t + timedelta(days=1, hours=7), base_t + timedelta(days=1, hours=8), None, None, 0.0, 10.0),

        # Shipment 3 (In-Transit Ahmedabad -> Jaipur)
        (301, 3, 1, "pickup", "Ahmedabad SEZ Plant", "NorthLine Express Truck 4", "Ahmedabad Cargo Terminal",
         datetime.utcnow() - timedelta(hours=2), datetime.utcnow() - timedelta(hours=1), None, None, 0.0, 20.0),
        (302, 3, 2, "transit", "NorthLine Express Truck 4", "Udaipur Cross-Dock", "Rajasthan Corridor",
         datetime.utcnow() - timedelta(hours=1), datetime.utcnow() + timedelta(hours=3), None, None, 0.0, 0.0),
        (303, 3, 3, "storage", "Udaipur Cross-Dock", "Jaipur Route Van", "Udaipur Distribution Center Apron",
         datetime.utcnow() + timedelta(hours=3), datetime.utcnow() + timedelta(hours=5), None, None, 0.0, 75.0),
        (304, 3, 4, "transit", "Jaipur Route Van", "Jaipur City Hub", "Jaipur Bypass",
         datetime.utcnow() + timedelta(hours=5), datetime.utcnow() + timedelta(hours=8), None, None, 0.0, 0.0),
        (305, 3, 5, "delivery", "Jaipur City Hub", "SMS Medical College Pharmacy", "Jaipur Central",
         datetime.utcnow() + timedelta(hours=8), datetime.utcnow() + timedelta(hours=10), None, None, 0.0, 15.0),
    ]
    for hid, sid, seq, htype, fp, tp, loc, ws, we, rs, re, skew, dwell in handoffs:
        conn.execute(
            "INSERT INTO HANDOFFGUARD.handoffs "
            "(handoff_id, shipment_id, sequence_no, handoff_type, from_party, to_party, location, "
            " window_start_utc, window_end_utc, reported_start_utc, reported_end_utc, clock_skew_seconds, dwell_minutes) "
            "VALUES ({hid!d}, {sid!d}, {seq!d}, {htype}, {fp}, {tp}, {loc}, {ws}, {we}, {rs}, {re}, {skew}, {dwell})",
            {"hid": hid, "sid": sid, "seq": seq, "htype": htype, "fp": fp, "tp": tp, "loc": loc,
             "ws": ts(ws), "we": ts(we), "rs": ts(rs) if rs else None, "re": ts(re) if re else None,
             "skew": skew, "dwell": dwell},
        )

    # 4. Logger Devices
    print("Seeding logger devices...")
    loggers = [
        (1, "TT-ULTRA-001", "TempTale Ultra BLE", "v2.3.1", 1, 0.0),
        (2, "CS-COLD-002", "Sensitech ColdStream", "v1.4.0", 1, 180.0),
        (3, "CT-ULTRA-003", "CryoTag Ultra", "v1.8.0", 2, 0.0),
        (4, "TT-GEO-004", "TempTale GEO LTE", "v3.1.0", 3, 45.0),
        (5, "TT-ULTRA-005", "TempTale Ultra BLE", "v2.3.1", 4, 0.0),
    ]
    for lid, code, model, fw, sid, skew in loggers:
        conn.execute(
            "INSERT INTO HANDOFFGUARD.logger_devices "
            "(logger_id, device_code, model, firmware, assigned_shipment_id, clock_skew_seconds) "
            "VALUES ({lid!d}, {code}, {model}, {fw}, {sid!d}, {skew})",
            {"lid": lid, "code": code, "model": model, "fw": fw, "sid": sid, "skew": skew},
        )

    # 5. Push 5,000+ Sample IoT Temperature Logs
    print("Generating and inserting 5,000+ sample IoT temperature logs...")
    reading_id = 1
    total_readings = 5200

    # Distribute 5,200 readings across loggers:
    # Logger 1 (Shipment 1): 1,500 readings
    # Logger 2 (Shipment 1, secondary): 1,500 readings
    # Logger 3 (Shipment 2): 1,000 readings
    # Logger 4 (Shipment 3): 600 readings
    # Logger 5 (Shipment 4): 600 readings
    logger_configs = [
        {"lid": 1, "count": 1500, "start": base_t, "step_sec": 30, "target_temp": 4.5,
         "excursion_window": (base_t + timedelta(hours=8), base_t + timedelta(hours=10)), "exc_temp": 14.8},
        {"lid": 2, "count": 1500, "start": base_t, "step_sec": 30, "target_temp": 4.6,
         "excursion_window": (base_t + timedelta(hours=8), base_t + timedelta(hours=10)), "exc_temp": 14.6},
        {"lid": 3, "count": 1000, "start": base_t + timedelta(days=1), "step_sec": 30, "target_temp": -18.5,
         "excursion_window": (base_t + timedelta(days=1, hours=2), base_t + timedelta(days=1, hours=2, minutes=48)), "exc_temp": -12.0},
        {"lid": 4, "count": 600, "start": datetime.utcnow() - timedelta(hours=2), "step_sec": 20, "target_temp": 4.8,
         "excursion_window": None, "exc_temp": None},
        {"lid": 5, "count": 600, "start": base_t + timedelta(days=2), "step_sec": 60, "target_temp": 5.0,
         "excursion_window": None, "exc_temp": None},
    ]

    for cfg in logger_configs:
        lid = cfg["lid"]
        cnt = cfg["count"]
        curr = cfg["start"]
        step = timedelta(seconds=cfg["step_sec"])
        base_temp = cfg["target_temp"]
        exc_win = cfg["excursion_window"]
        exc_temp = cfg["exc_temp"]

        for _ in range(cnt):
            temp = base_temp + random.uniform(-0.3, 0.3)
            if exc_win and exc_win[0] <= curr <= exc_win[1]:
                temp = exc_temp + random.uniform(-0.4, 0.4)

            conn.execute(
                "INSERT INTO HANDOFFGUARD.logger_readings "
                "(reading_id, logger_id, reading_at_utc, temperature_c, battery_pct) "
                "VALUES ({rid!d}, {lid!d}, {rat}, {tc}, {bp})",
                {
                    "rid": reading_id,
                    "lid": lid,
                    "rat": ts(curr),
                    "tc": round(temp, 2),
                    "bp": round(max(10.0, 100.0 - (reading_id * 0.01)), 1),
                },
            )
            reading_id += 1
            curr += step

    print(f"Pushed {reading_id - 1} temperature logs into HANDOFFGUARD.logger_readings.")

    # 6. Excursions
    print("Seeding detected temperature excursions...")
    excursions = [
        (1, 1, 1, base_t + timedelta(hours=3), base_t + timedelta(hours=10, minutes=45),
         8.1, 14.8, 14.8, 465.0, "critical", "system", 104,
         "Reefer truck refrigeration unit shut down on depot apron during shift turnover."),
        (2, 2, 2, base_t + timedelta(days=1, hours=2), base_t + timedelta(days=1, hours=2, minutes=48),
         -20.0, -12.0, -12.0, 48.0, "medium", "system", 202,
         "Dry ice sublimation accelerated due to compromised secondary seal."),
    ]
    for eid, sid, pid, sa, ea, mn, mx, pk, dm, sev, db, gt, gc in excursions:
        conn.execute(
            "INSERT INTO HANDOFFGUARD.excursions "
            "(excursion_id, shipment_id, product_id, started_at_utc, ended_at_utc, "
            " min_temp_c, max_temp_c, peak_temp_c, duration_minutes, severity, "
            " detected_by, ground_truth_handoff_id, ground_truth_cause) "
            "VALUES ({eid!d}, {sid!d}, {pid!d}, {sa}, {ea}, {mn}, {mx}, {pk}, {dm}, {sev}, {db}, {gt}, {gc})",
            {"eid": eid, "sid": sid, "pid": pid, "sa": ts(sa), "ea": ts(ea),
             "mn": mn, "mx": mx, "pk": pk, "dm": dm, "sev": sev, "db": db, "gt": gt, "gc": gc},
        )

    conn.commit()
    print("\nInitialization & seeding completed successfully!")
    print(f"Total shipments: {len(shipments)}")
    print(f"Total handoffs (legs): {len(handoffs)}")
    print(f"Total logger devices: {len(loggers)}")
    print(f"Total IoT temperature logs: {reading_id - 1}")
    print(f"Total excursions: {len(excursions)}")


def main():
    conn = get_connection()
    try:
        init_schema(conn)
        seed_data(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
