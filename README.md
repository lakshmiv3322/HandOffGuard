# HandoffGuard — Cold-Chain Custody Attribution Prototype

**ExaThon India 2026 Hackathon Submission**

---

## Overview

Cold-chain pharmaceutical shipments pass through multiple custodians — manufacturers, freight forwarders, airlines, last-mile couriers — before reaching their destination. When a temperature excursion is detected at delivery, determining *which* custodian is most likely responsible is typically a manual, disputed, and time-consuming process.

**HandoffGuard** is a prototype system that automates custody attribution for cold-chain temperature excursions. By correlating ambient temperature logger readings with documented handoff windows, it produces an *estimated* attribution score for each custodian segment, along with a printable evidence report.

> **Disclaimer:** Exposure is estimated from ambient/logger temperature and time. It is not a direct measurement of product-core temperature; thermal mass, packaging, and product-specific heat transfer are not modelled in this prototype.

All attribution outputs use language such as "most likely", "estimated exposure", and "prototype suggestion" to reflect the probabilistic and approximate nature of the analysis.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    HandoffGuard                         │
├──────────────┬──────────────────────────────────────────┤
│  Frontend    │  Backend                                 │
│  (React/TS)  │  (FastAPI/Python)                        │
│              │                                          │
│  5 Screens:  │  API Layer (FastAPI Routers)             │
│  - Shipments │         │                                │
│  - Timeline  │  Service Layer (Domain Logic)            │
│  - Attribution│        │                               │
│  - Report    │  Repository Layer (Adapter Pattern)      │
│  - Prevention│         │                                │
│              │  ┌──────┴────────┐                       │
│              │  │  Dev DB       │  Exasol DB            │
│              │  │  (SQLite)     │  (Future)             │
│              │  └───────────────┘                       │
└──────────────┴──────────────────────────────────────────┘
```

The backend follows a clean layered architecture:

- **API Layer** — FastAPI routers that handle HTTP requests and serialize responses.
- **Service Layer** — Domain logic for attribution scoring, exposure calculation, and prevention suggestions.
- **Repository Layer** — Abstract base interfaces with concrete adapter implementations. The `DATABASE_ENGINE` environment variable selects the active adapter at startup (`sqlite` for development, `exasol` for production).

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (optional, for Docker Compose workflow)

---

### Local Development (Without Docker)

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env if needed
python scripts/seed_data.py  # Load synthetic seed data
uvicorn app.main:app --reload
```

- Backend runs at: http://localhost:8000
- Interactive API docs (Swagger UI): http://localhost:8000/docs
- Alternative API docs (ReDoc): http://localhost:8000/redoc

#### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

- Frontend runs at: http://localhost:5173

---

### Docker Compose

```bash
docker-compose up --build
```

This will start both the backend (port 8000) and the frontend (port 5173). The frontend container depends on the backend being healthy.

---

## Environment Variables

### Backend (`.env`)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_ENGINE` | `sqlite` | Database adapter to use: `sqlite`, `postgres`, `exasol` |
| `DEV_DATABASE_URL` | `sqlite:///./handoffguard_dev.db` | SQLAlchemy connection URL for the development SQLite database |
| `EXASOL_HOST` | — | Exasol server hostname (production only) |
| `EXASOL_PORT` | `8563` | Exasol WebSocket port |
| `EXASOL_DATABASE` | — | Exasol database/catalog name |
| `EXASOL_USER` | — | Exasol login username |
| `EXASOL_PASSWORD` | — | Exasol login password |
| `EXASOL_SCHEMA` | — | Exasol schema name (e.g. `HANDOFFGUARD`) |
| `SKEW_TOLERANCE_SECONDS` | `120` | Time window tolerance (seconds) applied when matching temperature readings to handoff windows |

### Frontend (`.env`)

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Base URL for all backend API calls |

---

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Key Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check and database connectivity status |
| `GET` | `/api/shipments` | List shipments (paginated, filterable) |
| `GET` | `/api/shipments/{id}` | Shipment detail including product and status |
| `GET` | `/api/shipments/{id}/custody-timeline` | Full custody timeline with temperature readings and handoff windows |
| `GET` | `/api/shipments/{id}/handoffs` | List of handoff segments for a shipment |
| `GET` | `/api/excursions/{id}/attribution` | Attribution result for a given excursion event |
| `POST` | `/api/excursions/{id}/recompute` | Force recomputation of attribution scores |
| `GET` | `/api/excursions/{id}/evidence-report` | Structured data for the printable evidence report |
| `GET` | `/api/prevention/upcoming` | Prevention suggestions for an upcoming/in-transit shipment |

---

## How to Connect Exasol

When you have an Exasol instance available:

1. **Set environment variables:**

   ```bash
   DATABASE_ENGINE=exasol
   EXASOL_HOST=your-exasol-host
   EXASOL_PORT=8563
   EXASOL_DATABASE=your-db
   EXASOL_USER=your-user
   EXASOL_PASSWORD=your-password
   EXASOL_SCHEMA=HANDOFFGUARD
   ```

2. **Install the Exasol Python driver:**

   ```bash
   pip install pyexasol
   ```

3. **Implement the Exasol repository classes** in:

   ```
   backend/app/infrastructure/repositories/exasol/
   ```

   Each repository class must implement the abstract interface defined in:

   ```
   backend/app/infrastructure/repositories/base.py
   ```

4. The file `backend/app/infrastructure/db/exasol_db.py` contains the connection setup pattern and a placeholder `get_connection()` factory.

5. **Load your data** using the Exasol DDL schema provided in:

   ```
   backend/app/infrastructure/repositories/exasol/README.md
   ```

   Adapt the INSERT statements in `backend/scripts/seed_data.py` for Exasol SQL syntax if needed (e.g., `MERGE INTO` instead of `INSERT OR IGNORE`).

---

## Domain Logic

### Temperature-to-Handoff Assignment

Temperature readings are assigned to handoff custody windows using **interval overlap**, not by a stored foreign key. This allows retrospective re-attribution if handoff windows are corrected.

**Clock-skew correction:**
```
corrected_time = reading.recorded_at_utc + logger.clock_skew_seconds
```

A reading belongs to a handoff window if:
```
corrected_time ∈ [window_start_utc − skew_tolerance, window_end_utc + skew_tolerance]
```

The `SKEW_TOLERANCE_SECONDS` environment variable (default: 120 s) controls the boundary tolerance.

### Exposure Calculation

For each reading assigned to a handoff, out-of-range exposure is calculated as:

```
degree_minutes = max(0, distance_from_safe_limit_°C) × minutes_since_previous_reading
```

The cumulative `degree_minutes` for a handoff segment represents the estimated thermal exposure during that custody period.

### Attribution Scoring

Attribution uses a **transparent, rule-based scoring system** — no black-box ML models. Each handoff segment receives a confidence score derived from five weighted factors:

| # | Factor | Description |
|---|---|---|
| 1 | Normalized exposure share | Fraction of total excursion degree-minutes occurring during this segment |
| 2 | Data coverage ratio | Fraction of the segment's time window covered by logger readings |
| 3 | Data quality fraction | Share of readings with a passing quality flag |
| 4 | Clock skew uncertainty penalty | Penalty applied when logger clock skew is large relative to window duration |
| 5 | Overlap ambiguity penalty | Penalty when the reading falls within an overlapping handoff boundary |

The resulting score is labelled:

- **High confidence** — segment is the most likely responsible custodian
- **Medium confidence** — segment is a probable contributor
- **Low confidence** — weak signal; data gaps or ambiguity limit attribution

---

## Known Limitations

1. **Temperature proxy only** — Exposure is derived from ambient logger temperature, not product core temperature. Thermal mass and packaging insulation effects are not modelled. Actual product temperature may lag or lead the logger readings.

2. **Prototype attribution** — Attribution scores are probabilistic estimates intended for investigative guidance. They must not be used for legal proceedings, insurance claims, or regulatory compliance without independent validation.

3. **Clock skew simplification** — Logger clock skew is modelled as a constant offset. Real-world clock drift (which varies over time and temperature) is not modelled.

4. **Overlapping windows** — When handoff custody windows overlap, exposure is split proportionally between the affected segments, which is an approximation of the true allocation.

5. **Prevention suggestions** — Suggestions are generated by rules derived from synthetic seed data. They have not been validated against real-world cold-chain operational data.

6. **No real-time data** — This prototype ingests batch data. Live IoT stream ingestion, alerting, and continuous monitoring are outside the current scope.

7. **Exasol not connected** — Development and demonstration use SQLite. Exasol integration requires implementing the repository adapter classes as documented in `backend/app/infrastructure/repositories/exasol/README.md`.

---

## Testing

```bash
cd backend
pytest tests/ -v
```

Unit tests cover the attribution service, exposure calculator, and reading-to-handoff assignment logic using synthetic in-memory fixtures.

---

## Prototype Disclaimer

HandoffGuard is a **hackathon prototype** submitted for ExaThon India 2026. All attribution results, prevention suggestions, and risk scores are clearly marked as estimates. This system **must not** be used for regulatory compliance, legal proceedings, quality investigations, or operational decisions without:

- Proper validation against real cold-chain shipment data
- Review by qualified cold-chain and pharmaceutical quality professionals
- Alignment with applicable regulatory frameworks (e.g., GDP, WHO cold-chain guidelines)

---

*Built for ExaThon India 2026 — Exasol Hackathon*
