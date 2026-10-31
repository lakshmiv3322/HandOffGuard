"""
HandoffGuard Exasol SQL Integration Test Suite
Executes isolated tests in schema HANDOFFGUARD_TEST.
Does NOT modify or touch HANDOFFGUARD demo data.
Exits with code 0 on success, 1 on failure.
"""

import sys
import os
import re
import ssl
import pyexasol

def main():
    print("=" * 72)
    print("STARTING EXASOL SQL INTEGRATION TESTS (Schema: HANDOFFGUARD_TEST)")
    print("=" * 72)

    c = pyexasol.connect(
        dsn="localhost:8563",
        user="sys",
        password="exasol",
        encryption=True,
        fetch_dict=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
    )

    # 1. Setup isolated test schema
    c.execute("CREATE SCHEMA IF NOT EXISTS HANDOFFGUARD_TEST")
    c.execute("OPEN SCHEMA HANDOFFGUARD_TEST")

    # 2. Create isolated tables
    c.execute("""
    CREATE OR REPLACE TABLE PRODUCTS (
        ID VARCHAR(36) PRIMARY KEY,
        NAME VARCHAR(120),
        MIN_TEMP_C DECIMAL(5,2),
        MAX_TEMP_C DECIMAL(5,2),
        MAX_EXCURSION_MINUTES DECIMAL(18,0)
    )
    """)

    c.execute("""
    CREATE OR REPLACE TABLE SHIPMENTS (
        ID VARCHAR(36) PRIMARY KEY,
        SHIPMENT_CODE VARCHAR(30),
        PRODUCT_ID VARCHAR(36)
    )
    """)

    c.execute("""
    CREATE OR REPLACE TABLE LOGGER_DEVICES (
        LOGGER_ID VARCHAR(50) PRIMARY KEY,
        DEVICE_CODE VARCHAR(50),
        ASSIGNED_SHIPMENT_ID VARCHAR(36),
        CLOCK_SKEW_SECONDS DECIMAL(18,0)
    )
    """)

    c.execute("""
    CREATE OR REPLACE TABLE LOGGER_READINGS (
        READING_ID VARCHAR(50) PRIMARY KEY,
        LOGGER_ID VARCHAR(50),
        READING_AT_UTC TIMESTAMP(3),
        TEMPERATURE_C DOUBLE,
        BATTERY_PCT DOUBLE
    )
    """)

    c.execute("""
    CREATE OR REPLACE TABLE HANDOFFS (
        ID VARCHAR(36) PRIMARY KEY,
        SHIPMENT_ID VARCHAR(36),
        SEQUENCE_NUMBER DECIMAL(18,0),
        HANDOFF_TYPE VARCHAR(40),
        FROM_PARTY VARCHAR(120),
        TO_PARTY VARCHAR(120),
        LOCATION VARCHAR(150),
        PLANNED_START_AT TIMESTAMP(3),
        ACTUAL_START_AT TIMESTAMP(3),
        PLANNED_END_AT TIMESTAMP(3),
        ACTUAL_END_AT TIMESTAMP(3)
    )
    """)

    c.execute("""
    CREATE OR REPLACE TABLE EXCURSIONS (
        EXCURSION_ID VARCHAR(50) PRIMARY KEY,
        SHIPMENT_ID VARCHAR(50),
        PRODUCT_ID VARCHAR(50),
        STARTED_AT_UTC TIMESTAMP(3),
        ENDED_AT_UTC TIMESTAMP(3),
        MIN_TEMP_C DOUBLE,
        MAX_TEMP_C DOUBLE,
        DETECTED_BY VARCHAR(100)
    )
    """)

    # 3. Create Repaired Views in HANDOFFGUARD_TEST from production migration SQL
    # retargeted to isolated test schema (ensures test executes the exact same migration SQL)
    from pathlib import Path
    migration_path = Path(__file__).resolve().parent.parent.parent / "db" / "migrations" / "005_repair_analytics_views.sql"
    if not migration_path.exists():
        raise FileNotFoundError(f"Migration file not found at {migration_path}")
    
    raw_migration = migration_path.read_text(encoding="utf-8")
    retargeted_migration = raw_migration.replace("HANDOFFGUARD", "HANDOFFGUARD_TEST")
    
    statements = []
    current_statement = []
    for line in retargeted_migration.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        current_statement.append(line)
        if stripped.endswith(";"):
            stmt_text = "\n".join(current_statement).strip()
            if stmt_text.endswith(";"):
                stmt_text = stmt_text[:-1].strip()
            if stmt_text:
                statements.append(stmt_text)
            current_statement = []
    
    print(f"Executing {len(statements)} retargeted view migration statements from {migration_path.name}...")
    for stmt in statements:
        c.execute(stmt)

    print("Isolated test tables and repaired views successfully created.")
    print("-" * 72)

    # 4. Insert Fixtures and Run Isolated Tests
    all_passed = True
    test_results = []

    def record_test(name, passed, detail=""):
        nonlocal all_passed
        status = "PASS" if passed else "FAIL"
        test_results.append((name, status, detail))
        if not passed:
            all_passed = False
        print(f"[{status}] {name}")
        if detail:
            print(f"       {detail}")

    # ── Product Fixtures ─────────────────────────────────────────
    c.execute("""
    INSERT INTO PRODUCTS VALUES 
      ('P_VACC', 'mRNA Vaccine', 2.0, 8.0, 30),
      ('P_CART', 'CAR-T Cell Therapy', -25.0, -15.0, 15),
      ('P_ALBU', 'Human Albumin', 15.0, 25.0, 60)
    """)

    # ── Test 1 & Test 2: Half-Open Boundary + Clock Skew ──────────
    c.execute("INSERT INTO SHIPMENTS VALUES ('S1', 'SHP-TEST-01', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L1', 'DEV-1', 'S1', 120)") # +120s clock skew
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H1', 'S1', 1, 'Reefer Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00'),
      ('H2', 'S1', 2, 'Warehouse Dock', 'Party B', 'Party C', 'Loc 2',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00',
       TIMESTAMP '2026-10-30 14:00:00', TIMESTAMP '2026-10-30 14:00:00')
    """)
    # Reading at raw 12:02:00 -> corrected = 12:02:00 - 120s = 12:00:00.
    # Exactly at boundary 12:00:00.
    # Must belong to H2 (>= 12:00), NOT H1 (< 12:00).
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_BOUND', 'L1', TIMESTAMP '2026-10-30 12:02:00', 5.0, 99.0)
    """)

    res = c.execute("SELECT * FROM V_READING_HANDOFF_MEMBERSHIP WHERE reading_id = 'R_BOUND'").fetchall()
    row = res[0]
    expected_corr = "2026-10-30 12:00:00.000000"
    t1_pass = (row["HANDOFF_ID"] == "H2" and row["MEMBERSHIP_STATUS"] == "MATCHED")
    t2_pass = (str(row["CORRECTED_AT_UTC"]) == expected_corr)

    record_test("Test 1: Half-open boundary at 12:00 belongs to H2, not H1", t1_pass,
                f"Assigned handoff: {row['HANDOFF_ID']}, status: {row['MEMBERSHIP_STATUS']}")
    record_test("Test 2: +120s clock skew subtracted (12:02:00 -> 12:00:00)", t2_pass,
                f"Raw: {row['READING_AT_UTC']}, Corrected: {row['CORRECTED_AT_UTC']}")

    # ── Test 3, 4, 5: Supported Segment, Splits, and Product Bounds ──
    c.execute("INSERT INTO SHIPMENTS VALUES ('S2', 'SHP-TEST-02', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L2', 'DEV-2', 'S2', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H2_1', 'S2', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00'),
      ('H2_2', 'S2', 2, 'Dock', 'Party B', 'Party C', 'Loc 2',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00',
       TIMESTAMP '2026-10-30 14:00:00', TIMESTAMP '2026-10-30 14:00:00')
    """)
    # Segment crossing boundary:
    # Reading 1: 11:58:00 at 10.0°C (safe max 8.0°C -> breach 2.0°C).
    # Reading 2: 12:03:00 at 10.0°C (segment duration = 5 min = 300s <= 600s).
    # Reading 3: 12:08:00 at 0.0°C (safe min 2.0°C -> below breach 2.0°C, duration = 5 min).
    # Reading 4: 12:13:00 at 5.0°C (end of segment 3).
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_SEG1', 'L2', TIMESTAMP '2026-10-30 11:58:00', 10.0, 99.0),
      ('R_SEG2', 'L2', TIMESTAMP '2026-10-30 12:03:00', 10.0, 99.0),
      ('R_SEG3', 'L2', TIMESTAMP '2026-10-30 12:08:00', 0.0, 99.0),
      ('R_SEG4', 'L2', TIMESTAMP '2026-10-30 12:13:00', 5.0, 99.0)
    """)

    exp_rows = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S2' ORDER BY sequence_no").fetchall()
    h2_1 = exp_rows[0]
    h2_2 = exp_rows[1]

    t3_pass = (float(h2_2["DEGREE_MINUTES_ABOVE"]) == 16.0) # 6.0 + 10.0
    t4_pass = (float(h2_2["DEGREE_MINUTES_BELOW"]) == 10.0) # 10.0 below
    t5_pass = (float(h2_1["DEGREE_MINUTES_ABOVE"]) == 4.0 and float(h2_1["SUPPORTED_OBSERVATION_MINUTES"]) == 2.0)

    record_test("Test 3: Constant 10°C for supported segment with 8°C max produces correct degree-minutes", t3_pass,
                f"H2_2 above DM: {h2_2['DEGREE_MINUTES_ABOVE']} (expected 16.0 = 6.0 split + 10.0)")
    record_test("Test 4: Constant 0°C for 5 minutes with 2°C min produces 10 °C·min below range", t4_pass,
                f"H2_2 below DM: {h2_2['DEGREE_MINUTES_BELOW']} (expected 10.0)")
    record_test("Test 5: Segment crossing boundary (11:58 to 12:03) split across H1 (2m) and H2 (3m)", t5_pass,
                f"H2_1 obs min: {h2_1['SUPPORTED_OBSERVATION_MINUTES']} (expected 2.0), DM: {h2_1['DEGREE_MINUTES_ABOVE']} (expected 4.0)")

    # ── Test 6: Gap above 600s contributes 0 supported exposure ──
    c.execute("INSERT INTO SHIPMENTS VALUES ('S3', 'SHP-TEST-03', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L3', 'DEV-3', 'S3', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H3_1', 'S3', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 10:00:00', TIMESTAMP '2026-10-30 10:00:00')
    """)
    # Gap: 08:00 to 08:20 (1200 seconds > 600s default max gap limit!)
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_GAP1', 'L3', TIMESTAMP '2026-10-30 08:00:00', 15.0, 99.0),
      ('R_GAP2', 'L3', TIMESTAMP '2026-10-30 08:20:00', 15.0, 99.0)
    """)
    h3_row = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S3'").fetchall()[0]
    t6_pass = (float(h3_row["SUPPORTED_OBSERVATION_MINUTES"]) == 0.0 and float(h3_row["TOTAL_DEGREE_MINUTES"]) == 0.0 and float(h3_row["UNSUPPORTED_GAP_MINUTES"]) == 120.0)
    record_test("Test 6: Gap above configured 600s contributes 0 supported exposure and flags gap", t6_pass,
                f"Supported min: {h3_row['SUPPORTED_OBSERVATION_MINUTES']}, Total DM: {h3_row['TOTAL_DEGREE_MINUTES']}, Gap min: {h3_row['UNSUPPORTED_GAP_MINUTES']}")

    # ── Test 7: Excursion covering only part of segment ──────────
    c.execute("INSERT INTO SHIPMENTS VALUES ('S4', 'SHP-TEST-04', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L4', 'DEV-4', 'S4', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H4_1', 'S4', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00',
       TIMESTAMP '2026-10-30 14:00:00', TIMESTAMP '2026-10-30 14:00:00')
    """)
    # Reading segment: 12:00 to 12:08 (8 min = 480s <= 600s) at 12.0°C (safe max 8.0°C).
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_EXC1', 'L4', TIMESTAMP '2026-10-30 12:00:00', 12.0, 99.0),
      ('R_EXC2', 'L4', TIMESTAMP '2026-10-30 12:08:00', 5.0, 99.0)
    """)
    # Excursion from 12:03 to 12:08 (5 min overlap with segment).
    c.execute("""
    INSERT INTO EXCURSIONS VALUES 
      ('EXC_PART', 'S4', 'P_VACC',
       TIMESTAMP '2026-10-30 12:03:00', TIMESTAMP '2026-10-30 12:08:00',
       12.0, 12.0, 'Automated Monitor')
    """)
    exc_row = c.execute("SELECT * FROM V_EXCURSION_ATTRIBUTION WHERE excursion_id = 'EXC_PART'").fetchall()[0]
    t7_pass = (float(exc_row["HANDOFF_TOTAL_DM"]) == 20.0 and float(exc_row["SUPPORTED_OBSERVATION_MINUTES"]) == 5.0)
    record_test("Test 7: Excursion covering only part of segment counts only that part", t7_pass,
                f"Obs minutes: {exc_row['SUPPORTED_OBSERVATION_MINUTES']} (expected 5.0), Excursion DM: {exc_row['HANDOFF_TOTAL_DM']} (expected 20.0)")

    # ── Test 8: Different product limits produce different results ─
    c.execute("INSERT INTO SHIPMENTS VALUES ('S5', 'SHP-TEST-05', 'P_CART')") # CAR-T max -15.0°C
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L5', 'DEV-5', 'S5', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H5_1', 'S5', 1, 'Cryo Reefer', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 10:00:00', TIMESTAMP '2026-10-30 10:00:00')
    """)
    # 5 min at 10.0°C: for CAR-T (max -15°C), breach is 10 - (-15) = 25.0°C!
    # Exposure = 25.0 * 5 = 125.0 °C·min.
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_CART1', 'L5', TIMESTAMP '2026-10-30 08:00:00', 10.0, 99.0),
      ('R_CART2', 'L5', TIMESTAMP '2026-10-30 08:05:00', 10.0, 99.0)
    """)
    h5_row = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S5'").fetchall()[0]
    t8_pass = (float(h5_row["DEGREE_MINUTES_ABOVE"]) == 125.0)
    record_test("Test 8: Product limits from PRODUCTS (-25 to -15°C) produce 125.0 °C·min", t8_pass,
                f"CAR-T above DM: {h5_row['DEGREE_MINUTES_ABOVE']} (expected 125.0)")

    # ── Test 9: Segment overlapping custody excluded from single-party exposure ──
    c.execute("INSERT INTO SHIPMENTS VALUES ('S6', 'SHP-TEST-06', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L6', 'DEV-6', 'S6', 0)")
    # Overlapping custody: H6_1 ends at 12:10, H6_2 starts at 12:00.
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H6_1', 'S6', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 10:00:00', TIMESTAMP '2026-10-30 10:00:00',
       TIMESTAMP '2026-10-30 12:10:00', TIMESTAMP '2026-10-30 12:10:00'),
      ('H6_2', 'S6', 2, 'Dock', 'Party B', 'Party C', 'Loc 2',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00',
       TIMESTAMP '2026-10-30 14:00:00', TIMESTAMP '2026-10-30 14:00:00')
    """)
    # Reading at 12:02 to 12:06 (falls inside the 12:00-12:10 overlap window)
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_OV1', 'L6', TIMESTAMP '2026-10-30 12:02:00', 12.0, 99.0),
      ('R_OV2', 'L6', TIMESTAMP '2026-10-30 12:06:00', 12.0, 99.0)
    """)
    h6_rows = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S6' ORDER BY sequence_no").fetchall()
    h6_1 = h6_rows[0]
    h6_2 = h6_rows[1]
    # Under conservative policy: overlap interval is excluded from single-party attributable exposure
    # Contributes to ambiguous_minutes (4.0 min), 0.0 to degree_minutes_above
    t9_pass = (
        float(h6_1["AMBIGUOUS_MINUTES"]) == 4.0 and
        float(h6_2["AMBIGUOUS_MINUTES"]) == 4.0 and
        float(h6_1["DEGREE_MINUTES_ABOVE"]) == 0.0 and
        float(h6_2["DEGREE_MINUTES_ABOVE"]) == 0.0 and
        h6_1["COVERAGE_STATUS"] == "AMBIGUOUS_CUSTODY_EXCLUSION"
    )
    record_test("Test 9: Overlapping custody segment excluded from attributable exposure and flagged", t9_pass,
                f"H6_1 ambiguous min: {h6_1['AMBIGUOUS_MINUTES']}, status: {h6_1['COVERAGE_STATUS']}")

    # ── Test 10: Missing actual timestamps (PLANNED_ONLY) excluded ─
    c.execute("INSERT INTO SHIPMENTS VALUES ('S7', 'SHP-TEST-07', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L7', 'DEV-7', 'S7', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H7_PLAN', 'S7', 1, 'Planned Flight', 'Air Carrier', 'Ground Agent', 'Airport',
       TIMESTAMP '2026-10-30 08:00:00', NULL,
       TIMESTAMP '2026-10-30 12:00:00', NULL)
    """)
    h7_row = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S7'").fetchall()[0]
    t10_pass = (h7_row["WINDOW_SOURCE"] == "PLANNED_ONLY" and h7_row["COVERAGE_STATUS"] == "EXCLUDED_PLANNED_ONLY")
    record_test("Test 10: Missing actual timestamps marked PLANNED_ONLY and excluded", t10_pass,
                f"Window source: {h7_row['WINDOW_SOURCE']}, status: {h7_row['COVERAGE_STATUS']}")

    # ── Test 11: No readings at all returns INCONCLUSIVE ─────────
    c.execute("INSERT INTO SHIPMENTS VALUES ('S8', 'SHP-TEST-08', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L8', 'DEV-8', 'S8', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H8_1', 'S8', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00')
    """)
    c.execute("""
    INSERT INTO EXCURSIONS VALUES 
      ('EXC_NODATA', 'S8', 'P_VACC',
       TIMESTAMP '2026-10-30 09:00:00', TIMESTAMP '2026-10-30 10:00:00',
       12.0, 12.0, 'Automated Monitor')
    """)
    exc_nodata = c.execute("SELECT * FROM V_EXCURSION_ATTRIBUTION WHERE excursion_id = 'EXC_NODATA'").fetchall()[0]
    t11_pass = (exc_nodata["EVIDENCE_STATUS"] == "INCONCLUSIVE_INSUFFICIENT_DATA")
    record_test("Test 11: No readings at all returns INCONCLUSIVE_INSUFFICIENT_DATA", t11_pass,
                f"Status: {exc_nodata['EVIDENCE_STATUS']}")

    # ── Test 12: Multiple assigned loggers returns INCONCLUSIVE ──
    c.execute("INSERT INTO SHIPMENTS VALUES ('S9', 'SHP-TEST-09', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L9_A', 'DEV-9A', 'S9', 0), ('L9_B', 'DEV-9B', 'S9', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H9_1', 'S9', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00')
    """)
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_M1', 'L9_A', TIMESTAMP '2026-10-30 08:00:00', 12.0, 99.0),
      ('R_M2', 'L9_A', TIMESTAMP '2026-10-30 08:05:00', 12.0, 99.0)
    """)
    c.execute("""
    INSERT INTO EXCURSIONS VALUES 
      ('EXC_MULTI', 'S9', 'P_VACC',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:05:00',
       12.0, 12.0, 'Monitor')
    """)
    exc_multi = c.execute("SELECT * FROM V_EXCURSION_ATTRIBUTION WHERE excursion_id = 'EXC_MULTI'").fetchall()[0]
    t12_pass = (exc_multi["EVIDENCE_STATUS"] == "INCONCLUSIVE_MULTI_LOGGER")
    record_test("Test 12: Multiple assigned loggers returns INCONCLUSIVE_MULTI_LOGGER", t12_pass,
                f"Status: {exc_multi['EVIDENCE_STATUS']}")

    # ── Test 13: Duplicate timestamps produce 0 duration ─────────
    c.execute("INSERT INTO SHIPMENTS VALUES ('S10', 'SHP-TEST-10', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L10', 'DEV-10', 'S10', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H10_1', 'S10', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 10:00:00', TIMESTAMP '2026-10-30 10:00:00')
    """)
    # Two readings at exact same timestamp
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_DUP1', 'L10', TIMESTAMP '2026-10-30 08:00:00', 12.0, 99.0),
      ('R_DUP2', 'L10', TIMESTAMP '2026-10-30 08:00:00', 14.0, 99.0),
      ('R_DUP3', 'L10', TIMESTAMP '2026-10-30 08:05:00', 12.0, 99.0)
    """)
    h10_row = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S10'").fetchall()[0]
    t13_pass = (float(h10_row["SUPPORTED_OBSERVATION_MINUTES"]) == 5.0)
    record_test("Test 13: Duplicate timestamps contribute 0 duration, no inflated exposure", t13_pass,
                f"Obs minutes: {h10_row['SUPPORTED_OBSERVATION_MINUTES']} (expected 5.0)")

    # ── Test 14: Time before first reading & after last reading ──
    # In S10: Handoff is 08:00 to 10:00 (120 minutes).
    # Readings end at 08:05:00.
    # Time from 08:05 to 10:00 (115 min) must be unsupported gap, NOT carried forward!
    t14_pass = (float(h10_row["UNSUPPORTED_GAP_MINUTES"]) == 115.0)
    record_test("Test 14: Time after last reading is unsupported gap, does not extend indefinitely", t14_pass,
                f"Unsupported gap: {h10_row['UNSUPPORTED_GAP_MINUTES']} (expected 115.0 min)")

    # 5. Clean up isolated test schema
    c.execute("DROP SCHEMA IF EXISTS HANDOFFGUARD_TEST CASCADE")
    print("-" * 72)
    print("Cleaned up isolated schema HANDOFFGUARD_TEST.")
    c.close()

    print("=" * 72)
    print(f"SUMMARY: {len(test_results)} Tests Executed. All Passed: {all_passed}")
    print("=" * 72)

    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
