# HandoffGuard — 3-Minute Live Demo Script
**ExaThon India 2026 Hackathon Presentation**

---

## 🎯 Target Audience
Jury of data architects, supply-chain experts, and Exasol technical evaluators.

## ⏱ Timeline Breakdown
- **0:00 - 0:40**: The Problem & The Critical Data Constraint
- **0:40 - 1:25**: Exasol In-Memory Interval Join & Timeline Walkthrough
- **1:25 - 2:15**: Thermal Exposure & Attribution Engine (Naive Baseline Disproof)
- **2:15 - 2:45**: Evidence Report & Prevention Prototype
- **2:45 - 3:00**: Wrap-up & Exasol Value Demonstration

---

### Step 1: The Problem (0:00 - 0:40)
*Screen: Shipments Dashboard (`http://localhost:5173/`)*

**Speaker Script:**
> "Good evening, judges. In pharmaceutical cold chains, sensitive vaccines and biologics travel through multiple custodians: central cold warehouses, line-haul reefer trucks, air cargo, and last-mile motorbike couriers.
>
> When a shipment arrives warm, everyone blames the last person who touched it. But here is the critical data reality: **IoT temperature loggers do not know who owns the package.** The temperature records contain only a logger ID, a timestamp, and a temperature reading — **there is NO handoff ID in the telemetry**.
>
> In our database, this is strictly enforced: `logger_readings` has no custody foreign key. Connecting fragmented sensor readings to custody windows requires continuous non-equi interval joins over millions of data points.
>
> Let's open shipment **`SHP-2026-001`**, transporting mRNA Vaccine-21 requiring 2°C to 8°C."

*Action: Click on `SHP-2026-001` to navigate to the Custody Timeline.*

---

### Step 2: Custody Timeline & Exasol Interval Join (0:40 - 1:25)
*Screen: Shipment Custody Timeline (`http://localhost:5173/shipments/1`)*

**Speaker Script:**
> "Here on the timeline, HandoffGuard reconstructs the entire multi-modal journey. Notice three key engineering features:
>
> 1. **Data Quality & Skew Correction**: Loggers often have clock drift. Logger 2 has a +120s skew, which our engine auto-corrects before interval matching.
> 2. **Telemetry Gap Detection**: The dashed red zone flags where logger transmission dropped for 45 minutes between Warehouse Dispatch and Highway Reefer.
> 3. **Exasol Membership Interval Join**: Scrolling down to the Interval Join Membership tab, this table is computed directly by Exasol's view:
>    `r.reading_at_utc BETWEEN h.window_start_utc AND h.window_end_utc`
>    Exasol processes this non-equi interval join in under 82 milliseconds across 100,000 readings, resolving which custodian held the package at every minute.
>
> Now, notice the temperature excursion shaded in red starting at 14:15 UTC. Let's investigate who caused it."

*Action: Click on the excursion badge or 'Investigate Attribution' button.*

---

### Step 3: Attribution Engine & Naive Baseline Disproof (1:25 - 2:15)
*Screen: Attribution Investigation (`http://localhost:5173/shipments/1/excursions/1`)*

**Speaker Script:**
> "This is where HandoffGuard shines. 
> 
> A standard ERP or naive logistics rule simply blames the **first handoff** during which the 8.0°C threshold was breached. Look at our **Naive Baseline Comparison card**:
> - The naive rule blames **Leg 2 (Cross-Dock Transfer)** because the temperature nudged to 8.4°C for just 8 minutes.
> - But HandoffGuard calculates cumulative thermal stress in **degree-minutes**: $\int \max(0, T(t) - T_{\text{max}}) \, dt$.
> 
> Look at the attribution ranking:
> - **Leg 4 (Inter-facility Transit / City Courier)** is ranked **#1** with **82.3% of thermal exposure**! The temperature spiked to a catastrophic 14.8°C while waiting on an unshaded tarmac dock.
> 
> HandoffGuard produces probabilistic attribution scores backed by hard metrics: exposure share, duration outside safe range, peak temperature, logger confidence, and clock skew adjustments.
> We do not claim to settle legal disputes; we give quality assurance managers defensible evidence."

---

### Step 4: Evidence Report & Prevention Prototype (2:15 - 2:45)
*Screen: Evidence Report (`/report`) then Prevention Prototype (`/prevention`)*

**Speaker Script:**
> "Clicking **'Printable Evidence Report'**, we get an executive PDF-ready audit document detailing shipment metadata, product thermal mass limits, sensor telemetry notes, and methodology disclaimers.
>
> Furthermore, under **'Prevention Prototype'**, we demonstrate our forward-looking advisory screen:
> Before dispatching tomorrow's shipment, rule-based heuristics flag that midday transfers at the Phoenix Hub carry high risk based on previous excursion frequency, recommending pre-conditioned phase-change thermal covers."

*Action: Show the print-friendly view and click into Prevention tab.*

---

### Step 5: Summary & Exasol Value (2:45 - 3:00)

**Speaker Script:**
> "To summarize:
> - **Exasol Engine**: Delivers sub-second interval joins over non-equi time ranges, eliminating expensive ETL denormalization.
> - **Ingestion Pipeline**: Handles 3 disparate CSV formats with automatic timezone normalization.
> - **Ground-Truth Validation**: Achieved 100% Top-1 accuracy across 30 synthetic validation scenarios.
> 
> Thank you, and we welcome your questions!"
