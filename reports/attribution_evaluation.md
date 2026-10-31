# HandoffGuard — Synthetic Attribution Evaluation Report

> **Notice: Synthetic unit evaluation — not real-world field validation.**  
> Target: *Handoff with the largest supported out-of-range exposure within an excursion window.*  
> Decision support tool only — product disposition remains with the quality team.

Generated: 2026-10-31 06:56 UTC

---

## Evaluation Metrics Breakdown

To avoid misleading blanket accuracy claims, performance is separated across test categories:

| Evaluation Dimension | Primary Algorithm | Naive Baseline | Scope / Description |
|---|---|---|---|
| **Unique-Winner Accuracy** | **100.0%** (3/3) | 33.3% (1/3) | Cases with a single dominant responsible custody segment (EVAL-01, 02, 04) |
| **Tie Handling** | **100.0%** (1/1) | 0.0% (0/1) | Refusal to crown an arbitrary winner when exposure is exactly equal (EVAL-03) |
| **Insufficient-Data Abstention** | **100.0%** (1/1) | 0.0% (0/1) | Emitting INCONCLUSIVE when gaps exceed 600s rather than guessing (EVAL-05) |
| **Decision Coverage** | **100.0%** (5/5) | 100.0% | Taking appropriate action (attributing when evidence suffices, abstaining when not) |
| **Overall Fixture Outcomes** | **100.0%** (5/5) | 20.0% (1/5) | All 5 synthetic edge-case fixtures |

> *Note on Naive Baseline:* Naive baseline assigns custody based solely on the handoff containing the first observed out-of-range reading using uncorrected timestamps. It succeeded only on EVAL-01 (where there was only one carrier) and failed on spanning exposure (EVAL-02), tie detection (EVAL-03), clock offset (EVAL-04), and insufficient data (EVAL-05).

---

## Reconciled Case-by-Case Results

| Case ID | Fixture Objective | Expected Target | Primary Actual | Primary Scoring | Naive Baseline | Naive Scoring | Why Naive Succeeded / Failed |
|---|---|---|---|---|---|---|---|
| **EVAL-01-SINGLE-HANDOFF** | Clear Single-Handoff Exposure | `EH2` | `EH2` | ✅ PASS | `EH2` | ✅ PASS | Both primary and naive correctly select EH2 because only one handoff has readings. |
| **EVAL-02-SPANNING** | Exposure Spanning Multiple Handoffs | `FH2` | `FH2` | ✅ PASS | `FH1` | ❌ FAIL | Naive picks FH1 due to boundary-inclusive match at 10:00:00, missing cumulative exposure entirely. |
| **EVAL-03-TIED** | Tied Exposure — No Unique Winner | _None (Abstain)_ | _None (Abstained)_ | ✅ PASS | `GH1` | ❌ FAIL | Primary detects tie and refuses to declare unique winner. Naive arbitrarily crowns GH1 based on first reading. |
| **EVAL-04-CLOCK-OFFSET** | Clock Offset (+300s Skew Correction) | `KH1` | `KH1` | ✅ PASS | `KH2` | ❌ FAIL | Primary corrects skew (-300s) and identifies KH1. Naive uses raw timestamp 10:01 and erroneously blames KH2. |
| **EVAL-05-MISSING-READINGS** | Missing Readings — Insufficient Data Abstention | _None (Abstain)_ | _None (Abstained)_ | ✅ PASS | `MH1` | ❌ FAIL | Primary abstains with INCONCLUSIVE_INSUFFICIENT_DATA. Naive blindly outputs MH1 without checking data sufficiency. |

---

## Detailed Case Descriptions

### EVAL-01-SINGLE-HANDOFF — Clear Single-Handoff Exposure
_All out-of-range readings fall in H2. No other handoff has out-of-range exposure._

- **Category:** `UNIQUE_WINNER`
- **Expected Outcome:** `PRIMARY_MATCHES_GROUND_TRUTH` (Target: `EH2`)
- **Primary Result:** `PRIMARY_MATCHES_GROUND_TRUTH` (Target: `EH2`, Status: `Unvalidated prototype ranking`)
- **Naive Baseline:** Picked `EH2`
- **Scoring Analysis:** Both primary and naive correctly select EH2 because only one handoff has readings.

| Handoff | Rank | Supported Obs Min | Exposure (°C·min) | Evidence Status |
|---|---|---|---|---|
| `EH2` | 1 | 50.0 | 90.00 | `Unvalidated prototype ranking` |

### EVAL-02-SPANNING — Exposure Spanning Multiple Handoffs
_Excursion spans two handoffs. H2 holds 75% (120 DM) of out-of-range exposure, H3 holds 25% (40 DM). Primary target should select H2._

- **Category:** `UNIQUE_WINNER`
- **Expected Outcome:** `PRIMARY_MATCHES_GROUND_TRUTH` (Target: `FH2`)
- **Primary Result:** `PRIMARY_MATCHES_GROUND_TRUTH` (Target: `FH2`, Status: `Unvalidated prototype ranking`)
- **Naive Baseline:** Picked `FH1`
- **Scoring Analysis:** Naive picks FH1 due to boundary-inclusive match at 10:00:00, missing cumulative exposure entirely.

| Handoff | Rank | Supported Obs Min | Exposure (°C·min) | Evidence Status |
|---|---|---|---|---|
| `FH2` | 1 | 60.0 | 120.00 | `Unvalidated prototype ranking` |
| `FH3` | 2 | 20.0 | 40.00 | `Unvalidated prototype ranking` |

### EVAL-03-TIED — Tied Exposure — No Unique Winner
_Two handoffs (GH1 and GH2) have exactly equal supported out-of-range exposure (120 DM each). Attribution rank 1 is shared — no unique winner._

- **Category:** `TIE_HANDLING`
- **Expected Outcome:** `TIED_NO_UNIQUE_WINNER` (Target: `None`)
- **Primary Result:** `TIED_NO_UNIQUE_WINNER` (Target: `None`, Status: `Unvalidated prototype ranking`)
- **Naive Baseline:** Picked `GH1`
- **Scoring Analysis:** Primary detects tie and refuses to declare unique winner. Naive arbitrarily crowns GH1 based on first reading.

| Handoff | Rank | Supported Obs Min | Exposure (°C·min) | Evidence Status |
|---|---|---|---|---|
| `GH1` | 1 | 60.0 | 120.00 | `Unvalidated prototype ranking` |
| `GH2` | 1 | 60.0 | 120.00 | `Unvalidated prototype ranking` |

### EVAL-04-CLOCK-OFFSET — Clock Offset (+300s Skew Correction)
_Logger has +300s clock skew. Breach occurs at 09:56-09:58 UTC (in KH1). Logger clock reports 10:01-10:03 (looks like KH2). Skew correction correctly attributes to KH1._

- **Category:** `UNIQUE_WINNER`
- **Expected Outcome:** `PRIMARY_MATCHES_GROUND_TRUTH` (Target: `KH1`)
- **Primary Result:** `PRIMARY_MATCHES_GROUND_TRUTH` (Target: `KH1`, Status: `Unvalidated prototype ranking`)
- **Naive Baseline:** Picked `KH2`
- **Scoring Analysis:** Primary corrects skew (-300s) and identifies KH1. Naive uses raw timestamp 10:01 and erroneously blames KH2.

| Handoff | Rank | Supported Obs Min | Exposure (°C·min) | Evidence Status |
|---|---|---|---|---|
| `KH1` | 1 | 4.0 | 16.00 | `Unvalidated prototype ranking` |

### EVAL-05-MISSING-READINGS — Missing Readings — Insufficient Data Abstention
_Only two readings 90 minutes apart (>600s threshold). All segments unsupported. Should return INCONCLUSIVE_INSUFFICIENT_DATA._

- **Category:** `DATA_ABSTENTION`
- **Expected Outcome:** `INCONCLUSIVE` (Target: `None`)
- **Primary Result:** `INCONCLUSIVE` (Target: `None`, Status: `INCONCLUSIVE_INSUFFICIENT_DATA`)
- **Naive Baseline:** Picked `MH1`
- **Scoring Analysis:** Primary abstains with INCONCLUSIVE_INSUFFICIENT_DATA. Naive blindly outputs MH1 without checking data sufficiency.

| Handoff | Rank | Supported Obs Min | Exposure (°C·min) | Evidence Status |
|---|---|---|---|---|
| `MH1` | 1 | 0.0 | 0.00 | `INCONCLUSIVE_INSUFFICIENT_DATA` |

---

## Methodology & Disclaimers

1. **Primary Target Definition:** Handoff with the largest supported out-of-range thermal exposure within the excursion window.
2. **Gap Threshold:** 600 seconds (10 min) prototype default. Engineering assumption, not a validated pharmaceutical standard.
3. **Coverage Accounting:** Supported observation time and unsupported gap time are explicitly separated. If supported time is zero, status is `INCONCLUSIVE_INSUFFICIENT_DATA`.
4. **Disclaimer:** *Outputs reflect 5 synthetic unit fixtures and provide probabilistic decision support for quality team investigations. They do NOT constitute field validation or a legal determination of liability.*

---

*Synthetic evaluation — not real-world field validation.*