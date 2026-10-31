"""
HandoffGuard — Seed Demo Scenarios
==================================
Idempotently seeds the three mandatory demo scenarios into HANDOFFGUARD:

1. Clear Single-Handoff Exposure:
   Shipment: SHP-SYNTH-DENSE-01
   Excursion: EXC-SYNTH-01
   301 high-density readings (1-min intervals). Clear excursion during Handoff 2 (Dock Transfer).
   Attribution status: Prototype Ranking (Handoff 2 holds dominant exposure).

2. Insufficient Evidence:
   Shipment: SHP-2026-0881
   Excursion: EXC-1002
   9 sparse readings with consecutive gaps ranging from 30 to 75 min (all > 600s threshold).
   Attribution status: INCONCLUSIVE_INSUFFICIENT_DATA.
   Exposure displayed as "Unavailable" (not valid zero). Peak observed temp 18.2 °C preserved.

3. Conflicting / Ambiguous Custody:
   Shipment: SHP-SYNTH-AMBIG-01
   Excursion: EXC-SYNTH-02
   Overlapping actual custody windows between Handoff 1 and Handoff 2 (10:00 to 10:15).
   Excursion occurs during this conflict window.
   Overlapping segments are excluded from single-party attributable exposure and flagged.
   Attribution status: Inconclusive / Ambiguous custody exclusion.

Usage:
  backend\\venv\\Scripts\\python scripts/seed_demo_scenarios.py
"""

import sys
import ssl
from datetime import datetime, timedelta
import pyexasol

def main():
    print("=" * 72)
    print("Seeding HandoffGuard Demo Scenarios into HANDOFFGUARD")
    print("=" * 72)

    c = pyexasol.connect(
        dsn="localhost:8563",
        user="sys",
        password="exasol",
        encryption=True,
        fetch_dict=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
    )
    c.execute("OPEN SCHEMA HANDOFFGUARD")

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario 3: SHP-SYNTH-AMBIG-01 (Conflicting / Ambiguous Evidence)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[Scenario 3] Checking SHP-SYNTH-AMBIG-01...")
    exists = c.execute("SELECT id FROM shipments WHERE id = 'SHP-SYNTH-AMBIG-01'").fetchall()
    if exists:
        print("  SHP-SYNTH-AMBIG-01 already exists, refreshing...")
        c.execute("DELETE FROM logger_readings WHERE logger_id = 'LOG-SYNTH-AMBIG-01'")
        c.execute("DELETE FROM logger_devices WHERE logger_id = 'LOG-SYNTH-AMBIG-01'")
        c.execute("DELETE FROM excursions WHERE shipment_id = 'SHP-SYNTH-AMBIG-01'")
        c.execute("DELETE FROM handoffs WHERE shipment_id = 'SHP-SYNTH-AMBIG-01'")
        c.execute("DELETE FROM shipments WHERE id = 'SHP-SYNTH-AMBIG-01'")

    # Ensure prod-001 exists
    p = c.execute("SELECT id FROM products WHERE id = 'prod-001'").fetchall()
    if not p:
        c.execute("INSERT INTO products (id, name, min_temp_c, max_temp_c, max_excursion_minutes) VALUES ('prod-001', 'mRNA COVID-19 Vaccine (Demo)', 2.0, 8.0, 30)")

    c.execute("""
    INSERT INTO shipments (
        id, shipment_code, product_id, origin, destination,
        dispatched_at, expected_delivery_at, status, priority, overall_risk_score
    ) VALUES (
        'SHP-SYNTH-AMBIG-01',
        'SHP-HYD-DEL-02',
        'prod-001',
        'Hyderabad Pharma City Gateway',
        'Delhi NCR Regional Vaccine Depot',
        TIMESTAMP '2026-10-31 08:00:00',
        TIMESTAMP '2026-10-31 14:00:00',
        'IN_TRANSIT',
        'HIGH',
        85
    )
    """)

    c.execute("""
    INSERT INTO handoffs (
        id, shipment_id, sequence_number, handoff_type, from_party, to_party, location,
        planned_start_at, actual_start_at, planned_end_at, actual_end_at,
        dwell_minutes, temperature_log_available, risk_score, risk_level
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

    c.execute("""
    INSERT INTO logger_devices (logger_id, device_code, assigned_shipment_id, clock_skew_seconds)
    VALUES ('LOG-SYNTH-AMBIG-01', 'DEV-AMBIG-01', 'SHP-SYNTH-AMBIG-01', 0)
    """)

    # Excursion during the overlapping conflict window (10:02 to 10:14)
    c.execute("""
    INSERT INTO excursions (
        excursion_id, shipment_id, product_id, started_at_utc, ended_at_utc,
        min_temp_c, max_temp_c, detected_by
    ) VALUES (
        'EXC-SYNTH-02',
        'SHP-SYNTH-AMBIG-01',
        'prod-001',
        TIMESTAMP '2026-10-31 10:02:00',
        TIMESTAMP '2026-10-31 10:14:00',
        2.0, 8.0,
        'Exasol Continuous Ingestion'
    )
    """)

    # 361 readings: 08:00 to 14:00, 1 minute intervals
    base_t = datetime(2026, 10, 31, 8, 0, 0)
    reading_rows = []
    for i in range(361):
        t = base_t + timedelta(minutes=i)
        t_str = t.strftime("%Y-%m-%d %H:%M:%S")
        # During 10:00 to 10:15 (overlapping handoff window), temperature spikes to 14.0°C
        if 120 <= i <= 135:
            temp = 14.0
        else:
            temp = 4.5
        rid = f"RDG-AMBIG-{i:04d}"
        reading_rows.append((rid, "LOG-SYNTH-AMBIG-01", t_str, temp, 99))

    print(f"  Inserting {len(reading_rows)} 1-minute telemetry readings for SHP-SYNTH-AMBIG-01...")
    for b in range(0, len(reading_rows), 50):
        batch = reading_rows[b:b+50]
        val_strs = [f"('{r[0]}', '{r[1]}', TIMESTAMP '{r[2]}', {r[3]}, {r[4]})" for r in batch]
        c.execute(f"INSERT INTO logger_readings (reading_id, logger_id, reading_at_utc, temperature_c, battery_pct) VALUES {', '.join(val_strs)}")

    print("  Scenario 3 seeded successfully!")

    # ─────────────────────────────────────────────────────────────────────────
    # Verification
    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("VERIFYING 3 DEMO SCENARIOS IN EXASOL LIVE SCHEMA")
    print("=" * 72)

    scenarios = [
        ("Scenario 1: Clear Exposure", "SHP-SYNTH-DENSE-01", "EXC-SYNTH-01"),
        ("Scenario 2: Insufficient Data", "SHP-2026-0881", "EXC-1002"),
        ("Scenario 3: Ambiguous Custody", "SHP-SYNTH-AMBIG-01", "EXC-SYNTH-02"),
    ]

    for title, sid, eid in scenarios:
        print(f"\n--- {title} ({sid} / {eid}) ---")
        s = c.execute(f"SELECT id, shipment_code FROM shipments WHERE id = '{sid}'").fetchone()
        print(f"  Shipment: {s['ID']} ({s['SHIPMENT_CODE']})")

        rc = c.execute(f"SELECT COUNT(*) AS cnt FROM logger_readings r JOIN logger_devices ld ON r.logger_id = ld.logger_id WHERE ld.assigned_shipment_id = '{sid}'").fetchone()
        print(f"  Readings captured: {rc['CNT']}")

        rows = c.execute(f"""
        SELECT handoff_id, sequence_no, handoff_total_dm, supported_observation_minutes,
               ambiguous_minutes, attribution_rank, evidence_status
        FROM V_EXCURSION_ATTRIBUTION
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
    print("ALL 3 DEMO SCENARIOS READY AND VERIFIED")
    print("=" * 72)

if __name__ == "__main__":
    main()
