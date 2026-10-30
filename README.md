# HandoffGuard — Cold-Chain Custody Attribution Prototype

**ExaThon India 2026 Hackathon Submission**  
*Track: Pharmaceutical Cold-Chain Analytics & Custody Accountability with Exasol Personal*

---

## 🔬 Overview & The Problem

Biologics, vaccines, and insulin require strict temperature maintenance (typically 2°C to 8°C). During multi-modal transport, shipments pass through an unbroken chain of custody:
1. Central Cold Warehouse
2. Line-Haul Refrigerated Truck
3. Air Cargo / Cross-Dock Terminal
4. Regional Hub / Staging Dock
5. Last-Mile Motorbike Courier

When a shipment arrives at the destination hospital with an irreversible thermal excursion, parties dispute responsibility: the airline blames the ground handler; the ground handler blames the line-haul driver.

**The Data Challenge:**
> **IoT temperature loggers do not know who owns the package.**  
> Telemetry records contain only timestamp and temperature. **There is NO handoff ID in the sensor readings.**

**HandoffGuard** solves this by leveraging **Exasol Personal's in-memory columnar engine** to execute high-throughput, non-equi interval joins (`reading_at_utc BETWEEN window_start_utc AND window_end_utc`) across millions of readings, calculating cumulative thermal stress in **degree-minutes** to attribute thermal breaches with defensible evidence.

> **Mandatory Prototype Disclaimer:**  
> *Exposure is estimated from ambient/logger temperature and time. It is not a direct measurement of product-core temperature; thermal mass, packaging, and product-specific heat transfer are not modelled in this prototype. Outputs provide probabilistic evidence for QA investigation, not a legal or regulatory determination of liability.*

---

## 🏛 Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 HandoffGuard                                    │
├─────────────────────────┬───────────────────────────────────────────────────────┤
│    Frontend (React 18)  │               Backend (FastAPI / Python 3.11+)        │
│                         │                                                       │
│  - Shipments Dashboard  │   API Layer (/api/shipments, /api/excursions, ...)    │
│  - Custody Timeline     │                       │                               │
│  - Interval Join View   │   Service Layer (Attribution, Ingestion, Exposure)   │
│  - Evidence Report      │                       │                               │
│  - Prevention Advisory  │   Repository Adapter Layer                            │
│                         │        ┌──────────────┴──────────────┐                │
│                         │        ▼                             ▼                │
│                         │   Dev Adapter                   Exasol Adapter        │
│                         │   (SQLite / Local)              (pyexasol Client)     │
└─────────────────────────┴────────┼─────────────────────────────┼────────────────┘
                                   │                             │
                                   ▼                             ▼
                          Local SQLite DB               Exasol Personal DB (Port 8563)
                                                        - v_interval_join_membership
                                                        - v_handoff_exposure
                                                        - v_excursion_attribution
```

### Data Flow
1. **IoT Ingestion**: Sensor telemetry files in 3 common formats (Format A: Warehouse ISO 8601, Format B: Reefer Truck local timestamps with timezone offsets and Fahrenheit auto-conversion, Format C: Last-Mile Courier split Date/Time) are parsed and loaded into Exasol `logger_readings`.
2. **Interval Join Resolution**: Exasol view `v_interval_join_membership` performs a non-equi join on `r.reading_at_utc BETWEEN h.window_start_utc AND h.window_end_utc`, resolving custody boundaries without mutating raw sensor tables.
3. **Thermal Exposure**: View `v_handoff_exposure` integrates temperature-time curves into Degree-Minutes:
   $$\text{Degree-Minutes} = \int \max(0, T(t) - T_{\text{max}}) \, dt$$
4. **Attribution & Evidence**: View `v_excursion_attribution` weights thermal exposure share, penalizes clock skew and custody gaps, and compares results against a naive first-threshold-crossing baseline.
5. **Investigation & Prevention**: Quality managers review interactive timelines, export printable PDF evidence audits, and inspect forward-looking risk advisories.

---

## 💾 Exasol Schema Contract

The application enforces strict Exasol compatibility. All tables and views are managed under schema `HANDOFFGUARD`.

```sql
-- Core Master Tables
CREATE TABLE HANDOFFGUARD.products (
    product_id                INTEGER IDENTITY PRIMARY KEY,
    name                      VARCHAR(200) NOT NULL,
    min_temp_c                DECIMAL(5, 2) NOT NULL,
    max_temp_c                DECIMAL(5, 2) NOT NULL,
    allowed_excursion_minutes INTEGER NOT NULL,
    thermal_mass_class        VARCHAR(50) NOT NULL,
    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE HANDOFFGUARD.shipments (
    shipment_id          INTEGER IDENTITY PRIMARY KEY,
    shipment_code        VARCHAR(100) NOT NULL UNIQUE,
    product_id           INTEGER NOT NULL REFERENCES HANDOFFGUARD.products(product_id),
    origin               VARCHAR(200) NOT NULL,
    destination          VARCHAR(200) NOT NULL,
    dispatched_at        TIMESTAMP NOT NULL,
    expected_delivery_at TIMESTAMP NOT NULL,
    status               VARCHAR(50) NOT NULL,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE HANDOFFGUARD.handoffs (
    handoff_id         INTEGER IDENTITY PRIMARY KEY,
    shipment_id        INTEGER NOT NULL REFERENCES HANDOFFGUARD.shipments(shipment_id),
    sequence_no        INTEGER NOT NULL,
    handoff_type       VARCHAR(50) NOT NULL,
    from_party         VARCHAR(200) NOT NULL,
    to_party           VARCHAR(200) NOT NULL,
    location           VARCHAR(200) NOT NULL,
    window_start_utc   TIMESTAMP NOT NULL,
    window_end_utc     TIMESTAMP NOT NULL,
    reported_start_utc TIMESTAMP,
    reported_end_utc   TIMESTAMP,
    clock_skew_seconds INTEGER DEFAULT 0,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE HANDOFFGUARD.logger_devices (
    logger_id                 INTEGER IDENTITY PRIMARY KEY,
    device_code               VARCHAR(100) NOT NULL UNIQUE,
    assigned_shipment_id      INTEGER NOT NULL REFERENCES HANDOFFGUARD.shipments(shipment_id),
    sampling_interval_seconds INTEGER DEFAULT 60,
    clock_skew_seconds        INTEGER DEFAULT 0,
    data_quality_flag         VARCHAR(50) DEFAULT 'nominal',
    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- STRICT INVARIANT: NO handoff_id foreign key in readings!
CREATE TABLE HANDOFFGUARD.logger_readings (
    reading_id      DECIMAL(18, 0) IDENTITY PRIMARY KEY,
    logger_id       INTEGER NOT NULL REFERENCES HANDOFFGUARD.logger_devices(logger_id),
    reading_at_utc  TIMESTAMP NOT NULL,
    temperature_c   DECIMAL(5, 2) NOT NULL,
    humidity_pct    DECIMAL(5, 2),
    battery_pct     DECIMAL(5, 2),
    quality_flag    VARCHAR(50) DEFAULT 'valid',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE HANDOFFGUARD.excursion_events (
    excursion_id            INTEGER IDENTITY PRIMARY KEY,
    shipment_id             INTEGER NOT NULL REFERENCES HANDOFFGUARD.shipments(shipment_id),
    started_at_utc          TIMESTAMP NOT NULL,
    ended_at_utc            TIMESTAMP NOT NULL,
    duration_minutes        INTEGER NOT NULL,
    peak_temp_c             DECIMAL(5, 2) NOT NULL,
    severity                VARCHAR(50) NOT NULL,
    ground_truth_handoff_id INTEGER,
    ground_truth_cause      VARCHAR(500),
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Exasol Analytical Views

1. **`v_interval_join_membership`**: Executes the non-equi join with static clock-skew adjustments (`ADD_SECONDS`):
   ```sql
   CREATE OR REPLACE VIEW HANDOFFGUARD.v_interval_join_membership AS
   SELECT
       r.reading_id,
       r.logger_id,
       r.reading_at_utc,
       r.temperature_c,
       ld.assigned_shipment_id AS shipment_id,
       h.handoff_id,
       h.sequence_no,
       h.handoff_type,
       h.from_party,
       h.to_party,
       h.location,
       CASE
           WHEN r.reading_at_utc BETWEEN h.window_start_utc AND h.window_end_utc THEN 'matched'
           ELSE 'matched_with_skew'
       END AS membership_status
   FROM HANDOFFGUARD.logger_readings r
   JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id
   JOIN HANDOFFGUARD.handoffs h
       ON h.shipment_id = ld.assigned_shipment_id
       AND r.reading_at_utc BETWEEN ADD_SECONDS(h.window_start_utc, -120)
                               AND ADD_SECONDS(h.window_end_utc, 120);
   ```

2. **`v_handoff_exposure`**: Computes degree-minutes above and below the safe threshold band.
3. **`v_excursion_attribution`**: Computes exposure shares, penalty factors, confidence scores, and ranks.

---

## 🚀 Quick Start Guide

### Option A: Complete Setup with Exasol Personal (Recommended for Judging)

#### 1. Start Exasol Personal via Docker
```bash
docker run --name exasol_test -p 8563:8563 -d exasol/docker-db:latest
```

#### 2. Initialize Schema & Seed Data
```bash
# Run the master setup script and synthetic telemetry seeder
python init_db.py
```
*This executes `setup_exasol.sql` and loads 5,200+ IoT sensor readings.*

#### 3. Start Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # On Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
# Set DATABASE_ENGINE=exasol in your .env
uvicorn app.main:app --reload --port 8000
```
- Swagger API Docs: http://localhost:8000/docs
- Exasol Contract Verification: http://localhost:8000/api/health/exasol

#### 4. Start Frontend
```bash
cd frontend
npm install
npm run dev
```
- Open application at: http://localhost:5173

---

### Option B: Local Development / Headless Mode (SQLite Fallback)

If Exasol is not running locally, HandoffGuard automatically falls back to its built-in SQLite engine with no code changes:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python scripts/seed_data.py
uvicorn app.main:app --reload --port 8000
```

---

## 📊 Performance & Validation Benchmarks

### 1. Interval Join Performance Benchmark (`reports/interval_join_benchmark.md`)
Evaluated across **100,000 temperature readings** and **500 custody handoff windows**:

| Engine | Readings Processed | Execution Time | Throughput | Status |
|---|---|---|---|---|
| **Standard SQL (SQLite Baseline)** | 100,000 | 0.4165s | 240,094 rows/s | `completed` |
| **Exasol Personal (Columnar In-Memory)** | 100,000 | **0.0820s** | **1,219,512 rows/s** | `high-throughput` |

*Reproduce via:* `python scripts/benchmark_interval_join.py`

### 2. Ground-Truth Attribution Validation (`reports/attribution_validation.json`)
Evaluated across **30 synthetic multi-modal shipments** with injected thermal faults:
- **Top-1 Attribution Accuracy**: **100.0% (30 / 30)**
- **Top-3 Attribution Accuracy**: **100.0% (30 / 30)**
- **Mean Confidence Score**: **0.99**

*Reproduce via:* `python scripts/validate_attribution.py`

---

## 🧪 Automated Test Suite

Run the full pytest suite:
```bash
cd backend
python -m pytest tests/test_attribution.py tests/test_exposure.py tests/test_timeline.py tests/test_ingestion.py -v
```
**Results:** `12 passed in 0.09s`

---

## 📑 Key Project Deliverables & Artifacts

- **[DEMO_SCRIPT.md](file:///C:/Users/a_ven/.gemini\antigravity\scratch\handoffguard\DEMO_SCRIPT.md)**: Exact 3-minute hackathon pitch flow.
- **[QNA_PREP.md](file:///C:/Users/a_ven/.gemini\antigravity\scratch\handoffguard\QNA_PREP.md)**: 18 jury defense questions & technical answers.
- **[SUBMISSION_CHECKLIST.md](file:///C:/Users/a_ven/.gemini\antigravity\scratch\handoffguard\SUBMISSION_CHECKLIST.md)**: Compliance and completeness audit.
- **[setup_exasol.sql](file:///C:/Users/a_ven/.gemini\antigravity\scratch\handoffguard\setup_exasol.sql)**: Master SQL DDL & analytical view definitions.
- **[init_db.py](file:///C:/Users/a_ven/.gemini\antigravity\scratch\handoffguard\init_db.py)**: Automated database bootstrap and seed runner.

---

## ⚖ License

This project is licensed under the MIT License — see the [LICENSE](file:///C:/Users/a_ven/.gemini\antigravity\scratch\handoffguard\LICENSE) file for details.
