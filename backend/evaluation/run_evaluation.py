"""
HandoffGuard — Phase B Synthetic Evaluation
============================================
Reproducible command that evaluates the primary attribution target:
  "Handoff with the largest supported out-of-range exposure within an excursion window."

This is NOT root-cause identification. It is an evidence-aid ranking for
quality-team investigation support only.

Ground-truth metadata is stored separately in synthetic_ground_truth.json and is
NEVER exposed to or queried by production attribution views.

Outputs:
  reports/attribution_evaluation.json   — machine-readable results
  reports/attribution_evaluation.md     — human-readable summary

Label: Synthetic evaluation — not field validation.

Usage:
  python backend/evaluation/run_evaluation.py

Requirements:
  - Exasol running on localhost:8563
  - db/migrations/005_repair_analytics_views.sql present
  - reports/ directory present (created automatically)
"""

import sys
import ssl
import json
import datetime
from pathlib import Path

import pyexasol

EVAL_SCHEMA = "HANDOFFGUARD_EVAL"
MIGRATION_SQL = Path(__file__).resolve().parent.parent.parent / "db" / "migrations" / "005_repair_analytics_views.sql"
GROUND_TRUTH_FILE = Path(__file__).resolve().parent / "synthetic_ground_truth.json"
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"

PRODUCT_MIN_C = 2.0
PRODUCT_MAX_C = 8.0


# ─────────────────────────────────────────────────────────────────────────────
# Schema Setup
# ─────────────────────────────────────────────────────────────────────────────

def setup_eval_schema(c):
    """Create isolated evaluation schema and seed tables."""
    c.execute(f"DROP SCHEMA IF EXISTS {EVAL_SCHEMA} CASCADE")
    c.execute(f"CREATE SCHEMA {EVAL_SCHEMA}")
    c.execute(f"OPEN SCHEMA {EVAL_SCHEMA}")

    c.execute("""
    CREATE TABLE PRODUCTS (
        ID VARCHAR(50) PRIMARY KEY,
        NAME VARCHAR(100),
        MIN_TEMP_C DOUBLE,
        MAX_TEMP_C DOUBLE,
        MAX_EXCURSION_MINUTES INT
    )""")

    c.execute("""
    CREATE TABLE SHIPMENTS (
        ID VARCHAR(50) PRIMARY KEY,
        SHIPMENT_CODE VARCHAR(50),
        PRODUCT_ID VARCHAR(50)
    )""")

    c.execute("""
    CREATE TABLE LOGGER_DEVICES (
        LOGGER_ID VARCHAR(50) PRIMARY KEY,
        DEVICE_CODE VARCHAR(50),
        ASSIGNED_SHIPMENT_ID VARCHAR(50),
        CLOCK_SKEW_SECONDS INT
    )""")

    c.execute("""
    CREATE TABLE LOGGER_READINGS (
        READING_ID VARCHAR(50) PRIMARY KEY,
        LOGGER_ID VARCHAR(50),
        READING_AT_UTC TIMESTAMP(3),
        TEMPERATURE_C DOUBLE,
        BATTERY_PCT INT,
        CREATED_AT TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""
    CREATE TABLE HANDOFFS (
        ID VARCHAR(50) PRIMARY KEY,
        SHIPMENT_ID VARCHAR(50),
        SEQUENCE_NUMBER INT,
        HANDOFF_TYPE VARCHAR(100),
        FROM_PARTY VARCHAR(100),
        TO_PARTY VARCHAR(100),
        LOCATION VARCHAR(100),
        PLANNED_START_AT TIMESTAMP(3),
        ACTUAL_START_AT TIMESTAMP(3),
        PLANNED_END_AT TIMESTAMP(3),
        ACTUAL_END_AT TIMESTAMP(3)
    )""")

    c.execute("""
    CREATE TABLE EXCURSIONS (
        EXCURSION_ID VARCHAR(50) PRIMARY KEY,
        SHIPMENT_ID VARCHAR(50),
        PRODUCT_ID VARCHAR(50),
        STARTED_AT_UTC TIMESTAMP(3),
        ENDED_AT_UTC TIMESTAMP(3),
        MIN_TEMP_C DOUBLE,
        MAX_TEMP_C DOUBLE,
        DETECTED_BY VARCHAR(100)
    )""")

    # Apply production migration SQL retargeted to HANDOFFGUARD_EVAL
    raw = MIGRATION_SQL.read_text(encoding="utf-8")
    retargeted = raw.replace("HANDOFFGUARD", EVAL_SCHEMA)
    stmts = []
    current = []
    for line in retargeted.splitlines():
        s = line.strip()
        if s.startswith("--") or not s:
            continue
        current.append(line)
        if s.endswith(";"):
            text = "\n".join(current).strip().rstrip(";").strip()
            if text:
                stmts.append(text)
            current = []
    for stmt in stmts:
        c.execute(stmt)

    print(f"  Eval schema '{EVAL_SCHEMA}' ready ({len(stmts)} migration statements applied)")


def teardown_eval_schema(c):
    c.execute(f"DROP SCHEMA IF EXISTS {EVAL_SCHEMA} CASCADE")


# ─────────────────────────────────────────────────────────────────────────────
# Fixture Helpers
# ─────────────────────────────────────────────────────────────────────────────

def ts(dt_str):
    """Return SQL TIMESTAMP literal for an ISO datetime string."""
    return f"TIMESTAMP '{dt_str}'"


def seed_product(c):
    c.execute(f"""
    INSERT INTO PRODUCTS VALUES
      ('PROD-VACC', 'Test Vaccine', {PRODUCT_MIN_C}, {PRODUCT_MAX_C}, 30)
    """)


def seed_shipment(c, shp_id, code):
    c.execute(f"INSERT INTO SHIPMENTS VALUES ('{shp_id}', '{code}', 'PROD-VACC')")


def seed_logger(c, logger_id, shp_id, skew_s=0):
    c.execute(f"INSERT INTO LOGGER_DEVICES VALUES ('{logger_id}', 'DEV-{logger_id}', '{shp_id}', {skew_s})")


def seed_handoff(c, hid, shp_id, seq, htype, start, end):
    c.execute(f"""
    INSERT INTO HANDOFFS VALUES
      ('{hid}', '{shp_id}', {seq}, '{htype}', 'Party-A', 'Party-B', 'Loc-{hid}',
       {ts(start)}, {ts(start)},
       {ts(end)}, {ts(end)})
    """)


def seed_reading(c, rid, logger_id, at_utc, temp_c):
    c.execute(f"""
    INSERT INTO LOGGER_READINGS (READING_ID, LOGGER_ID, READING_AT_UTC, TEMPERATURE_C, BATTERY_PCT)
    VALUES ('{rid}', '{logger_id}', {ts(at_utc)}, {temp_c}, 100)
    """)


def seed_excursion(c, eid, shp_id, start, end):
    c.execute(f"""
    INSERT INTO EXCURSIONS VALUES
      ('{eid}', '{shp_id}', 'PROD-VACC',
       {ts(start)}, {ts(end)}, {PRODUCT_MIN_C}, {PRODUCT_MAX_C}, 'Logger')
    """)


def query_attribution(c, excursion_id):
    """Query V_EXCURSION_ATTRIBUTION for a given excursion and return rows as dicts."""
    rows = c.execute(f"""
    SELECT
        excursion_id, handoff_id, sequence_no, handoff_type,
        window_source, reading_count, supported_observation_minutes,
        handoff_total_dm, total_excursion_dm,
        attribution_rank, evidence_status
    FROM {EVAL_SCHEMA}.V_EXCURSION_ATTRIBUTION
    WHERE excursion_id = '{excursion_id}'
    ORDER BY attribution_rank, handoff_id
    """).fetchall()
    return rows


def naive_baseline_handoff(c, excursion_id):
    """
    Naive baseline: first observed out-of-range reading's handoff.
    Uses uncorrected timestamps and simple >= / <= boundary (inclusive).
    This is the naive approach; the primary target uses corrected, half-open intervals.
    """
    row = c.execute(f"""
    SELECT h.id AS handoff_id
    FROM {EVAL_SCHEMA}.LOGGER_READINGS r
    JOIN {EVAL_SCHEMA}.LOGGER_DEVICES ld ON r.logger_id = ld.logger_id
    JOIN {EVAL_SCHEMA}.HANDOFFS h
      ON ld.assigned_shipment_id = h.shipment_id
     AND r.reading_at_utc >= h.actual_start_at
     AND r.reading_at_utc <= h.actual_end_at
    JOIN {EVAL_SCHEMA}.EXCURSIONS e
      ON ld.assigned_shipment_id = e.shipment_id
    WHERE e.excursion_id = '{excursion_id}'
      AND r.temperature_c > {PRODUCT_MAX_C}
    ORDER BY r.reading_at_utc
    LIMIT 1
    """).fetchone()
    return row["HANDOFF_ID"] if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Test Cases
# ─────────────────────────────────────────────────────────────────────────────

def seed_case_01(c):
    """EVAL-01: Clear single-handoff exposure (all OOR readings in H2)."""
    seed_shipment(c, "SHP-E01", "EVAL-01")
    seed_logger(c, "EL1", "SHP-E01", skew_s=0)
    seed_handoff(c, "EH1", "SHP-E01", 1, "Cold Storage", "2026-11-01 08:00:00", "2026-11-01 10:00:00")
    seed_handoff(c, "EH2", "SHP-E01", 2, "Reefer Truck",  "2026-11-01 10:00:00", "2026-11-01 12:00:00")
    seed_handoff(c, "EH3", "SHP-E01", 3, "Pharmacy",      "2026-11-01 12:00:00", "2026-11-01 14:00:00")
    # 6 readings at 10:00, 10:10, 10:20, 10:30, 10:40, 10:50 — all at 10.0°C (OOR)
    for i, (minute, temp) in enumerate([
        ("10:00:00", 5.0),   # In-range, in H2 (boundary)
        ("10:10:00", 10.0),  # OOR, H2
        ("10:20:00", 10.0),  # OOR, H2
        ("10:30:00", 10.0),  # OOR, H2
        ("10:40:00", 10.0),  # OOR, H2
        ("10:50:00", 10.0),  # OOR, H2
        ("11:00:00", 5.0),   # In-range, H2
    ]):
        seed_reading(c, f"ER1-{i}", "EL1", f"2026-11-01 {minute}", temp)
    # Excursion: 10:05 to 10:55
    seed_excursion(c, "EXC-E01", "SHP-E01", "2026-11-01 10:05:00", "2026-11-01 10:55:00")


def seed_case_02(c):
    """EVAL-02: Excursion spanning two handoffs. H2 gets 75% OOR exposure, H3 gets 25%."""
    seed_shipment(c, "SHP-E02", "EVAL-02")
    seed_logger(c, "FL1", "SHP-E02", skew_s=0)
    seed_handoff(c, "FH1", "SHP-E02", 1, "Warehouse",    "2026-11-02 08:00:00", "2026-11-02 10:00:00")
    seed_handoff(c, "FH2", "SHP-E02", 2, "Reefer Truck", "2026-11-02 10:00:00", "2026-11-02 11:00:00")
    seed_handoff(c, "FH3", "SHP-E02", 3, "Last Mile",    "2026-11-02 11:00:00", "2026-11-02 12:00:00")
    # 6 readings at 10-min intervals, all at 10°C (OOR), spanning FH2 and FH3
    for i, minute in enumerate(["09:50:00", "10:00:00", "10:10:00", "10:20:00",
                                 "10:30:00", "10:40:00", "10:50:00",
                                 "11:00:00", "11:10:00", "11:20:00", "11:30:00"]):
        temp = 5.0 if minute in ("09:50:00",) else 10.0
        seed_reading(c, f"FR1-{i}", "FL1", f"2026-11-02 {minute}", temp)
    # Excursion: 10:00 to 11:20 — FH2 gets 60 min, FH3 gets 20 min of OOR exposure
    # FH2 overlap: 10:00->11:00 (60 min, all OOR) = 6 segs × 10 min × 2°C = 120 DM
    # FH3 overlap: 11:00->11:20 (20 min, all OOR) = 2 segs × 10 min × 2°C = 40 DM
    seed_excursion(c, "EXC-E02", "SHP-E02", "2026-11-02 10:00:00", "2026-11-02 11:20:00")


def seed_case_03(c):
    """EVAL-03: Tied exposure. Two handoffs, each with exactly 30 min of OOR exposure at same temperature."""
    seed_shipment(c, "SHP-E03", "EVAL-03")
    seed_logger(c, "GL1", "SHP-E03", skew_s=0)
    seed_handoff(c, "GH1", "SHP-E03", 1, "Cold Storage", "2026-11-03 09:00:00", "2026-11-03 10:00:00")
    seed_handoff(c, "GH2", "SHP-E03", 2, "Reefer Truck", "2026-11-03 10:00:00", "2026-11-03 11:00:00")
    # 7 readings at 10-min intervals all at 10°C (OOR), 3 in GH1, 3 in GH2
    for i, minute in enumerate(["09:00:00", "09:10:00", "09:20:00", "09:30:00",
                                 "09:40:00", "09:50:00",
                                 "10:00:00", "10:10:00", "10:20:00", "10:30:00",
                                 "10:40:00", "10:50:00", "11:00:00"]):
        seed_reading(c, f"GR1-{i}", "GL1", f"2026-11-03 {minute}", 10.0)
    # Excursion: spans both handoffs fully — each contributes equal exposure
    seed_excursion(c, "EXC-E03", "SHP-E03", "2026-11-03 09:00:00", "2026-11-03 11:00:00")


def seed_case_04(c):
    """EVAL-04: Clock offset +300s. Without correction, readings appear 5 min early.
    Corrected readings land in KH2 (correct). Naive baseline using uncorrected timestamps
    assigns first OOR reading to KH1 (wrong).
    """
    seed_shipment(c, "SHP-E04", "EVAL-04")
    seed_logger(c, "KL1", "SHP-E04", skew_s=300)  # device clock +300s fast
    seed_handoff(c, "KH1", "SHP-E04", 1, "Warehouse",    "2026-11-04 09:00:00", "2026-11-04 10:00:00")
    seed_handoff(c, "KH2", "SHP-E04", 2, "Reefer Truck", "2026-11-04 10:00:00", "2026-11-04 11:00:00")
    # Readings raw at 09:55, 10:05, 10:15, 10:25 — all OOR at 10°C
    # Corrected (subtract 300s): 09:50, 10:00, 10:10, 10:20
    # 09:50 lands in KH1 (but is in-range per corrected below), 10:00-10:20 land in KH2
    for i, (raw_minute, temp) in enumerate([
        ("09:55:00", 5.0),   # corrected to 09:50 — in KH1, in-range
        ("10:05:00", 10.0),  # corrected to 10:00 — in KH2, OOR
        ("10:15:00", 10.0),  # corrected to 10:10 — in KH2, OOR
        ("10:25:00", 10.0),  # corrected to 10:20 — in KH2, OOR
        ("10:35:00", 10.0),  # corrected to 10:30 — in KH2, OOR
        ("10:45:00", 5.0),   # corrected to 10:40 — in KH2, in-range
    ]):
        seed_reading(c, f"KR1-{i}", "KL1", f"2026-11-04 {raw_minute}", temp)
    # Excursion: 10:00 to 10:35 (corrected window)
    seed_excursion(c, "EXC-E04", "SHP-E04", "2026-11-04 10:00:00", "2026-11-04 10:35:00")


def seed_case_05(c):
    """EVAL-05: Only two readings, gap >600s. All segments unsupported. Should be INCONCLUSIVE."""
    seed_shipment(c, "SHP-E05", "EVAL-05")
    seed_logger(c, "ML1", "SHP-E05", skew_s=0)
    seed_handoff(c, "MH1", "SHP-E05", 1, "Reefer Truck", "2026-11-05 09:00:00", "2026-11-05 11:00:00")
    # Only 2 readings, 90 min apart (5400s >> 600s threshold)
    seed_reading(c, "MR1-0", "ML1", "2026-11-05 09:00:00", 10.0)
    seed_reading(c, "MR1-1", "ML1", "2026-11-05 10:30:00", 10.0)
    seed_excursion(c, "EXC-E05", "SHP-E05", "2026-11-05 09:00:00", "2026-11-05 10:30:00")


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation Logic
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_case(c, case_meta, exc_id, case_name):
    """Run primary + naive queries for one case, compare against ground truth."""
    rows = query_attribution(c, exc_id)
    naive_hid = naive_baseline_handoff(c, exc_id)

    expected_hid   = case_meta["expected_primary_handoff"]
    expected_status = case_meta["expected_evidence_status"]
    expected_outcome = case_meta["expected_outcome"]

    # Derive primary result
    if not rows:
        primary_hid = None
        actual_status = "NO_ROWS_RETURNED"
        actual_outcome = "INCONCLUSIVE"
        top_dm = None
    else:
        statuses = [r["EVIDENCE_STATUS"] for r in rows]

        # Check if all rows are inconclusive / insufficient
        if all(s in ("INCONCLUSIVE_INSUFFICIENT_DATA", "INCONCLUSIVE_MULTI_LOGGER",
                     "EXCLUDED_PLANNED_ONLY") for s in statuses):
            primary_hid = None
            actual_status = statuses[0]
            actual_outcome = "INCONCLUSIVE"
            top_dm = None
        else:
            # rank 1 rows (largest supported exposure)
            rank1 = [r for r in rows if r["ATTRIBUTION_RANK"] == 1]
            if len(rank1) > 1:
                actual_outcome = "TIED_NO_UNIQUE_WINNER"
                primary_hid = None
                actual_status = rank1[0]["EVIDENCE_STATUS"]
                top_dm = float(rank1[0]["HANDOFF_TOTAL_DM"] or 0)
            else:
                primary_hid = rank1[0]["HANDOFF_ID"] if rank1 else None
                actual_status = rank1[0]["EVIDENCE_STATUS"] if rank1 else statuses[0]
                actual_outcome = "PRIMARY_MATCHES_GROUND_TRUTH" if primary_hid == expected_hid else "PRIMARY_MISMATCH"
                top_dm = float(rank1[0]["HANDOFF_TOTAL_DM"] or 0) if rank1 else None

    # Score
    primary_correct = (actual_outcome == expected_outcome)
    naive_correct = (naive_hid == case_meta.get("naive_baseline_first_oor_handoff"))
    naive_matches_primary_expected = case_meta.get("naive_matches_primary")

    result = {
        "case_id": case_meta["case_id"],
        "case_name": case_name,
        "description": case_meta["description"],
        "excursion_id": exc_id,
        "expected_primary_handoff": expected_hid,
        "actual_primary_handoff": primary_hid,
        "actual_evidence_status": actual_status,
        "expected_evidence_status": expected_status,
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "primary_correct": primary_correct,
        "top_exposure_dm": top_dm,
        "naive_baseline_handoff": naive_hid,
        "naive_expected_handoff": case_meta.get("naive_baseline_first_oor_handoff"),
        "naive_correct": naive_correct,
        "naive_matches_primary_expected": naive_matches_primary_expected,
        "attribution_rows": [
            {
                "handoff_id": r["HANDOFF_ID"],
                "rank": int(r["ATTRIBUTION_RANK"]) if r["ATTRIBUTION_RANK"] is not None else None,
                "evidence_status": r["EVIDENCE_STATUS"],
                "supported_obs_min": float(r["SUPPORTED_OBSERVATION_MINUTES"] or 0),
                "handoff_total_dm": float(r["HANDOFF_TOTAL_DM"] or 0),
                "reading_count": int(r["READING_COUNT"] or 0),
            }
            for r in rows
        ],
    }

    status_icon = "PASS" if primary_correct else "FAIL"
    print(f"  [{status_icon}] {case_meta['case_id']}: outcome={actual_outcome}  "
          f"primary={primary_hid}  naive={naive_hid}  dm={top_dm}")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Report Generation
# ─────────────────────────────────────────────────────────────────────────────

def write_json_report(results, summary, output_path):
    report = {
        "_label": "Synthetic evaluation -- not field validation.",
        "_note": (
            "Primary target: handoff with the largest supported out-of-range "
            "exposure within an excursion window. This is NOT root-cause identification."
        ),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": summary,
        "cases": results,
    }
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"  JSON report written: {output_path}")


def write_md_report(results, summary, output_path):
    lines = [
        "# HandoffGuard — Attribution Evaluation Report",
        "",
        "> **Synthetic evaluation — not field validation.**  ",
        "> Primary target: *handoff with the largest supported out-of-range exposure within an excursion window.*  ",
        "> This is evidence-aid ranking for quality-team investigation support only — not root-cause identification.",
        "",
        f"Generated: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total cases | {summary['total_cases']} |",
        f"| Primary algorithm correct | {summary['primary_correct']} / {summary['total_cases']} |",
        f"| Naive baseline correct | {summary['naive_correct']} / {summary['total_cases']} |",
        f"| Primary accuracy | {summary['primary_accuracy_pct']:.1f}% |",
        f"| Naive accuracy | {summary['naive_accuracy_pct']:.1f}% |",
        "",
        "---",
        "",
        "## Case-by-Case Results",
        "",
    ]

    for r in results:
        icon = "✅" if r["primary_correct"] else "❌"
        lines += [
            f"### {icon} {r['case_id']} — {r['case_name']}",
            "",
            f"_{r['description']}_",
            "",
            f"| Field | Value |",
            f"|---|---|",
            f"| Excursion | `{r['excursion_id']}` |",
            f"| Expected primary handoff | `{r['expected_primary_handoff']}` |",
            f"| Actual primary handoff | `{r['actual_primary_handoff']}` |",
            f"| Top exposure (°C·min) | {r['top_exposure_dm'] if r['top_exposure_dm'] is not None else '—'} |",
            f"| Evidence status | `{r['actual_evidence_status']}` |",
            f"| Expected outcome | `{r['expected_outcome']}` |",
            f"| Actual outcome | `{r['actual_outcome']}` |",
            f"| Primary correct | {'Yes' if r['primary_correct'] else 'No'} |",
            f"| Naive baseline handoff | `{r['naive_baseline_handoff']}` |",
            f"| Naive correct | {'Yes' if r['naive_correct'] else 'No'} |",
            "",
        ]

        if r["attribution_rows"]:
            lines += [
                "**Attribution rows returned by V_EXCURSION_ATTRIBUTION:**",
                "",
                "| Handoff | Rank | Obs Min | DM (°C·min) | Status |",
                "|---|---|---|---|---|",
            ]
            for row in r["attribution_rows"]:
                lines.append(
                    f"| `{row['handoff_id']}` | {row['rank']} | "
                    f"{row['supported_obs_min']:.1f} | {row['handoff_total_dm']:.2f} | "
                    f"`{row['evidence_status']}` |"
                )
            lines.append("")
        else:
            lines += ["_No attribution rows returned._", ""]

    lines += [
        "---",
        "",
        "## Methodology Notes",
        "",
        "- **Primary target**: handoff with `MAX(handoff_total_dm)` within the excursion window, "
          "using supported sensor segments (gap ≤ 600 s).",
        "- **Naive baseline**: handoff containing the first observed out-of-range reading, "
          "using uncorrected raw timestamps and inclusive `>=` / `<=` boundaries.",
        "- **Clock correction**: primary target applies `corrected_time = reading_at_utc − clock_skew_seconds`.",
        "- **Ambiguous custody**: segments overlapping multiple handoffs are excluded from attributable exposure.",
        "- **Insufficient data**: if all segments are unsupported (gap > 600 s), status = `INCONCLUSIVE_INSUFFICIENT_DATA`.",
        "- **Tied exposure**: if two handoffs share rank 1, no unique winner is reported.",
        "",
        "> Gap threshold of 600 s is an engineering/demo prototype assumption — "
        "not a validated pharmaceutical standard.",
        "",
        "---",
        "",
        "*Synthetic evaluation — not field validation.*",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Markdown report written: {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("HandoffGuard — Phase B Synthetic Evaluation")
    print("Synthetic evaluation -- not field validation.")
    print("=" * 72)

    # Validate prerequisites
    if not MIGRATION_SQL.exists():
        print(f"ERROR: Migration file not found: {MIGRATION_SQL}")
        sys.exit(1)
    if not GROUND_TRUTH_FILE.exists():
        print(f"ERROR: Ground truth file not found: {GROUND_TRUTH_FILE}")
        sys.exit(1)

    gt = json.loads(GROUND_TRUTH_FILE.read_text(encoding="utf-8"))
    gt_by_id = {c["case_id"]: c for c in gt["cases"]}

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    c = pyexasol.connect(
        dsn="localhost:8563",
        user="sys",
        password="exasol",
        encryption=True,
        fetch_dict=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
    )

    print("\n[1/3] Setting up isolated evaluation schema...")
    setup_eval_schema(c)

    print("\n[2/3] Seeding fixtures and running evaluation...")
    seed_product(c)

    CASES = [
        ("EVAL-01-SINGLE-HANDOFF", seed_case_01, "EXC-E01", "Clear Single-Handoff Exposure"),
        ("EVAL-02-SPANNING",       seed_case_02, "EXC-E02", "Exposure Spanning Two Handoffs"),
        ("EVAL-03-TIED",           seed_case_03, "EXC-E03", "Tied Exposure — No Unique Winner"),
        ("EVAL-04-CLOCK-OFFSET",   seed_case_04, "EXC-E04", "Clock Offset +300s Correction"),
        ("EVAL-05-MISSING-READINGS", seed_case_05, "EXC-E05", "Missing Readings — Inconclusive"),
    ]

    results = []
    for case_id, seed_fn, exc_id, case_name in CASES:
        seed_fn(c)
        case_meta = gt_by_id[case_id]
        result = evaluate_case(c, case_meta, exc_id, case_name)
        results.append(result)

    print("\n[3/3] Cleaning up and writing reports...")
    teardown_eval_schema(c)

    primary_correct = sum(1 for r in results if r["primary_correct"])
    naive_correct   = sum(1 for r in results if r["naive_correct"])
    total = len(results)
    summary = {
        "total_cases": total,
        "primary_correct": primary_correct,
        "naive_correct": naive_correct,
        "primary_accuracy_pct": (primary_correct / total * 100) if total else 0,
        "naive_accuracy_pct":   (naive_correct   / total * 100) if total else 0,
    }

    json_path = REPORTS_DIR / "attribution_evaluation.json"
    md_path   = REPORTS_DIR / "attribution_evaluation.md"
    write_json_report(results, summary, json_path)
    write_md_report(results, summary, md_path)

    print()
    print("=" * 72)
    print(f"EVALUATION COMPLETE")
    print(f"  Primary algorithm: {primary_correct}/{total} correct "
          f"({summary['primary_accuracy_pct']:.1f}%)")
    print(f"  Naive baseline:    {naive_correct}/{total} correct "
          f"({summary['naive_accuracy_pct']:.1f}%)")
    print("=" * 72)

    if primary_correct < total:
        print(f"\nWARNING: {total - primary_correct} case(s) did not match expected outcome.")
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
