# HandoffGuard — Attribution Evaluation Report

> **Synthetic evaluation — not field validation.**  
> Primary target: *handoff with the largest supported out-of-range exposure within an excursion window.*  
> This is evidence-aid ranking for quality-team investigation support only — not root-cause identification.

Generated: 2026-10-31 05:51 UTC

---

## Summary

| Metric | Value |
|---|---|
| Total cases | 5 |
| Primary algorithm correct | 5 / 5 |
| Naive baseline correct | 3 / 5 |
| Primary accuracy | 100.0% |
| Naive accuracy | 60.0% |

---

## Case-by-Case Results

### ✅ EVAL-01-SINGLE-HANDOFF — Clear Single-Handoff Exposure

_Clear single-handoff exposure. All readings during excursion fall in H2. No other handoff overlaps._

| Field | Value |
|---|---|
| Excursion | `EXC-E01` |
| Expected primary handoff | `EH2` |
| Actual primary handoff | `EH2` |
| Top exposure (°C·min) | 90.0 |
| Evidence status | `Unvalidated prototype ranking` |
| Expected outcome | `PRIMARY_MATCHES_GROUND_TRUTH` |
| Actual outcome | `PRIMARY_MATCHES_GROUND_TRUTH` |
| Primary correct | Yes |
| Naive baseline handoff | `EH2` |
| Naive correct | Yes |

**Attribution rows returned by V_EXCURSION_ATTRIBUTION:**

| Handoff | Rank | Obs Min | DM (°C·min) | Status |
|---|---|---|---|---|
| `EH2` | 1 | 50.0 | 90.00 | `Unvalidated prototype ranking` |

### ✅ EVAL-02-SPANNING — Exposure Spanning Two Handoffs

_Excursion spans two handoffs. H2 holds 75% of out-of-range exposure, H3 holds 25%. Primary target should select H2._

| Field | Value |
|---|---|
| Excursion | `EXC-E02` |
| Expected primary handoff | `FH2` |
| Actual primary handoff | `FH2` |
| Top exposure (°C·min) | 120.0 |
| Evidence status | `Unvalidated prototype ranking` |
| Expected outcome | `PRIMARY_MATCHES_GROUND_TRUTH` |
| Actual outcome | `PRIMARY_MATCHES_GROUND_TRUTH` |
| Primary correct | Yes |
| Naive baseline handoff | `FH1` |
| Naive correct | No |

**Attribution rows returned by V_EXCURSION_ATTRIBUTION:**

| Handoff | Rank | Obs Min | DM (°C·min) | Status |
|---|---|---|---|---|
| `FH2` | 1 | 60.0 | 120.00 | `Unvalidated prototype ranking` |
| `FH3` | 2 | 20.0 | 40.00 | `Unvalidated prototype ranking` |

### ✅ EVAL-03-TIED — Tied Exposure — No Unique Winner

_Two handoffs have exactly equal supported out-of-range exposure. Attribution rank 1 is shared — no unique winner._

| Field | Value |
|---|---|
| Excursion | `EXC-E03` |
| Expected primary handoff | `None` |
| Actual primary handoff | `None` |
| Top exposure (°C·min) | 120.0 |
| Evidence status | `Unvalidated prototype ranking` |
| Expected outcome | `TIED_NO_UNIQUE_WINNER` |
| Actual outcome | `TIED_NO_UNIQUE_WINNER` |
| Primary correct | Yes |
| Naive baseline handoff | `GH1` |
| Naive correct | Yes |

**Attribution rows returned by V_EXCURSION_ATTRIBUTION:**

| Handoff | Rank | Obs Min | DM (°C·min) | Status |
|---|---|---|---|---|
| `GH1` | 1 | 60.0 | 120.00 | `Unvalidated prototype ranking` |
| `GH2` | 1 | 60.0 | 120.00 | `Unvalidated prototype ranking` |

### ✅ EVAL-04-CLOCK-OFFSET — Clock Offset +300s Correction

_Logger has +300s clock skew. Without correction, readings land in wrong handoff. With correction, H2 is correctly identified._

| Field | Value |
|---|---|
| Excursion | `EXC-E04` |
| Expected primary handoff | `KH2` |
| Actual primary handoff | `KH2` |
| Top exposure (°C·min) | 70.0 |
| Evidence status | `Unvalidated prototype ranking` |
| Expected outcome | `PRIMARY_MATCHES_GROUND_TRUTH` |
| Actual outcome | `PRIMARY_MATCHES_GROUND_TRUTH` |
| Primary correct | Yes |
| Naive baseline handoff | `KH2` |
| Naive correct | No |

**Attribution rows returned by V_EXCURSION_ATTRIBUTION:**

| Handoff | Rank | Obs Min | DM (°C·min) | Status |
|---|---|---|---|---|
| `KH2` | 1 | 35.0 | 70.00 | `Unvalidated prototype ranking` |

### ✅ EVAL-05-MISSING-READINGS — Missing Readings — Inconclusive

_Only two readings >600s apart. All segments unsupported. Should return INCONCLUSIVE_INSUFFICIENT_DATA._

| Field | Value |
|---|---|
| Excursion | `EXC-E05` |
| Expected primary handoff | `None` |
| Actual primary handoff | `None` |
| Top exposure (°C·min) | — |
| Evidence status | `INCONCLUSIVE_INSUFFICIENT_DATA` |
| Expected outcome | `INCONCLUSIVE` |
| Actual outcome | `INCONCLUSIVE` |
| Primary correct | Yes |
| Naive baseline handoff | `MH1` |
| Naive correct | Yes |

**Attribution rows returned by V_EXCURSION_ATTRIBUTION:**

| Handoff | Rank | Obs Min | DM (°C·min) | Status |
|---|---|---|---|---|
| `MH1` | 1 | 0.0 | 0.00 | `INCONCLUSIVE_INSUFFICIENT_DATA` |

---

## Methodology Notes

- **Primary target**: handoff with `MAX(handoff_total_dm)` within the excursion window, using supported sensor segments (gap ≤ 600 s).
- **Naive baseline**: handoff containing the first observed out-of-range reading, using uncorrected raw timestamps and inclusive `>=` / `<=` boundaries.
- **Clock correction**: primary target applies `corrected_time = reading_at_utc − clock_skew_seconds`.
- **Ambiguous custody**: segments overlapping multiple handoffs are excluded from attributable exposure.
- **Insufficient data**: if all segments are unsupported (gap > 600 s), status = `INCONCLUSIVE_INSUFFICIENT_DATA`.
- **Tied exposure**: if two handoffs share rank 1, no unique winner is reported.

> Gap threshold of 600 s is an engineering/demo prototype assumption — not a validated pharmaceutical standard.

---

*Synthetic evaluation — not field validation.*