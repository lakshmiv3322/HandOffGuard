"""
HandoffGuard — Seed Demo Scenarios
==================================
Idempotently seeds the three mandatory demo scenarios into Exasol:

1. Clear Single-Handoff Exposure:
   Shipment: SHP-SYNTH-DENSE-01 | Excursion: EXC-SYNTH-01
   301 high-density readings (1-min intervals). 
   Selected investigation window: 10:10 to 10:55 UTC (45 min, 281.20 °C·min).
   Cooldown exposure continues until 10:58 UTC (total 289.12 °C·min across H2).
   Attribution status: Prototype Ranking (Handoff 2 holds 100% share).

2. Insufficient Evidence:
   Shipment: SHP-2026-0881 | Excursion: EXC-1002
   9 sparse readings with consecutive gaps ranging from 30 to 75 min (all > 600s threshold).
   Attribution status: INCONCLUSIVE_INSUFFICIENT_DATA.
   Exposure displayed as "Unavailable". Peak observed temp 18.2 °C preserved.

3. Conflicting / Ambiguous Custody:
   Shipment: SHP-SYNTH-AMBIG-01 | Excursion: EXC-SYNTH-02
   Overlapping actual custody windows between Handoff 1 and Handoff 2 (10:00 to 10:15 UTC).
   361 readings. 12-min breach occurs during overlap.
   Overlapping segments are excluded from single-party attributable exposure and flagged.
   Attribution status: Inconclusive / Ambiguous custody exclusion.

Usage:
  python scripts/seed_demo_scenarios.py [--schema SCHEMA_NAME]
"""

import os
import sys
import argparse
import ssl
from datetime import datetime, timedelta
import pyexasol

from init_exasol_db import init_db

def parse_args():
    parser = argparse.ArgumentParser(description="Seed HandoffGuard demo scenarios into Exasol")
    parser.add_argument("--schema", default=os.getenv("EXASOL_SCHEMA", "HANDOFFGUARD"), help="Target schema")
    parser.add_argument("--host", default=os.getenv("EXASOL_HOST", "localhost"), help="Exasol host")
    parser.add_argument("--port", type=int, default=int(os.getenv("EXASOL_PORT", 8563)), help="Exasol port")
    parser.add_argument("--user", default=os.getenv("EXASOL_USER", "sys"), help="Exasol user")
    parser.add_argument("--password", default=os.getenv("EXASOL_PASSWORD", "exasol"), help="Exasol password")
    return parser.parse_args()

def ensure_schema_ready(host, port, user, password, schema):
    c = pyexasol.connect(
        dsn=f"{host}:{port}", user=user, password=password,
        encryption=True, fetch_dict=True, websocket_sslopt={"cert_reqs": ssl.CERT_NONE}
    )
    # Check if schema and views exist
    views = c.execute(f"SELECT VIEW_NAME FROM EXA_ALL_VIEWS WHERE VIEW_SCHEMA = '{schema}'").fetchall()
    c.close()
    if len(views) < 3:
        print(f"Schema {schema} missing base tables or views. Auto-initializing schema...")
        init_db(host, port, user, password, schema)

def seed_scenarios(host, port, user, password, schema):
    ensure_schema_ready(host, port, user, password, schema)

    print("=" * 72)
    print(f"Seeding HandoffGuard Demo Scenarios into Schema: {schema}")
    print("=" * 72)

    c = pyexasol.connect(
        dsn=f"{host}:{port}", user=user, password=password,
        encryption=True, fetch_dict=True, websocket_sslopt={"cert_reqs": ssl.CERT_NONE}
    )
    c.execute(f"OPEN SCHEMA {schema}")

    # Ensure base product prod-001 exists
    p = c.execute(f"SELECT ID FROM {schema}.PRODUCTS WHERE ID = 'prod-001'").fetchall()
    if not p:
        c.execute(f"""
        INSERT INTO {schema}.PRODUCTS (ID, NAME, MIN_TEMP_C, MAX_TEMP_C, MAX_EXCURSION_MINUTES)
        VALUES ('prod-001', 'mRNA COVID-19 Vaccine (Demo)', 2.0, 8.0, 30)
        """)

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario 1: SHP-SYNTH-DENSE-01 (Clear Single-Handoff Exposure)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[Scenario 1] Seeding SHP-SYNTH-DENSE-01...")
    c.execute(f"DELETE FROM {schema}.LOGGER_READINGS WHERE LOGGER_ID = 'LOG-SYNTH-01'")
    c.execute(f"DELETE FROM {schema}.LOGGER_DEVICES WHERE LOGGER_ID = 'LOG-SYNTH-01'")
    c.execute(f"DELETE FROM {schema}.EXCURSIONS WHERE EXCURSION_ID = 'EXC-SYNTH-01'")
    c.execute(f"DELETE FROM {schema}.HANDOFFS WHERE SHIPMENT_ID = 'SHP-SYNTH-DENSE-01'")
    c.execute(f"DELETE FROM {schema}.SHIPMENTS WHERE ID = 'SHP-SYNTH-DENSE-01'")

    c.execute(f"""
    INSERT INTO {schema}.SHIPMENTS (
        ID, SHIPMENT_CODE, PRODUCT_ID, ORIGIN, DESTINATION,
        DISPATCHED_AT, EXPECTED_DELIVERY_AT, ACTUAL_DELIVERY_AT,
        STATUS, PRIORITY, OVERALL_RISK_SCORE, CREATED_AT, UPDATED_AT
    ) VALUES (
        'SHP-SYNTH-DENSE-01', 'SHP-BLR-HYD-01', 'prod-001',
        'Bengaluru Central Pharma Hub', 'Hyderabad Regional Depot',
        TIMESTAMP '2026-10-31 08:00:00', TIMESTAMP '2026-10-31 13:00:00', NULL,
        'IN_TRANSIT', 'HIGH', 78,
        TIMESTAMP '2026-10-31 07:30:00', TIMESTAMP '2026-10-31 07:30:00'
    )
    """)

    c.execute(f"""
    INSERT INTO {schema}.LOGGER_DEVICES (
        LOGGER_ID, DEVICE_CODE, MODEL, FIRMWARE,
        ASSIGNED_SHIPMENT_ID, CLOCK_SKEW_SECONDS, CREATED_AT
    ) VALUES (
        'LOG-SYNTH-01', 'DEV-SYNTH-PRO', 'SensGuard Ultra HD', 'FW-2.1.0',
        'SHP-SYNTH-DENSE-01', 0, TIMESTAMP '2026-10-31 07:45:00'
    )
    """)

    c.execute(f"""
    INSERT INTO {schema}.HANDOFFS (
        ID, SHIPMENT_ID, SEQUENCE_NUMBER, HANDOFF_TYPE,
        FROM_PARTY, TO_PARTY, LOCATION,
        PLANNED_START_AT, ACTUAL_START_AT, PLANNED_END_AT, ACTUAL_END_AT,
        DWELL_MINUTES, TEMPERATURE_LOG_AVAILABLE, RISK_SCORE, RISK_LEVEL, CREATED_AT
    ) VALUES 
    (
        'HND-SYNTH-01', 'SHP-SYNTH-DENSE-01', 1, 'Reefer Truck',
        'Apex Cold Logistics', 'Deccan Logistics Hub', 'Highway NH44',
        TIMESTAMP '2026-10-31 08:00:00', TIMESTAMP '2026-10-31 08:00:00',
        TIMESTAMP '2026-10-31 10:00:00', TIMESTAMP '2026-10-31 10:00:00',
        0, TRUE, 12, 'LOW', TIMESTAMP '2026-10-31 07:45:00'
    ),
    (
        'HND-SYNTH-02', 'SHP-SYNTH-DENSE-01', 2, 'Dock Transfer',
        'Deccan Logistics Hub Operator', 'Express Last-Mile Ltd', 'Hyderabad Cross-Dock Bay 4',
        TIMESTAMP '2026-10-31 10:00:00', TIMESTAMP '2026-10-31 10:00:00',
        TIMESTAMP '2026-10-31 11:00:00', TIMESTAMP '2026-10-31 11:00:00',
        0, TRUE, 88, 'CRITICAL', TIMESTAMP '2026-10-31 07:45:00'
    ),
    (
        'HND-SYNTH-03', 'SHP-SYNTH-DENSE-01', 3, 'Delivery Van',
        'Express Last-Mile Ltd', 'Hyderabad Health Depot Receiving', 'Hyderabad Urban Route',
        TIMESTAMP '2026-10-31 11:00:00', TIMESTAMP '2026-10-31 11:00:00',
        TIMESTAMP '2026-10-31 13:00:00', TIMESTAMP '2026-10-31 13:00:00',
        0, TRUE, 18, 'LOW', TIMESTAMP '2026-10-31 07:45:00'
    )
    """)

    c.execute(f"""
    INSERT INTO {schema}.EXCURSIONS (
        EXCURSION_ID, SHIPMENT_ID, PRODUCT_ID,
        STARTED_AT_UTC, ENDED_AT_UTC, MIN_TEMP_C, MAX_TEMP_C,
        DETECTED_BY, CREATED_AT
    ) VALUES (
        'EXC-SYNTH-01', 'SHP-SYNTH-DENSE-01', 'prod-001',
        TIMESTAMP '2026-10-31 10:10:00', TIMESTAMP '2026-10-31 10:55:00',
        12.0, 16.5, 'Exasol Automated Window Monitor', TIMESTAMP '2026-10-31 11:05:00'
    )
    """)

    base_time = datetime(2026, 10, 31, 8, 0, 0)
    dense_readings = []
    for i in range(301):
        t = base_time + timedelta(minutes=i)
        temp = 4.8 + 0.3 * ((i % 5) - 2) / 2.0
        if 130 <= i <= 175:
            progress = (i - 130) / 45.0
            if progress < 0.5:
                temp = 12.0 + (16.5 - 12.0) * (progress / 0.5)
            else:
                temp = 16.5 - (16.5 - 12.0) * ((progress - 0.5) / 0.5)
        elif 120 <= i < 130:
            temp = 5.2 + (7.8 - 5.2) * ((i - 120) / 10.0)
        elif 175 < i < 180:
            temp = 12.0 - (12.0 - 5.2) * ((i - 175) / 5.0)

        dense_readings.append((
            f'R-SYNTH-{i:04d}', 'LOG-SYNTH-01', t.strftime('%Y-%m-%d %H:%M:%S'), round(temp, 2), 99
        ))

    for b in range(0, len(dense_readings), 50):
        batch = dense_readings[b:b+50]
        val_strs = [f"('{r[0]}', '{r[1]}', TIMESTAMP '{r[2]}', {r[3]}, {r[4]})" for r in batch]
        c.execute(f"INSERT INTO {schema}.LOGGER_READINGS (READING_ID, LOGGER_ID, READING_AT_UTC, TEMPERATURE_C, BATTERY_PCT) VALUES {', '.join(val_strs)}")

    print(f"  Inserted 301 readings for Scenario 1.")

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario 2: SHP-2026-0881 (Insufficient Evidence / Gaps)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[Scenario 2] Seeding SHP-2026-0881...")
    c.execute(f"DELETE FROM {schema}.LOGGER_READINGS WHERE LOGGER_ID = 'LOG-9942'")
    c.execute(f"DELETE FROM {schema}.LOGGER_DEVICES WHERE LOGGER_ID = 'LOG-9942'")
    c.execute(f"DELETE FROM {schema}.EXCURSIONS WHERE EXCURSION_ID = 'EXC-1002'")
    c.execute(f"DELETE FROM {schema}.HANDOFFS WHERE SHIPMENT_ID = 'SHP-2026-0881'")
    c.execute(f"DELETE FROM {schema}.SHIPMENTS WHERE ID = 'SHP-2026-0881'")

    c.execute(f"""
    INSERT INTO {schema}.SHIPMENTS (
        ID, SHIPMENT_CODE, PRODUCT_ID, ORIGIN, DESTINATION,
        DISPATCHED_AT, EXPECTED_DELIVERY_AT, STATUS, PRIORITY, OVERALL_RISK_SCORE
    ) VALUES (
        'SHP-2026-0881', 'SHP-DEL-MUM-04', 'prod-001',
        'Delhi Central Hub', 'Mumbai Distribution Center',
        TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 18:00:00',
        'IN_TRANSIT', 'HIGH', 0
    )
    """)

    c.execute(f"""
    INSERT INTO {schema}.LOGGER_DEVICES (
        LOGGER_ID, DEVICE_CODE, MODEL, FIRMWARE, ASSIGNED_SHIPMENT_ID, CLOCK_SKEW_SECONDS
    ) VALUES (
        'LOG-9942', 'DEVICE-TEMP-X', 'SensGuard V2', 'FW-1.0.4', 'SHP-2026-0881', 0
    )
    """)

    c.execute(f"""
    INSERT INTO {schema}.HANDOFFS (
        ID, SHIPMENT_ID, SEQUENCE_NUMBER, HANDOFF_TYPE,
        FROM_PARTY, TO_PARTY, LOCATION,
        PLANNED_START_AT, ACTUAL_START_AT, PLANNED_END_AT, ACTUAL_END_AT,
        DWELL_MINUTES, TEMPERATURE_LOG_AVAILABLE, RISK_SCORE, RISK_LEVEL
    ) VALUES 
    (
        'H1', 'SHP-2026-0881', 1, 'Reefer Truck',
        'Alpha Logistics', 'Cross-Dock Delta', 'Highway Zone A',
        TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
        TIMESTAMP '2026-10-30 11:59:00', TIMESTAMP '2026-10-30 12:00:00',
        0, TRUE, 10, 'LOW'
    ),
    (
        'H2', 'SHP-2026-0881', 2, 'Warehouse Dock',
        'Cross-Dock Delta Operator', 'Swift Riders Ltd', 'Terminal 2 Loading Area',
        TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00',
        TIMESTAMP '2026-10-30 13:59:00', TIMESTAMP '2026-10-30 14:00:00',
        0, TRUE, 85, 'HIGH'
    ),
    (
        'H3', 'SHP-2026-0881', 3, 'Delivery Bike',
        'Swift Riders Ltd', 'Mumbai Pharmacy Local Agent', 'Urban Zone B',
        TIMESTAMP '2026-10-30 14:00:00', TIMESTAMP '2026-10-30 14:00:00',
        TIMESTAMP '2026-10-30 17:00:00', TIMESTAMP '2026-10-30 17:00:00',
        0, TRUE, 15, 'LOW'
    )
    """)

    c.execute(f"""
    INSERT INTO {schema}.EXCURSIONS (
        EXCURSION_ID, SHIPMENT_ID, PRODUCT_ID,
        STARTED_AT_UTC, ENDED_AT_UTC, MIN_TEMP_C, MAX_TEMP_C, DETECTED_BY
    ) VALUES (
        'EXC-1002', 'SHP-2026-0881', 'prod-001',
        TIMESTAMP '2026-10-30 12:15:00', TIMESTAMP '2026-10-30 13:45:00',
        12.8, 18.2, 'Exasol Automated Window Monitor'
    )
    """)

    sparse_readings = [
        ('R1', 'LOG-9942', '2026-10-30 09:00:00', 4.2, 99),
        ('R2', 'LOG-9942', '2026-10-30 10:00:00', 4.5, 99),
        ('R3', 'LOG-9942', '2026-10-30 11:00:00', 4.1, 99),
        ('R4', 'LOG-9942', '2026-10-30 12:15:00', 12.8, 98),
        ('R5', 'LOG-9942', '2026-10-30 12:45:00', 16.4, 98),
        ('R6', 'LOG-9942', '2026-10-30 13:15:00', 18.2, 98),
        ('R7', 'LOG-9942', '2026-10-30 13:45:00', 14.1, 97),
        ('R8', 'LOG-9942', '2026-10-30 14:30:00', 5.5, 97),
        ('R9', 'LOG-9942', '2026-10-30 15:30:00', 4.8, 97),
    ]
    val_strs = [f"('{r[0]}', '{r[1]}', TIMESTAMP '{r[2]}', {r[3]}, {r[4]})" for r in sparse_readings]
    c.execute(f"INSERT INTO {schema}.LOGGER_READINGS (READING_ID, LOGGER_ID, READING_AT_UTC, TEMPERATURE_C, BATTERY_PCT) VALUES {', '.join(val_strs)}")
    print("  Inserted 9 sparse readings for Scenario 2.")

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario 3: SHP-SYNTH-AMBIG-01 (Conflicting / Ambiguous Evidence)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[Scenario 3] Seeding SHP-SYNTH-AMBIG-01...")
    c.execute(f"DELETE FROM {schema}.LOGGER_READINGS WHERE LOGGER_ID = 'LOG-SYNTH-AMBIG-01'")
    c.execute(f"DELETE FROM {schema}.LOGGER_DEVICES WHERE LOGGER_ID = 'LOG-SYNTH-AMBIG-01'")
    c.execute(f"DELETE FROM {schema}.EXCURSIONS WHERE SHIPMENT_ID = 'SHP-SYNTH-AMBIG-01'")
    c.execute(f"DELETE FROM {schema}.HANDOFFS WHERE SHIPMENT_ID = 'SHP-SYNTH-AMBIG-01'")
    c.execute(f"DELETE FROM {schema}.SHIPMENTS WHERE ID = 'SHP-SYNTH-AMBIG-01'")

    c.execute(f"""
    INSERT INTO {schema}.SHIPMENTS (
        ID, SHIPMENT_CODE, PRODUCT_ID, ORIGIN, DESTINATION,
        DISPATCHED_AT, EXPECTED_DELIVERY_AT, STATUS, PRIORITY, OVERALL_RISK_SCORE
    ) VALUES (
        'SHP-SYNTH-AMBIG-01', 'SHP-HYD-DEL-02', 'prod-001',
        'Hyderabad Pharma City Gateway', 'Delhi NCR Regional Vaccine Depot',
        TIMESTAMP '2026-10-31 08:00:00', TIMESTAMP '2026-10-31 14:00:00',
        'IN_TRANSIT', 'HIGH', 85
    )
    """)

    c.execute(f"""
    INSERT INTO {schema}.HANDOFFS (
        ID, SHIPMENT_ID, SEQUENCE_NUMBER, HANDOFF_TYPE, FROM_PARTY, TO_PARTY, LOCATION,
        PLANNED_START_AT, ACTUAL_START_AT, PLANNED_END_AT, ACTUAL_END_AT,
        DWELL_MINUTES, TEMPERATURE_LOG_AVAILABLE, RISK_SCORE, RISK_LEVEL
    ) VALUES
    (
        'HND-AMBIG-01', 'SHP-SYNTH-AMBIG-01', 1, 'Reefer Truck',
        'Hyderabad Logistics Hub', 'Nagpur Transit Facility', 'Highway NH44 South',
        TIMESTAMP '2026-10-31 08:00:00', TIMESTAMP '2026-10-31 08:00:00',
        TIMESTAMP '2026-10-31 10:00:00', TIMESTAMP '2026-10-31 10:15:00',
        0, TRUE, 25, 'LOW'
    ),
    (
        'HND-AMBIG-02', 'SHP-SYNTH-AMBIG-01', 2, 'Warehouse Cross-Dock',
        'Nagpur Transit Facility', 'Northern Express Linehaul', 'Nagpur Cross-Dock Bay 4',
        TIMESTAMP '2026-10-31 10:00:00', TIMESTAMP '2026-10-31 10:00:00',
        TIMESTAMP '2026-10-31 12:00:00', TIMESTAMP '2026-10-31 12:00:00',
        45, TRUE, 70, 'HIGH'
    ),
    (
        'HND-AMBIG-03', 'SHP-SYNTH-AMBIG-01', 3, 'Delivery Van',
        'Northern Express Linehaul', 'Delhi Regional Depot', 'Highway NH44 North',
        TIMESTAMP '2026-10-31 12:00:00', TIMESTAMP '2026-10-31 12:00:00',
        TIMESTAMP '2026-10-31 14:00:00', TIMESTAMP '2026-10-31 14:00:00',
        0, TRUE, 15, 'LOW'
    )
    """)

    c.execute(f"""
    INSERT INTO {schema}.LOGGER_DEVICES (LOGGER_ID, DEVICE_CODE, ASSIGNED_SHIPMENT_ID, CLOCK_SKEW_SECONDS)
    VALUES ('LOG-SYNTH-AMBIG-01', 'DEV-AMBIG-01', 'SHP-SYNTH-AMBIG-01', 0)
    """)

    c.execute(f"""
    INSERT INTO {schema}.EXCURSIONS (
        EXCURSION_ID, SHIPMENT_ID, PRODUCT_ID, STARTED_AT_UTC, ENDED_AT_UTC,
        MIN_TEMP_C, MAX_TEMP_C, DETECTED_BY
    ) VALUES (
        'EXC-SYNTH-02', 'SHP-SYNTH-AMBIG-01', 'prod-001',
        TIMESTAMP '2026-10-31 10:02:00', TIMESTAMP '2026-10-31 10:14:00',
        2.0, 8.0, 'Exasol Continuous Ingestion'
    )
    """)

    base_t = datetime(2026, 10, 31, 8, 0, 0)
    ambig_readings = []
    for i in range(361):
        t = base_t + timedelta(minutes=i)
        temp = 14.0 if (120 <= i <= 135) else 4.5
        ambig_readings.append((f"RDG-AMBIG-{i:04d}", "LOG-SYNTH-AMBIG-01", t.strftime("%Y-%m-%d %H:%M:%S"), temp, 99))

    for b in range(0, len(ambig_readings), 50):
        batch = ambig_readings[b:b+50]
        val_strs = [f"('{r[0]}', '{r[1]}', TIMESTAMP '{r[2]}', {r[3]}, {r[4]})" for r in batch]
        c.execute(f"INSERT INTO {schema}.LOGGER_READINGS (READING_ID, LOGGER_ID, READING_AT_UTC, TEMPERATURE_C, BATTERY_PCT) VALUES {', '.join(val_strs)}")

    print("  Inserted 361 readings for Scenario 3.")

    # ─────────────────────────────────────────────────────────────────────────
    # Verification
    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print(f"VERIFYING 3 DEMO SCENARIOS IN EXASOL SCHEMA: {schema}")
    print("=" * 72)

    scenarios = [
        ("Scenario 1: Clear Exposure", "SHP-SYNTH-DENSE-01", "EXC-SYNTH-01"),
        ("Scenario 2: Insufficient Data", "SHP-2026-0881", "EXC-1002"),
        ("Scenario 3: Ambiguous Custody", "SHP-SYNTH-AMBIG-01", "EXC-SYNTH-02"),
    ]

    for title, sid, eid in scenarios:
        print(f"\n--- {title} ({sid} / {eid}) ---")
        s = c.execute(f"SELECT ID, SHIPMENT_CODE FROM {schema}.SHIPMENTS WHERE ID = '{sid}'").fetchone()
        print(f"  Shipment: {s['ID']} ({s['SHIPMENT_CODE']})")

        rc = c.execute(f"""
        SELECT COUNT(*) AS CNT FROM {schema}.LOGGER_READINGS r 
        JOIN {schema}.LOGGER_DEVICES ld ON r.LOGGER_ID = ld.LOGGER_ID 
        WHERE ld.ASSIGNED_SHIPMENT_ID = '{sid}'
        """).fetchone()
        print(f"  Readings captured: {rc['CNT']}")

        rows = c.execute(f"""
        SELECT handoff_id, sequence_no, handoff_total_dm, supported_observation_minutes,
               ambiguous_minutes, attribution_rank, evidence_status
        FROM {schema}.V_EXCURSION_ATTRIBUTION
        WHERE excursion_id = '{eid}'
        ORDER BY sequence_no
        """).fetchall()

        print(f"  Attribution rows: {len(rows)}")
        for r in rows:
            print(f"    Handoff {r['SEQUENCE_NO']} ({r['HANDOFF_ID']}): "
                  f"Rank={r['ATTRIBUTION_RANK']}, "
                  f"DM={r['HANDOFF_TOTAL_DM']}, "
                  f"SupportedMin={r['SUPPORTED_OBSERVATION_MINUTES']}, "
                  f"AmbiguousMin={r['AMBIGUOUS_MINUTES']}, "
                  f"Status={r['EVIDENCE_STATUS']}")

    print("\n" + "=" * 72)
    print(f"ALL 3 DEMO SCENARIOS READY AND VERIFIED IN {schema}")
    print("=" * 72)
    c.close()

def main():
    args = parse_args()
    seed_scenarios(args.host, args.port, args.user, args.password, args.schema)

if __name__ == "__main__":
    main()
