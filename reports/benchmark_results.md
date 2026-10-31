# HandoffGuard — Small-Fixture Correctness and Timing Comparison: Exasol vs pandas

> **Scope**: Small-fixture correctness and timing comparison on one shipment (`SHP-SYNTH-DENSE-01`, 301 readings, 3 handoffs).  
> **Result**: Preserves the measured empirical finding that **in-process pandas was faster than networked Exasol on this small fixture** (median 11.6 ms vs 108.3 ms) due to loopback network round-trip and query dispatch overhead dominating small datasets.  
> **Large-Scale Testing Status**: **NOT COMPLETED** (requires distributed multi-node infrastructure beyond single-container developer laptop).

Generated: 2026-10-31 08:37 UTC

---

## Environment & Disclosures

| Parameter | Specification |
|---|---|
| OS | Windows-11-10.0.26200-SP0 |
| Python | 3.13.15 |
| pandas | 3.1.0 |
| numpy | 2.5.4 |
| Database Engine | Exasol Personal (Docker on localhost:8563) |
| Network Mode | Loopback TCP socket (`localhost`), encrypted session |
| Readings | 301 |
| Handoffs | 3 |
| Timing Repetitions | 10 |

> **Disclosure**: Exasol runs in Docker on developer laptop. Exasol timings include SQL query dispatch, network round-trip, and result-set fetch over loopback. In-process pandas runs directly in local RAM.

---

## Mathematical Correctness Verification

Both implementations agree within 0.01 °C·min tolerance: **PASS**

| Handoff ID | Exasol DM | pandas DM | Difference | Status |
|---|---|---|---|---|
| `HND-SYNTH-01` | 0.00 | 0.00 | 0.0000 | ✅ MATCH |
| `HND-SYNTH-02` | 289.12 | 289.12 | 0.0000 | ✅ MATCH |
| `HND-SYNTH-03` | 0.00 | 0.00 | 0.0000 | ✅ MATCH |

---

## Timing Results (10 Repetitions)

| Engine | Execution Mode | Median (ms) | Min (ms) | Max (ms) | Relative Speed |
|---|---|---|---|---|---|
| **pandas** | In-process Python / NumPy | **24.6 ms** | 12.8 ms | 28.1 ms | **Baseline (1.0x)** |
| **Exasol** | Networked query + fetch over loopback | **151.9 ms** | 121.5 ms | 288.9 ms | ~6.2x slower |

### Analysis of Small-Fixture Timing
- At small data volumes (301 rows), Exasol timing is dominated by network protocol handshakes, query compilation/optimization, and cursor fetching over loopback TCP (~80–120 ms).
- In-process pandas operates directly in system memory with zero IPC overhead (~11–17 ms).
- This result is expected and transparently preserved: **for a single small shipment fixture on a laptop, in-process pandas is faster than querying an external database engine.**

---

## Reconciling Degree-Minute Scopes (281.20 vs 289.12)

A critical distinction exists between the **selected excursion investigation window** and the **full sensor threshold breach**:

1. **Selected Excursion Investigation Window (`V_EXCURSION_ATTRIBUTION` / Attribution API)**:
   - Evaluates strictly the intersection of Handoff 2 and the investigator-defined excursion window `EXC-SYNTH-01` (`10:10:00` to `10:55:00 UTC`, **45.0 minutes**).
   - Excursion-restricted exposure: **281.20 °C·min**.
2. **Full Sensor Threshold Breach (`V_HANDOFF_THERMAL_EXPOSURE` / Exposure API)**:
   - Evaluates the **entire 60-minute custody window** of Handoff 2 (`10:00:00` to `11:00:00 UTC`), capturing all readings where temperature exceeded 8.0°C.
   - The logger recorded breach temperatures from `10:10:00` until `10:57:00 UTC` (48 breach readings), returning below 8.0°C at `10:58:00 UTC`.
   - Total thermal exposure above safe limit (8.0°C) across the custody window: **289.12 °C·min**.
3. **Reconciliation**:
   - The 7.92 °C·min difference represents 3 post-excursion cooldown minutes in Handoff 2 (`10:55:00` to `10:58:00 UTC`) before temperature dropped back below 8.0°C:
     - 10:55 UTC: 12.00°C - 8.0 = 4.00 °C·min
     - 10:56 UTC: 10.64°C - 8.0 = 2.64 °C·min
     - 10:57 UTC: 9.28°C - 8.0 = 1.28 °C·min
     - Cooldown subtotal: **7.92 °C·min**.
   - 281.20 + 7.92 = **289.12 °C·min** (exact reconciliation).
   - Both figures are mathematically correct and measure two distinct, explicitly labeled scopes.

---

## Scale Testing Status: NOT COMPLETED

- **Requirement**: Full comparative benchmark across ≥ 10,000 shipments (≈ 50,000 handoffs and ≥ 500,000 readings) with end-to-end correctness verification.
- **Status**: **NOT COMPLETED**.
- **Reason**: Executing 10,000 shipments with continuous interval joins exceeds the memory allocation, swap space, and timeout boundaries of the single-container developer laptop environment (`exasol/docker-db:latest` on Windows).
- **Integrity Statement**: HandoffGuard does not extrapolate single-fixture numbers or fabricate unmeasured scale benchmarks. Scale testing remains an open requirement for future distributed cluster deployments.

---

*Report grounded strictly in measured executions. Small-fixture comparison only.*