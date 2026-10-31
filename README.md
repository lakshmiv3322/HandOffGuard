# HandoffGuard — Cold-Chain Custody Attribution Prototype

**High-Throughput Pharmaceutical Cold-Chain Analytics & Custody Attribution**  
*Prototype Decision Support Engine Powered by Exasol In-Memory Columnar Database*

---

## 🔬 Overview & The Problem

Biologics, vaccines, and cell therapies require strict thermal maintenance (e.g., 2°C to 8°C or deep frozen -25°C to -15°C). During multi-modal distribution, shipments pass through an unbroken chain of custody:
1. Central Cold Storage Warehouse
2. Line-Haul Refrigerated Truck
3. Air Cargo / Staging Cross-Dock Facility
4. Regional Hub / Depot
5. Last-Mile Delivery Courier

When a shipment arrives with an irreversible thermal excursion, parties dispute responsibility: the airline blames ground handling; ground handling blames the line-haul carrier.

**The Fundamental Data Challenge:**
> **IoT temperature loggers do not know who owns the package.**  
> Raw telemetry records contain only logger timestamps and temperature observations. **There is NO handoff ID or custody tag in sensor readings.**

**HandoffGuard** solves this by leveraging **Exasol Personal's in-memory columnar engine** to execute high-throughput, non-equi interval joins across dense sensor observations and custody transfer logs, calculating cumulative thermal exposure in **degree-minutes** to attribute thermal breaches with defensible, transparent evidence.

> [!IMPORTANT]
> **Mandatory Quality Investigation Disclaimer:**  
> *Thermal exposure is estimated from ambient/logger observations and stated engineering assumptions (e.g., 600s maximum supported segment duration). Product thermal mass, packaging insulation, and core kinetics are not modelled in this prototype. Results serve strictly as decision support for quality team investigations, NOT legal determinations of liability.*

---

## 🏛 Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 HandoffGuard                                    │
├─────────────────────────┬───────────────────────────────────────────────────────┤
│    Frontend (React 18)  │               Backend (FastAPI / Python 3.11+)        │
│                         │                                                       │
│  - Shipments Monitor    │   API Layer (/api/shipments, /api/excursions, ...)    │
│  - Custody Timeline     │                       │                               │
│  - Telemetry Drilldown  │   Service Layer (Attribution, Ingestion, Exposure)   │
│  - Evidence Report      │                       │                               │
│  - Prevention Advisory  │   Repository Adapter Layer                            │
│  - Exasol Benchmarks    │        ┌──────────────┴──────────────┐                │
│                         │        ▼                             ▼                │
│                         │   Dev Adapter                   Exasol Adapter        │
│                         │   (SQLite / Local)              (pyexasol Client)     │
└─────────────────────────┴────────┼─────────────────────────────┼────────────────┘
                                   │                             │
                                   ▼                             ▼
                          Local SQLite DB               Exasol Personal DB (Port 8563)
                                                        - V_READING_HANDOFF_MEMBERSHIP
                                                        - V_HANDOFF_THERMAL_EXPOSURE
                                                        - V_EXCURSION_ATTRIBUTION
```

### Core Analytical Methodology (Migration 005)

1. **Clock Skew Correction & Half-Open Windows**:
   $$\text{corrected\_time} = \text{reading\_at\_utc} - \text{COALESCE}(\text{clock\_skew\_seconds}, 0)$$
   Matched using half-open intervals:
   $$\text{corrected\_time} \ge \text{actual\_start\_at} \quad\text{AND}\quad \text{corrected\_time} < \text{actual\_end\_at}$$
2. **Deterministic Sensor Segments**:
   Segments are formed via `LEAD(corrected_at_utc) OVER (PARTITION BY logger_id ORDER BY corrected_at_utc, reading_id)`.
   A configurable maximum gap threshold (default 600s / 10 min) is enforced. Unsupported gaps contribute zero duration and cannot carry temperatures forward.
3. **Ambiguity Exclusion**:
   Overlapping custody intervals (where multiple handoffs claim the same time window) are detected across full segment intersections and conservatively excluded from single-party attributable exposure, flagged as `AMBIGUOUS_CUSTODY_EXCLUSION`.
4. **Actual vs Planned Custody Windows**:
   Actual start and end timestamps are required for custody attribution. Handoffs with planned-only timestamps are marked `PLANNED_ONLY` and excluded by default.
5. **Single-Logger MVP Rule**:
   Multi-logger assignments emit explicit `INCONCLUSIVE_MULTI_LOGGER` warnings to avoid double-counting exposure.
6. **Excursion-Restricted Integration**:
   Attribution integrates thermal stress strictly over the intersection of the handoff custody window and the excursion interval:
   $$\text{Degree-Minutes} = \int_{t \in \text{Handoff} \cap \text{Excursion}} \max(0, T(t) - T_{\text{product\_max}}) \, dt$$

---

## 🎯 Three Demonstration Scenarios

HandoffGuard comes pre-loaded with three deterministic scenarios demonstrating distinct analytical outcomes:

| Scenario | Shipment ID | Excursion ID | Characteristics | Outcome & Status |
|---|---|---|---|---|
| **1. Clear Single-Handoff Exposure** | `SHP-SYNTH-DENSE-01` | `EXC-SYNTH-01` | 301 readings at 1-min intervals. 45-min breach during Handoff 2 (Dock Transfer). | **Rank #1**: Handoff 2 holds 281.2 °C·min (100% share). Status: *Prototype Ranking*. |
| **2. Insufficient Data** | `SHP-2026-0881` | `EXC-1002` | 9 sparse readings with multi-hour gaps (>600s threshold). | **Inconclusive**: Status: `INCONCLUSIVE_INSUFFICIENT_DATA`. Exposure displayed as *Unavailable* (observed peak 18.2°C preserved). |
| **3. Conflicting / Ambiguous Custody** | `SHP-SYNTH-AMBIG-01` | `EXC-SYNTH-02` | Overlapping actual custody windows (10:00 to 10:15) during thermal breach. | **Inconclusive**: 12.0 ambiguous minutes excluded from attributable exposure. Status: `AMBIGUOUS_CUSTODY_EXCLUSION`. |

Seed or re-verify these scenarios at any time:
```bash
python scripts/seed_demo_scenarios.py
```

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker (for Exasol Personal)

### 1. Start Exasol Personal
```bash
docker run --name exasol_test -p 8563:8563 -d exasol/docker-db:latest
```

### 2. Configure Environment
Copy `.env.example` to `.env` in the repository root and `backend/`:
```bash
cp .env.example backend/.env
```
*(Default settings connect to Exasol on localhost:8563 with no plaintext secret credentials).*

### 3. Initialize Database & Seed Scenarios
```bash
# Seed all 3 demo scenarios into Exasol live schema
backend\venv\Scripts\python scripts/seed_demo_scenarios.py
```

### 4. Start Backend Server
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### 5. Start Frontend UI
```bash
cd frontend
npm install
npm run dev
```
- Open application at: http://localhost:5173

---

## 🧪 Verification & Evaluation Commands

### 1. Exasol Integration Tests (14 Scenarios)
Executes production migration SQL retargeted against an isolated schema `HANDOFFGUARD_TEST`:
```bash
backend\venv\Scripts\python backend/tests/run_exasol_integration_tests.py
```
*Result: 14/14 PASS.*

### 2. Synthetic Evaluation Suite (`reports/attribution_evaluation.md`)
Runs reproducible evaluation against 5 held-out synthetic cases (single-handoff, spanning, tied, clock offset, missing data):
```bash
backend\venv\Scripts\python backend/evaluation/run_evaluation.py
```
*Result: Primary algorithm 5/5 correct (100%), Naive baseline 3/5 correct (60%).*

### 3. Practical Benchmark: Exasol vs pandas (`reports/benchmark_results.md`)
Compares Exasol view execution against an equivalent pandas interval join workload with mathematical correctness verification:
```bash
backend\venv\Scripts\python scripts/benchmark_exasol_vs_pandas.py
```
*Result: Mathematical agreement within 0.0000 °C·min. Median Exasol loopback: 112.6 ms; median pandas in-process: 11.6 ms.*

### 4. End-to-End API Smoke Tests
```bash
backend\venv\Scripts\python backend/tests/test_api_endpoints.py
```
*Result: All endpoints PASS.*

---

## 🖨 Printable Evidence Reports

HandoffGuard generates audit-grade, print-friendly evidence reports for quality and regulatory review:
- Navigate to any excursion attribution view (e.g. `SHP-SYNTH-DENSE-01` / `EXC-SYNTH-01`).
- Click **"View Official Evidence Audit Report"**.
- Click **"Print Report (PDF)"** or press `Ctrl+P`.
- All navigation and interactive controls automatically hide via `@media print` CSS rules, producing clean audit documentation.

---

## ⚖ License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
