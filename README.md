# HandoffGuard — Cold-Chain Custody Attribution Prototype

**Pharmaceutical Cold-Chain Analytics & Custody Attribution**  
*Prototype Decision Support Engine Powered by Exasol In-Memory Columnar Database*

---

## 🔬 Overview & The Problem

Biologics, vaccines, and cell therapies require strict thermal maintenance (e.g., 2°C to 8°C or deep frozen -25°C to -15°C). During multi-modal distribution, shipments pass through an unbroken chain of custody:
1. Central Cold Storage Warehouse
2. Line-Haul Refrigerated Truck
3. Air Cargo / Staging Cross-Dock Facility
4. Regional Hub / Depot
5. Last-Mile Delivery Courier

When a shipment arrives with a detected thermal excursion, parties dispute responsibility: the airline blames ground handling; ground handling blames the line-haul carrier.

**The Fundamental Data Challenge:**
> **IoT temperature loggers do not know who owns the package.**  
> Raw telemetry records contain only logger timestamps and temperature observations. **There is NO handoff ID or custody tag in sensor readings.**

**HandoffGuard** solves this by leveraging **Exasol Personal's in-memory columnar engine** to execute non-equi interval joins across dense sensor observations and custody transfer logs, calculating cumulative thermal exposure in **degree-minutes** to attribute thermal breaches with defensible, transparent evidence.

> [!IMPORTANT]
> **Mandatory Quality Investigation Disclaimer:**  
> *Thermal exposure is estimated from ambient/logger observations and stated engineering assumptions (e.g., 600s maximum supported segment duration). Product thermal mass, packaging insulation, and core kinetics are not modelled in this prototype. Results serve strictly as decision support for quality team investigations, NOT legal determinations of liability.*

---

## 🏛 Architecture & Analytical Methodology (Migration 005)

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
│  - Benchmark Insights   │        ┌──────────────┴──────────────┐                │
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

### Core Analytical Invariants

1. **Clock Skew Correction & Half-Open Windows**:
   $$\text{corrected\_time} = \text{reading\_at\_utc} - \text{COALESCE}(\text{clock\_skew\_seconds}, 0)$$
   Matched using half-open intervals to prevent boundary double-counting:
   $$\text{corrected\_time} \ge \text{actual\_start\_at} \quad\text{AND}\quad \text{corrected\_time} < \text{actual\_end\_at}$$
2. **Deterministic Sensor Segments**:
   Segments are formed via `LEAD(corrected_at_utc) OVER (PARTITION BY logger_id ORDER BY corrected_at_utc, reading_id)`.
   A configurable maximum gap threshold (default 600s / 10 min) is enforced as a prototype engineering assumption. Unsupported gaps contribute zero duration and cannot carry temperatures forward.
3. **Ambiguity Exclusion**:
   Overlapping custody intervals (where multiple handoffs claim the same time window) are detected across full segment intersections and conservatively excluded from single-party attributable exposure, flagged as `AMBIGUOUS_CUSTODY_EXCLUSION`.
4. **Actual vs Planned Custody Windows**:
   Actual start and end timestamps are required for custody attribution. Handoffs with planned-only timestamps are marked `PLANNED_ONLY` and excluded by default.
5. **Single-Logger MVP Rule**:
   Multi-logger assignments emit explicit `INCONCLUSIVE_MULTI_LOGGER` warnings to avoid double-counting exposure.
6. **Excursion-Restricted Integration vs Whole-Handoff Exposure**:
   - **Excursion-Restricted Scope (`V_EXCURSION_ATTRIBUTION`)**: Integrates thermal stress strictly over the intersection of the handoff custody window and the excursion interval:
     $$\text{Degree-Minutes} = \int_{t \in \text{Handoff} \cap \text{Excursion}} \max(0, T(t) - T_{\text{product\_max}}) \, dt$$
   - **Whole-Handoff Scope (`V_HANDOFF_THERMAL_EXPOSURE`)**: Integrates thermal stress across the entire handoff duration, including post-excursion cooldown periods before temperatures re-enter the safe range.
7. **Removed Uncalibrated Confidence Scores**:
   Arbitrary numerical confidence values (`0.85`, `0.10`) have been removed and replaced with `null` / descriptive labels (`"Prototype Ranking"`, `"Inconclusive"`) pending a scientifically validated calibration model.

---

## 🎯 Three Demonstration Scenarios

HandoffGuard includes three deterministic live scenarios demonstrating distinct analytical outcomes:

| Scenario | Shipment ID | Excursion ID | Telemetry Profile | Coverage & Exposure Accounting | Attribution Status |
|---|---|---|---|---|---|
| **1. Clear Single-Handoff Exposure** | `SHP-SYNTH-DENSE-01` | `EXC-SYNTH-01` | 301 readings at 1-min intervals. 45-min breach during H2 (Dock Transfer). | **Excursion-Restricted Exposure**: 281.20 °C·min (45.0 min).<br>**Whole-Handoff Exposure**: 289.12 °C·min (includes 7.92 °C·min cooldown).<br>**Coverage**: 45.0/45.0 min (100.0%). | **Rank #1**: Handoff 2 holds 100% exposure share. Status: *Prototype Ranking*. |
| **2. Insufficient Evidence** | `SHP-2026-0881` | `EXC-1002` | 9 sparse readings with consecutive gaps ranging from 30 to 75 min (1,800s to 4,500s; all > 600s threshold). | **Excursion Denominator**: 90.0 min (12:15–13:45 UTC).<br>**Supported Obs**: 0.0 min.<br>**Unsupported Gap**: 90.0 min (100% gap).<br>**Shipment Denominator**: 540.0 min (H1+H2+H3).<br>**Exposure**: Displayed as *Unavailable* (observed peak 18.2°C preserved). | **Inconclusive**: Status: `INCONCLUSIVE_INSUFFICIENT_DATA`. No winner crowned. |
| **3. Conflicting / Ambiguous Custody** | `SHP-SYNTH-AMBIG-01` | `EXC-SYNTH-02` | 361 readings. Overlapping actual custody windows between H1 and H2 (10:00 to 10:15) during breach. | **Excursion Denominator**: 12.0 min (10:02–10:14 UTC).<br>**Ambiguous Overlap**: 12.0 min.<br>**Attributable Exposure**: 0.0 °C·min (overlap excluded). | **Inconclusive**: Status: `AMBIGUOUS_CUSTODY_EXCLUSION`. Overlapping segments excluded. |

Seed or re-verify all 3 demo scenarios:
```bash
python scripts/seed_demo_scenarios.py
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Git**
- **Python 3.11+**
- **Node.js 18+** & npm
- **Docker** (to run Exasol Personal edition)

---

### Option 1: Docker Compose (Automated Stack)

If Docker and Docker Compose are installed:
```bash
git clone https://github.com/lakshmiv3322/HandOffGuard.git
cd HandOffGuard
docker compose up -d
```
*(Wait ~30–45 seconds for Exasol's internal database initialization, then seed the demo data):*
```bash
python scripts/seed_demo_scenarios.py
```
- Open application at: **http://localhost:5173**
- Backend API docs: **http://localhost:8000/docs**

---

### Option 2: Step-by-Step Local Setup (macOS / Linux / Windows)

#### 1. Clone Repository
```bash
git clone https://github.com/lakshmiv3322/HandOffGuard.git
cd HandOffGuard
```

#### 2. Start Exasol Personal via Docker
```bash
# Standard Docker run (on Apple Silicon M1/M2/M3 Macs, add --platform linux/amd64):
docker run --name exasol_test -p 8563:8563 -d exasol/docker-db:latest
```
*(Wait ~30–45 seconds for Exasol's internal database instance to initialize).*

#### 3. Set Up Python Virtual Environment
```bash
python -m venv venv

# macOS / Linux:
source venv/bin/activate

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt):
venv\Scripts\activate.bat

# Install dependencies:
pip install -r requirements.txt
```

#### 4. Configure Environment
```bash
# macOS / Linux:
cp .env.example backend/.env

# Windows (PowerShell):
Copy-Item .env.example backend\.env
```
*(The backend reads `backend/.env`. Default settings connect to Exasol on `localhost:8563` with no secret credentials. The root `.env` is not loaded by the application.)*

#### 5. Initialize Schema and Seed Demo Scenarios into Exasol
```bash
# 5a. Create schema + tables + analytical views in a fresh Exasol instance:
python scripts/init_exasol_db.py

# 5b. Seed all 3 demonstration scenarios (calls init automatically if schema is missing):
python scripts/seed_demo_scenarios.py
```
*Seeds all 3 demo scenarios (dense breach, sparse inconclusive, and ambiguous custody).*
*`seed_demo_scenarios.py` auto-initializes the schema if the analytical views are missing; running `init_exasol_db.py` separately first is still recommended for clarity.*

#### 6. Start Backend Server
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

#### 7. Start Frontend UI (In a new terminal)
```bash
cd frontend
npm install
npm run dev
```
- Open application at: **http://localhost:5173**

---

## 🧪 Verification & Evaluation Commands

Run these from the repository root with your virtual environment activated:

### 1. Exasol Integration Tests (14 Scenarios)
Executes production migration SQL ([`db/migrations/005_repair_analytics_views.sql`](db/migrations/005_repair_analytics_views.sql)) retargeted against an isolated schema `HANDOFFGUARD_TEST`:
```bash
python backend/tests/run_exasol_integration_tests.py
```
**Result**: **14 / 14 PASS**. Verifies half-open boundaries, clock skew subtraction, 600s gap limits, product thresholds, overlapping custody exclusions, planned-only exclusions, no-reading abstention, multi-logger warnings, and non-extending tail gaps.

### 2. Synthetic Attribution Evaluation ([`reports/attribution_evaluation.md`](reports/attribution_evaluation.md))
Evaluates the primary target (*"handoff with largest supported out-of-range exposure within an excursion window"*) against the naive baseline (*"first observed out-of-range reading"*) across 5 held-out synthetic test fixtures:
```bash
python backend/evaluation/run_evaluation.py
```
*Note: Evaluates 5 synthetic unit fixtures to verify algorithmic guardrails; not a real-world field validation claim.*

| Evaluation Dimension | Primary Algorithm | Naive Baseline | Description / Scope |
|---|---|---|---|
| **Unique-Winner Accuracy** | **100.0% (3/3)** | 33.3% (1/3) | Solvable cases with a single dominant carrier (EVAL-01, 02, 04) |
| **Tie Handling** | **100.0% (1/1)** | 0.0% (0/1) | Refuses to crown an arbitrary winner when exposure is equal (EVAL-03) |
| **Insufficient-Data Abstention** | **100.0% (1/1)** | 0.0% (0/1) | Emits `INCONCLUSIVE_INSUFFICIENT_DATA` when gaps exceed 600s (EVAL-05) |
| **Decision Coverage** | **60.0% (3/5)** | 100.0% (5/5) | Unique selections / all cases (primary abstains on ties and gaps; naive blindly crowns a winner) |
| **Overall Fixture Decision Outcomes** | **100.0% (5/5)** | 20.0% (1/5) | Performance across all 5 synthetic edge-case fixtures |

- **Why Naive Baseline Failed 4 of 5 Cases**:
  - `EVAL-02` (Spanning): Naive picked FH1 due to boundary match at 10:00, ignoring that FH2 held 75% of cumulative exposure.
  - `EVAL-03` (Tie): Naive arbitrarily crowned GH1; failed tie detection.
  - `EVAL-04` (Clock Offset): Naive used raw uncorrected timestamp (10:01) to blame KH2; primary corrected -300s skew and properly attributed to KH1 (09:56 UTC).
  - `EVAL-05` (Missing Data): Naive blindly output MH1 despite a 90-minute unobserved gap; primary correctly abstained.

### 3. Practical Benchmark: Small-Fixture Comparison ([`reports/benchmark_results.md`](reports/benchmark_results.md))
Compares Exasol query execution against an equivalent in-process pandas interval join on `SHP-SYNTH-DENSE-01` (301 readings, 3 handoffs):
```bash
python scripts/benchmark_exasol_vs_pandas.py
```
- **Mathematical Correctness**: **PASS (0.0000 diff per handoff)**.
- **Measured Timings (10 Repetitions)**:
  - **In-process pandas**: Median **20.9 ms**.
  - **Networked Exasol**: Median **108.7 ms**.
  - **Finding**: On this small 301-reading fixture, in-process pandas was faster than Exasol due to loopback network socket IPC and query dispatch overhead dominating small data transfers.
- **Large-Scale Testing Status**: **NOT COMPLETED**. A benchmark across >= 10,000 shipments was not run due to single-container developer laptop memory and execution limits.

### 4. End-to-End API Smoke Tests
```bash
python backend/tests/test_api_endpoints.py
```
**Result**: **ALL PASS**. Verifies health, membership counts, exposure status, attribution ranks, null-safety, and telemetry drilldowns across sparse and dense scenarios.

### 5. Automated Security & Credential Audit
```bash
python scripts/scan_secrets.py
```
**Result**: **ALL PASS**. Scans tracked files, frontend code, and Git history for leaked credentials or secrets.

---

## 📖 Reviewing Without Running Locally

If judges or reviewers prefer to review audit and verification evidence directly in the repository without running Docker:

1. **Release Audit Matrix**: [`RELEASE_AUDIT.md`](RELEASE_AUDIT.md) — 36-point verified release audit.
2. **Attribution Evaluation Report**: [`reports/attribution_evaluation.md`](reports/attribution_evaluation.md) — Case-by-case evaluation against naive baseline with scoring breakdowns.
3. **Performance Benchmark Report**: [`reports/benchmark_results.md`](reports/benchmark_results.md) — Exasol vs pandas small-fixture timing, correctness checks, and scope reconciliation.
4. **Offline / Development Mode**: HandoffGuard can run without Docker using SQLite by setting `DATABASE_ENGINE=sqlite` in `backend/.env`. *This development-only fallback does not execute Exasol analytical views; results will differ from the production Exasol path.*

---

## 🖨 Printable Evidence Reports

HandoffGuard generates print-friendly evidence reports for quality and regulatory review:
- Navigate to any excursion attribution view (e.g. `SHP-SYNTH-DENSE-01` / `EXC-SYNTH-01`).
- Click **"View Evidence Report"**.
- Click **"Print Report (PDF)"** or press `Ctrl+P`.
- All navigation and interactive controls automatically hide via `@media print` CSS rules, producing clean audit documentation.

---

## ⚖ License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
