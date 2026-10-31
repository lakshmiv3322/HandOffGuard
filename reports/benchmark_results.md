# HandoffGuard — Practical Benchmark: Exasol vs pandas

> **Scope**: Interval join + exposure calculation on one shipment (SHP-SYNTH-DENSE-01, 301 readings, 3 handoffs).  
> This is a developer-laptop benchmark — NOT a production workload comparison.

Generated: 2026-10-31 05:57 UTC

---

## Environment

| Field | Value |
|---|---|
| OS | Windows-11-10.0.26200-SP0 |
| Python | 3.13.15 |
| pandas | 3.1.0 |
| numpy | 2.5.4 |
| Exasol | Docker, localhost:8563 |
| Readings | 301 |
| Handoffs | 3 |
| Timing reps | 10 |

> Exasol runs in Docker on the same developer laptop. Exasol timings include TCP round-trip and result-set fetch over loopback. Results are NOT representative of production-scale workloads.

---

## Correctness

Both implementations agree within 0.01 °C·min tolerance: **PASS**

| Handoff | Exasol DM | pandas DM | Diff | Match |
|---|---|---|---|---|
| `HND-SYNTH-01` | 0.00 | 0.00 | 0.0000 | ✅ |
| `HND-SYNTH-02` | 289.12 | 289.12 | 0.0000 | ✅ |
| `HND-SYNTH-03` | 0.00 | 0.00 | 0.0000 | ✅ |

---

## Timing Results

Median over 10 repetitions. Exasol includes network round-trip over loopback.

| Engine | Median (ms) | Min (ms) | Max (ms) |
|---|---|---|---|
| Exasol (view query + fetch) | 112.6 | 94.9 | 231.9 |
| pandas (in-process) | 11.6 | 7.7 | 21.9 |

---

## Methodology Notes

- **Exasol**: queries `V_HANDOFF_THERMAL_EXPOSURE` (production repaired view) directly. Includes connection already established; measured is query dispatch + result fetch.
- **pandas**: reproduces the identical calculation in Python:
  - `corrected_at_utc = reading_at_utc − clock_skew_seconds`
  - Segments via `groupby().shift(-1)` (same as SQL `LEAD`)
  - Supported segments: `0 < duration <= 600 s`
  - Interval join via **boolean masks per handoff window** — no Cartesian merge
  - Overlap clipped to handoff boundaries; degree-minutes accumulated with NumPy
- Gap threshold: 600 s (engineering/demo prototype assumption, not a validated pharmaceutical standard)
- Correctness is verified before speed is reported.
- **Interpretation caveat**: Exasol is networked; pandas runs in-process. At 301 readings, pandas in-process is expected to be faster due to zero network overhead. The meaningful question is correctness agreement, not which is faster at this scale.

---

*Benchmark conducted on a developer laptop. Results are not representative of production-scale workloads.*