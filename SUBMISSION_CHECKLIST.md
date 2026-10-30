# HandoffGuard — ExaThon India 2026 Submission Checklist

**Submission Status**: Ready for Submission  
**Target Deadline**: Saturday, 31 October 2026, 23:59 IST  

---

## ✅ Core Requirements Verification

### 1. Database & Exasol Integration
- [x] **Strict Invariant**: `logger_readings` table does **NOT** contain a `handoff_id` column.
- [x] Non-equi interval join implemented in Exasol view `v_interval_join_membership`:
  `r.reading_at_utc BETWEEN h.window_start_utc AND h.window_end_utc`
- [x] Analytical view `v_handoff_exposure` computes degree-minutes and duration outside safe bounds.
- [x] Analytical view `v_excursion_attribution` computes exposure share, confidence penalties, and rank.
- [x] SQL migration scripts organized under `db/migrations/`:
  - `001_create_schema.sql`
  - `002_create_tables.sql`
  - `003_create_indexes.sql`
  - `004_create_views.sql`
- [x] Master setup script provided: `setup_exasol.sql`
- [x] Python database seeder provided: `init_db.py` (seeds 5,200+ IoT telemetry readings)
- [x] Docker setup provided: `docker-compose.yml` with Exasol Personal service.
- [x] Health check endpoint verifying database connectivity and schema contract: `GET /api/health/exasol`.

### 2. Backend API & Engine
- [x] Python 3.11+ / FastAPI / Pydantic v2.
- [x] Dual-engine repository architecture (`DATABASE_ENGINE=exasol` or `sqlite`).
- [x] CSV Ingestion service (`POST /api/ingest/logger-file`) auto-detecting 3 formats:
  - Format A (Warehouse ISO 8601 Celsius)
  - Format B (Reefer Truck local timestamps, timezone offset, Fahrenheit-to-Celsius conversion)
  - Format C (Last-Mile Courier split Date/Time columns)
- [x] Attribution Engine calculating degree-minutes, exposure share, and confidence scores.
- [x] Naive baseline comparison implemented (first-threshold-crossing vs. degree-minute exposure).
- [x] Printable Evidence Report API endpoint: `GET /api/excursions/{id}/evidence-report`.
- [x] Prevention prototype API endpoint: `GET /api/prevention/suggestions`.
- [x] Automated test suite: 12 passing pytest unit & integration tests.

### 3. Frontend & Visualizations
- [x] React 18 + TypeScript + Vite + Tailwind CSS.
- [x] Clean, production-grade responsive UI with 5 main views:
  1. Shipments Dashboard (`/`)
  2. Shipment Custody Timeline with Recharts temperature series & excursion shading (`/shipments/:id`)
  3. Custody Membership Interval Join Table (`/shipments/:id` tab)
  4. Excursion Attribution Investigation with Naive Baseline Disproof (`/shipments/:id/excursions/:id`)
  5. Print-Friendly Evidence Report (`/shipments/:id/excursions/:id/report`)
  6. Rule-Based Prevention Prototype (`/prevention`)
- [x] Production build passes with 0 TypeScript/lint errors (`dist/` generated).

### 4. Benchmarking & Ground-Truth Validation
- [x] Ground-Truth Attribution Validation harness (`scripts/validate_attribution.py`):
  - 30 synthetic validation scenarios
  - **100% Top-1 Accuracy**
  - **100% Top-3 Accuracy**
  - Report saved to `reports/attribution_validation.json`
- [x] Interval Join Performance Benchmark harness (`scripts/benchmark_interval_join.py`):
  - 100,000 readings benchmark
  - Cross-engine evaluation (SQLite vs DuckDB vs Exasol)
  - Reports saved to `reports/interval_join_benchmark.json` and `reports/interval_join_benchmark.md`

### 5. Documentation & Compliance
- [x] Comprehensive `README.md` with system overview, architecture diagram, Exasol schema contract, and step-by-step setup instructions.
- [x] 3-Minute Live Pitch & Demo Script (`DEMO_SCRIPT.md`).
- [x] 18-Question Jury Defense Guide (`QNA_PREP.md`).
- [x] Open-source MIT License (`LICENSE`).
- [x] Mandatory prototype disclaimers visible on all UI screens and API responses:
  *"Exposure is estimated from ambient/logger temperature and time. It is not a direct measurement of product-core temperature; thermal mass, packaging, and product-specific heat transfer are not modelled in this prototype."*
- [x] Clean `.gitignore` protecting build artifacts and sensitive environment files.
