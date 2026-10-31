"""
HandoffGuard — Exasol Database Initialization Script
===================================================
Creates base tables and analytical views from 005_repair_analytics_views.sql.
Idempotent and safe to run multiple times.

Usage:
  python scripts/init_exasol_db.py [--schema SCHEMA_NAME]
"""

import os
import sys
import argparse
import ssl
from pathlib import Path
import pyexasol

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_SQL_PATH = REPO_ROOT / "db" / "migrations" / "005_repair_analytics_views.sql"

def parse_args():
    parser = argparse.ArgumentParser(description="Initialize HandoffGuard Exasol schema and views")
    parser.add_argument("--schema", default=os.getenv("EXASOL_SCHEMA", "HANDOFFGUARD"), help="Target Exasol schema name")
    parser.add_argument("--host", default=os.getenv("EXASOL_HOST", "localhost"), help="Exasol host")
    parser.add_argument("--port", type=int, default=int(os.getenv("EXASOL_PORT", 8563)), help="Exasol port")
    parser.add_argument("--user", default=os.getenv("EXASOL_USER", "sys"), help="Exasol user")
    parser.add_argument("--password", default=os.getenv("EXASOL_PASSWORD", "exasol"), help="Exasol password")
    return parser.parse_args()

def init_db(host, port, user, password, target_schema):
    print("=" * 72)
    print(f"Initializing HandoffGuard Database in Schema: {target_schema}")
    print(f"Connecting to Exasol at {host}:{port}...")
    print("=" * 72)

    c = pyexasol.connect(
        dsn=f"{host}:{port}",
        user=user,
        password=password,
        encryption=True,
        fetch_dict=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
    )

    # 1. Create Schema
    c.execute(f"CREATE SCHEMA IF NOT EXISTS {target_schema}")
    c.execute(f"OPEN SCHEMA {target_schema}")
    print(f"Schema {target_schema} ready.")

    # 2. Base Tables
    c.execute(f"""
    CREATE TABLE IF NOT EXISTS {target_schema}.PRODUCTS (
        ID VARCHAR(50) PRIMARY KEY,
        NAME VARCHAR(100),
        MIN_TEMP_C DOUBLE,
        MAX_TEMP_C DOUBLE,
        MAX_EXCURSION_MINUTES INT
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS {target_schema}.SHIPMENTS (
        ID VARCHAR(50) PRIMARY KEY,
        SHIPMENT_CODE VARCHAR(50),
        PRODUCT_ID VARCHAR(50),
        ORIGIN VARCHAR(100),
        DESTINATION VARCHAR(100),
        DISPATCHED_AT TIMESTAMP,
        EXPECTED_DELIVERY_AT TIMESTAMP,
        ACTUAL_DELIVERY_AT TIMESTAMP,
        STATUS VARCHAR(50),
        PRIORITY VARCHAR(20),
        OVERALL_RISK_SCORE DOUBLE,
        CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS {target_schema}.LOGGER_DEVICES (
        LOGGER_ID VARCHAR(50) PRIMARY KEY,
        DEVICE_CODE VARCHAR(50),
        MODEL VARCHAR(50),
        FIRMWARE VARCHAR(50),
        ASSIGNED_SHIPMENT_ID VARCHAR(50),
        CLOCK_SKEW_SECONDS INT,
        CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS {target_schema}.LOGGER_READINGS (
        READING_ID VARCHAR(50) PRIMARY KEY,
        LOGGER_ID VARCHAR(50),
        READING_AT_UTC TIMESTAMP(3),
        TEMPERATURE_C DOUBLE,
        BATTERY_PCT DOUBLE,
        CREATED_AT TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS {target_schema}.HANDOFFS (
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
        ACTUAL_END_AT TIMESTAMP(3),
        DWELL_MINUTES INT DEFAULT 0,
        TEMPERATURE_LOG_AVAILABLE BOOLEAN DEFAULT TRUE,
        RISK_SCORE DOUBLE DEFAULT 0,
        RISK_LEVEL VARCHAR(20) DEFAULT 'LOW',
        NOTES VARCHAR(500),
        CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS {target_schema}.EXCURSIONS (
        EXCURSION_ID VARCHAR(50) PRIMARY KEY,
        SHIPMENT_ID VARCHAR(50),
        PRODUCT_ID VARCHAR(50),
        STARTED_AT_UTC TIMESTAMP(3),
        ENDED_AT_UTC TIMESTAMP(3),
        MIN_TEMP_C DOUBLE,
        MAX_TEMP_C DOUBLE,
        DETECTED_BY VARCHAR(100),
        CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("Base tables verified.")

    # 3. Create Analytical Views from 005_repair_analytics_views.sql
    if not MIGRATION_SQL_PATH.exists():
        raise FileNotFoundError(f"Missing migration SQL: {MIGRATION_SQL_PATH}")

    raw_sql = MIGRATION_SQL_PATH.read_text(encoding="utf-8")
    retargeted_sql = raw_sql.replace("HANDOFFGUARD.", f"{target_schema}.").replace(
        "OPEN SCHEMA HANDOFFGUARD;", f"OPEN SCHEMA {target_schema};"
    )

    statements = []
    current_stmt = []
    for line in retargeted_sql.splitlines():
        if line.strip().startswith("--"):
            continue
        current_stmt.append(line)
        if line.strip().endswith(";"):
            full_s = "\n".join(current_stmt).strip().rstrip(";")
            if full_s:
                statements.append(full_s)
            current_stmt = []

    view_stmts = [s for s in statements if "CREATE OR REPLACE VIEW" in s.upper()]
    for s in view_stmts:
        c.execute(s)
    print(f"Applied {len(view_stmts)} analytical views from 005_repair_analytics_views.sql.")

    # Verify Views
    views = c.execute(f"SELECT VIEW_NAME FROM EXA_ALL_VIEWS WHERE VIEW_SCHEMA = '{target_schema}' ORDER BY VIEW_NAME").fetchall()
    view_names = [v['VIEW_NAME'] for v in views]
    print(f"Verified views in {target_schema}: {view_names}")
    c.close()

def main():
    args = parse_args()
    init_db(args.host, args.port, args.user, args.password, args.schema)

if __name__ == "__main__":
    main()
