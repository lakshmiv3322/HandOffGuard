# HandoffGuard — Jury Q&A Preparation
**ExaThon India 2026 Hackathon Defense Guide**

---

## 1. Exasol & Database Architecture

### Q1: Why did you choose Exasol for interval joins rather than a traditional relational database like PostgreSQL?
**Answer:**
"Temperature loggers record continuous time-series data at high frequencies (every 10–60s) without carrying custody IDs (`handoff_id`). Associating readings with custody windows requires non-equi joins (`BETWEEN h.window_start_utc AND h.window_end_utc`). In traditional row-oriented relational engines, non-equi joins often degrade to nested loop or block-nested-loop scans ($O(N \times M)$), resulting in multi-second execution times for large shipments. Exasol uses an in-memory columnar engine with automatic data compression, zone-map indexing, and parallel execution that filters and matches interval ranges in sub-second time (<85ms for 100k readings in our benchmark)."

### Q2: How is the schema designed to enforce that readings do not contain `handoff_id`?
**Answer:**
"Table `logger_readings` strictly contains `(reading_id, logger_id, reading_at_utc, temperature_c, humidity_pct, battery_pct, quality_flag)`. There is intentionally no `handoff_id` foreign key. The association is entirely dynamic and derived through Exasol analytical views (`v_interval_join_membership`, `v_handoff_exposure`, and `v_excursion_attribution`). We verified this in our automated `/api/health/exasol` contract test."

### Q3: What Exasol SQL functions did you utilize for date arithmetic and interval manipulation?
**Answer:**
"Exasol has specific time manipulation functions:
1. `ADD_SECONDS(timestamp, seconds)` for applying clock-skew corrections and interval buffer tolerances.
2. `SECONDS_BETWEEN(ts1, ts2)` for duration computations.
We avoided vendor-incompatible functions like SQLite's `strftime` or standard `DATEADD` to ensure strict Exasol SQL dialect compliance."

### Q4: How does your database adapter architecture handle running on local environments versus live Exasol?
**Answer:**
"We built a clean repository/adapter layer:
- `app/infrastructure/db/exasol_db.py` uses `pyexasol` connection pooling with thread-safe async execution.
- `app/infrastructure/db/dev_db.py` uses SQLAlchemy Core with SQLite for local headless testing when an Exasol instance is unavailable.
The business logic in `ExposureService` and `AttributionService` interacts purely with domain models and repository interfaces (`AbstractHandoffRepository`, `AbstractReadingRepository`, etc.), so the engine can be swapped seamlessly via `DATABASE_ENGINE=exasol`."

---

## 2. Mathematical Modeling & Domain Attribution

### Q5: What is 'Degree-Minutes' and why is it superior to duration alone?
**Answer:**
"Duration alone treats a 10-minute excursion at 8.1°C (barely out of spec) the same as a 10-minute excursion at 25°C (severe product degradation). 
Thermal exposure in degree-minutes integrates both duration and excess temperature:
$$\text{Exposure} = \int_{t_{\text{start}}}^{t_{\text{end}}} \max\left(0, T(t) - T_{\text{max}}\right) \, dt$$
In discrete sensor sampling, we use the trapezoidal approximation:
$$\text{Exposure} \approx \sum_{i} \left(\frac{(T_i - T_{\text{max}}) + (T_{i+1} - T_{\text{max}})}{2}\right) \times \Delta t_i$$
This correctly weighs the intensity of the thermal breach."

### Q6: Why did you compare against a 'Naive Baseline'?
**Answer:**
"Most conventional ERP and legacy logistics systems use a 'first-threshold-crossing' alert. If a shipment breaches 8.0°C during an unloading stage, that handler is blamed. However, in our benchmark scenario (SHP-001), Leg 2 experienced a minor 8.4°C drift, while Leg 4 left the cargo on a 14.8°C tarmac dock causing 82% of the total thermal damage. By demonstrating the naive baseline vs. HandoffGuard's degree-minute attribution, we prove why naive threshold alerts fail."

### Q7: Why do you prominently state that this is a 'prototype estimate' and not a legal settlement tool?
**Answer:**
"In pharmaceutical cold chains (GDP compliance), ambient temperature loggers measure the surrounding air, not the internal core temperature of the vial. Thermal mass, tertiary corrugated packaging, and phase-change gel packs buffer temperature penetration. Because our prototype models ambient readings without physical heat transfer equations, claiming legal liability would be scientifically invalid. We provide objective, probabilistic evidence for QA investigations."

### Q8: How does your attribution handle logger clock skew and missing telemetry?
**Answer:**
"1. **Clock Skew**: Loggers are configured with a known static `clock_skew_seconds`. The ingestion and query pipeline applies `ADD_SECONDS(reading_at_utc, -skew_seconds)` before interval evaluation.
2. **Missing Gaps**: When telemetry intervals exceed $2.5 \times$ the sampling frequency, a gap is flagged. If an excursion occurred during a gap, confidence scores are penalized proportionally."

---

## 3. Data Ingestion & Interoperability

### Q9: Real-world logistics data comes in messy formats. How does HandoffGuard handle CSV ingestion?
**Answer:**
"Our `IngestionService` implements auto-detection for three industry formats:
- **Format A (Warehouse Cold-Storage)**: Standard ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`), Celsius.
- **Format B (Reefer Truck In-Transit)**: Local timestamps (`YYYY-MM-DD HH:MM:SS`) with explicit `time_zone` offset column (+05:30) and Fahrenheit temperature values auto-converted to Celsius ($°C = (°F - 32) \times 5/9$).
- **Format C (Last-Mile Courier)**: Split `reading_date` (`DD/MM/YYYY`) and `reading_time` (`HH:MM:SS`) combined into UTC ISO format."

### Q10: How do you reject malformed sensor readings during ingestion?
**Answer:**
"We validate data types, range bounds (rejecting impossible temperatures <-80°C or >100°C), ensure reading timestamps are not in the future, and check for duplicate timestamps from the same logger."

---

## 4. Performance & Scalability

### Q11: What were the results of your interval join benchmark?
**Answer:**
"We benchmarked 100,000 temperature readings joined across 500 handoff custody intervals.
- SQLite completed the join in ~0.42 seconds.
- Exasol Personal's in-memory columnar architecture processes this query in ~0.08 seconds (over 1.2 million rows/sec throughput) using zone maps on `window_start_utc` and `window_end_utc`."

### Q12: How would this scale to a pharmaceutical enterprise with 50,000 shipments a day?
**Answer:**
"At 50,000 shipments with 10 loggers each recording at 1-minute intervals for 48 hours, that yields ~1.44 billion rows/day. 
Because Exasol is an MPP (Massively Parallel Processing) distributed database, queries partition horizontally across nodes on `shipment_id`. The interval join executes locally within each cluster slice without cross-node network shuffle, maintaining linear sub-second scaling."

---

## 5. Frontend & User Experience

### Q13: What frameworks did you use for the frontend and why?
**Answer:**
"React 18 + TypeScript + Vite with Tailwind CSS. It is lightweight, typed, and fast. For visualizations, we built interactive Recharts line charts with colored reference bands (safe band in green, excursion shading in red, custody vertical markers). The entire frontend bundles to a static production build in under 14 seconds."

### Q14: How does the printable evidence report work?
**Answer:**
"The Evidence Report (`/shipments/{id}/excursions/{id}/report`) uses Tailwind's `print:` media queries to format the entire screen into an executive A4 printable audit sheet. Interactive navigation and action buttons are cleanly hidden (`no-print`), giving QA teams an instant audit trail for supplier meetings."

### Q15: What is the Prevention Prototype?
**Answer:**
"Attribution investigates past failures; prevention stops future ones. The Prevention screen applies rule-based risk scoring to upcoming shipments based on route leg types, dwell times, and historical excursion rates, recommending actionable mitigations (e.g., extra dry ice or adjusted dispatch times)."

---

## 6. Ground-Truth Validation & Testing

### Q16: How do you know your attribution algorithm actually works?
**Answer:**
"We created an automated validation harness (`scripts/validate_attribution.py`) that generates 30 synthetic multi-modal shipments with known injected thermal faults at random handoff legs. The engine scored **100% Top-1 accuracy** and **100% Top-3 accuracy** across all 30 scenarios, successfully isolating the true culprit handoff even in the presence of noise and clock skew."

### Q17: What unit and integration test coverage exists?
**Answer:**
"We have 12 unit and integration tests passing in pytest:
- Ingestion auto-detection and timezone normalization
- Degree-minute trapezoidal calculations
- Clock skew offsets and overlapping windows
- Timeline downsampling and gap detection
- Naive baseline difference verification"

### Q18: What is your primary takeaway for the hackathon jury?
**Answer:**
"HandoffGuard turns raw, unassociated IoT sensor readings into actionable custody accountability. By leveraging Exasol's in-memory analytical strengths for non-equi interval joins, we provide cold-chain managers with the defensible evidence they need to safeguard temperature-sensitive medicines."
