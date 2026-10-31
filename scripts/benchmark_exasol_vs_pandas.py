"""
HandoffGuard — Phase C Practical Benchmark
==========================================
Compares Exasol vs pandas for the interval join + exposure calculation
on the dense synthetic shipment (SHP-SYNTH-DENSE-01, 301 readings, 3 handoffs).

Design decisions to keep the comparison honest:
  - Both implementations reproduce the SAME calculation:
      corrected_time = reading_at_utc - clock_skew_seconds
      segment duration via LEAD over ordered readings (per logger)
      supported segment: 0 < duration <= MAX_GAP_SECONDS (600)
      exposure = sum((temp - product_max) * segment_minutes) where temp > product_max
  - Pandas does NOT use a Cartesian merge. It uses sorted boolean masks
    per handoff window — O(n_handoffs * n_readings), safe for the dataset size.
  - Correctness is verified before any timing is reported:
      both results must match to within 0.01 degree-minutes.
  - Timings are median over N_REPEATS real executions (no warm-up excluded).
  - Exasol timings include round-trip network latency and result-set fetch.
  - Environment (OS, Python, pandas, Exasol version) is disclosed.
  - This benchmark covers one shipment of 301 readings on a developer laptop.
    Results are NOT representative of production-scale workloads.

Usage:
  python scripts/benchmark_exasol_vs_pandas.py

Output:
  reports/benchmark_results.json
  reports/benchmark_results.md
"""

import sys
import ssl
import json
import time
import platform
import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import pyexasol

# ── Configuration ─────────────────────────────────────────────────────────────
SHIPMENT_ID = "SHP-SYNTH-DENSE-01"
MAX_GAP_SECONDS = 600  # prototype assumption, not a validated pharmaceutical standard
N_REPEATS = 10         # timing repetitions
TOLERANCE_DM = 0.01   # degree-minutes correctness tolerance
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


# ── Exasol connection ─────────────────────────────────────────────────────────

def connect_exasol():
    return pyexasol.connect(
        dsn="localhost:8563",
        user="sys",
        password="exasol",
        encryption=True,
        fetch_dict=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
    )


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_data(c, shipment_id):
    """Pull all needed tables for one shipment into pandas DataFrames."""
    readings = c.execute(f"""
        SELECT r.reading_id, r.logger_id, r.reading_at_utc, r.temperature_c,
               COALESCE(ld.clock_skew_seconds, 0) AS clock_skew_seconds,
               ld.assigned_shipment_id AS shipment_id
        FROM HANDOFFGUARD.logger_readings r
        JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id
        WHERE ld.assigned_shipment_id = '{shipment_id}'
        ORDER BY r.logger_id, r.reading_at_utc, r.reading_id
    """).fetchall()

    handoffs = c.execute(f"""
        SELECT h.id AS handoff_id, h.sequence_number, h.handoff_type,
               h.from_party, h.to_party, h.actual_start_at, h.actual_end_at
        FROM HANDOFFGUARD.handoffs h
        WHERE h.shipment_id = '{shipment_id}'
          AND h.actual_start_at IS NOT NULL
          AND h.actual_end_at IS NOT NULL
        ORDER BY h.sequence_number
    """).fetchall()

    product = c.execute(f"""
        SELECT p.min_temp_c, p.max_temp_c
        FROM HANDOFFGUARD.products p
        JOIN HANDOFFGUARD.shipments s ON s.product_id = p.id
        WHERE s.id = '{shipment_id}'
    """).fetchone()

    df_r = pd.DataFrame(readings)
    df_h = pd.DataFrame(handoffs)
    df_r.columns = [c.lower() for c in df_r.columns]
    df_h.columns = [c.lower() for c in df_h.columns]

    df_r["reading_at_utc"] = pd.to_datetime(df_r["reading_at_utc"])
    df_h["actual_start_at"] = pd.to_datetime(df_h["actual_start_at"])
    df_h["actual_end_at"] = pd.to_datetime(df_h["actual_end_at"])

    return df_r, df_h, float(product["MIN_TEMP_C"]), float(product["MAX_TEMP_C"])


# ── Exasol Benchmark ──────────────────────────────────────────────────────────

def run_exasol(c, shipment_id):
    """
    Query V_HANDOFF_THERMAL_EXPOSURE for the target shipment.
    Returns list of (handoff_id, total_degree_minutes) and elapsed_seconds.
    """
    t0 = time.perf_counter()
    rows = c.execute(f"""
        SELECT handoff_id, total_degree_minutes, supported_observation_minutes,
               coverage_status
        FROM HANDOFFGUARD.V_HANDOFF_THERMAL_EXPOSURE
        WHERE shipment_id = '{shipment_id}'
        ORDER BY handoff_id
    """).fetchall()
    elapsed = time.perf_counter() - t0
    result = [
        {
            "handoff_id": r["HANDOFF_ID"],
            "total_dm": float(r["TOTAL_DEGREE_MINUTES"] or 0),
            "supported_obs_min": float(r["SUPPORTED_OBSERVATION_MINUTES"] or 0),
            "coverage_status": r["COVERAGE_STATUS"],
        }
        for r in rows
    ]
    return result, elapsed


# ── Pandas Benchmark ──────────────────────────────────────────────────────────

def pandas_exposure(df_r, df_h, product_min_c, product_max_c):
    """
    Reproduce the same calculation as V_HANDOFF_THERMAL_EXPOSURE in pure pandas.

    Steps:
      1. Compute corrected_at_utc = reading_at_utc - clock_skew_seconds
      2. Sort by (logger_id, corrected_at_utc, reading_id) — deterministic
      3. LEAD via groupby shift(-1) to get segment_end
      4. Compute duration_seconds; mark as supported if 0 < dur <= MAX_GAP_SECONDS
      5. For each handoff window [actual_start_at, actual_end_at):
           - intersect segment [segment_start, segment_end) with window using
             boolean masks — NO Cartesian merge
           - clip overlap to window bounds
           - sum degree-minutes for above / below range
    """
    # Step 1: corrected time
    df = df_r.copy()
    df["corrected_at_utc"] = df["reading_at_utc"] - pd.to_timedelta(
        df["clock_skew_seconds"], unit="s"
    )

    # Step 2: sort deterministically
    df = df.sort_values(["logger_id", "corrected_at_utc", "reading_id"]).reset_index(drop=True)

    # Step 3: LEAD via shift within each logger
    df["segment_start"] = df["corrected_at_utc"]
    df["segment_end"] = df.groupby("logger_id")["corrected_at_utc"].shift(-1)

    # Step 4: duration and support flag
    df["duration_s"] = (df["segment_end"] - df["segment_start"]).dt.total_seconds()
    df["is_supported"] = (
        df["segment_end"].notna()
        & (df["duration_s"] > 0)
        & (df["duration_s"] <= MAX_GAP_SECONDS)
    )

    # Step 5: per-handoff accumulation using boolean masks (no Cartesian)
    results = []
    for _, hw in df_h.iterrows():
        win_start = hw["actual_start_at"]
        win_end = hw["actual_end_at"]

        # Segments that overlap [win_start, win_end) — half-open on both ends
        mask = (
            df["is_supported"]
            & (df["segment_start"] < win_end)
            & (df["segment_end"] > win_start)
        )
        segs = df[mask].copy()

        if segs.empty:
            results.append({
                "handoff_id": hw["handoff_id"],
                "total_dm": 0.0,
                "supported_obs_min": 0.0,
            })
            continue

        # Clip to handoff window
        overlap_start = segs["segment_start"].clip(lower=win_start)
        overlap_end = segs["segment_end"].clip(upper=win_end)
        overlap_min = (overlap_end - overlap_start).dt.total_seconds() / 60.0

        above_dm = np.where(
            segs["temperature_c"].values > product_max_c,
            (segs["temperature_c"].values - product_max_c) * overlap_min.values,
            0.0,
        )
        below_dm = np.where(
            segs["temperature_c"].values < product_min_c,
            (product_min_c - segs["temperature_c"].values) * overlap_min.values,
            0.0,
        )

        results.append({
            "handoff_id": hw["handoff_id"],
            "total_dm": round(float(above_dm.sum() + below_dm.sum()), 2),
            "supported_obs_min": round(float(overlap_min.sum()), 2),
        })

    return results


def run_pandas(df_r, df_h, product_min_c, product_max_c):
    t0 = time.perf_counter()
    result = pandas_exposure(df_r, df_h, product_min_c, product_max_c)
    elapsed = time.perf_counter() - t0
    return result, elapsed


# ── Correctness Check ─────────────────────────────────────────────────────────

def check_correctness(exasol_result, pandas_result):
    """
    Verify both implementations agree on total_degree_minutes per handoff.
    Returns (passed: bool, details: list[dict])
    """
    ex_map = {r["handoff_id"]: r["total_dm"] for r in exasol_result}
    pd_map = {r["handoff_id"]: r["total_dm"] for r in pandas_result}

    all_ids = sorted(set(ex_map) | set(pd_map))
    details = []
    all_ok = True
    for hid in all_ids:
        ex_dm = ex_map.get(hid, 0.0)
        pd_dm = pd_map.get(hid, 0.0)
        diff = abs(ex_dm - pd_dm)
        ok = diff <= TOLERANCE_DM
        if not ok:
            all_ok = False
        details.append({
            "handoff_id": hid,
            "exasol_dm": ex_dm,
            "pandas_dm": pd_dm,
            "diff": round(diff, 4),
            "ok": ok,
        })
    return all_ok, details


# ── Report Writers ────────────────────────────────────────────────────────────

def environment_info():
    try:
        import pandas as pd
        pandas_ver = pd.__version__
    except Exception:
        pandas_ver = "N/A"
    try:
        import numpy as np
        numpy_ver = np.__version__
    except Exception:
        numpy_ver = "N/A"
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "pandas": pandas_ver,
        "numpy": numpy_ver,
        "note": (
            "Exasol runs in Docker on the same developer laptop. "
            "Exasol timings include TCP round-trip and result-set fetch over loopback. "
            "Results are NOT representative of production-scale workloads."
        ),
    }


def write_json(data, path):
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"  JSON report written: {path}")


def write_md(data, path):
    env = data["environment"]
    corr = data["correctness"]
    ex_times = data["exasol_timings_s"]
    pd_times = data["pandas_timings_s"]
    summary = data["summary"]
    detail = data["per_handoff_correctness"]

    lines = [
        "# HandoffGuard — Practical Benchmark: Exasol vs pandas",
        "",
        "> **Scope**: Interval join + exposure calculation on one shipment "
        f"({data['shipment_id']}, {data['reading_count']} readings, "
        f"{data['handoff_count']} handoffs).  ",
        "> This is a developer-laptop benchmark — NOT a production workload comparison.",
        "",
        f"Generated: {data['generated_at']}",
        "",
        "---",
        "",
        "## Environment",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| OS | {env['os']} |",
        f"| Python | {env['python']} |",
        f"| pandas | {env['pandas']} |",
        f"| numpy | {env['numpy']} |",
        f"| Exasol | Docker, localhost:8563 |",
        f"| Readings | {data['reading_count']} |",
        f"| Handoffs | {data['handoff_count']} |",
        f"| Timing reps | {data['n_repeats']} |",
        "",
        f"> {env['note']}",
        "",
        "---",
        "",
        "## Correctness",
        "",
        f"Both implementations agree within {TOLERANCE_DM} °C·min tolerance: "
        f"**{'PASS' if corr else 'FAIL'}**",
        "",
        "| Handoff | Exasol DM | pandas DM | Diff | Match |",
        "|---|---|---|---|---|",
    ]
    for d in detail:
        icon = "✅" if d["ok"] else "❌"
        lines.append(
            f"| `{d['handoff_id']}` | {d['exasol_dm']:.2f} | "
            f"{d['pandas_dm']:.2f} | {d['diff']:.4f} | {icon} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Timing Results",
        "",
        f"Median over {data['n_repeats']} repetitions. "
        "Exasol includes network round-trip over loopback.",
        "",
        "| Engine | Median (ms) | Min (ms) | Max (ms) |",
        "|---|---|---|---|",
        f"| Exasol (view query + fetch) | {summary['exasol_median_ms']:.1f} | "
        f"{summary['exasol_min_ms']:.1f} | {summary['exasol_max_ms']:.1f} |",
        f"| pandas (in-process) | {summary['pandas_median_ms']:.1f} | "
        f"{summary['pandas_min_ms']:.1f} | {summary['pandas_max_ms']:.1f} |",
        "",
        "---",
        "",
        "## Methodology Notes",
        "",
        "- **Exasol**: queries `V_HANDOFF_THERMAL_EXPOSURE` (production repaired view) directly. "
          "Includes connection already established; measured is query dispatch + result fetch.",
        "- **pandas**: reproduces the identical calculation in Python:",
        "  - `corrected_at_utc = reading_at_utc − clock_skew_seconds`",
        "  - Segments via `groupby().shift(-1)` (same as SQL `LEAD`)",
        "  - Supported segments: `0 < duration <= 600 s`",
        "  - Interval join via **boolean masks per handoff window** — no Cartesian merge",
        "  - Overlap clipped to handoff boundaries; degree-minutes accumulated with NumPy",
        f"- Gap threshold: {MAX_GAP_SECONDS} s (engineering/demo prototype assumption, "
          "not a validated pharmaceutical standard)",
        "- Correctness is verified before speed is reported.",
        "- **Interpretation caveat**: Exasol is networked; pandas runs in-process. "
          "At 301 readings, pandas in-process is expected to be faster due to zero "
          "network overhead. The meaningful question is correctness agreement, not which "
          "is faster at this scale.",
        "",
        "---",
        "",
        "*Benchmark conducted on a developer laptop. "
        "Results are not representative of production-scale workloads.*",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Markdown report written: {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("HandoffGuard — Phase C Practical Benchmark: Exasol vs pandas")
    print("=" * 72)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n[1/4] Connecting to Exasol and loading data for {SHIPMENT_ID}...")
    c = connect_exasol()
    df_r, df_h, product_min_c, product_max_c = load_data(c, SHIPMENT_ID)
    print(f"  Loaded {len(df_r)} readings, {len(df_h)} handoffs, "
          f"product range [{product_min_c}, {product_max_c}] °C")

    print(f"\n[2/4] Correctness check (single run each)...")
    exasol_single, _ = run_exasol(c, SHIPMENT_ID)
    pandas_single, _ = run_pandas(df_r, df_h, product_min_c, product_max_c)
    correctness_ok, correctness_detail = check_correctness(exasol_single, pandas_single)

    for d in correctness_detail:
        icon = "MATCH" if d["ok"] else "MISMATCH"
        print(f"  [{icon}] {d['handoff_id']}: Exasol={d['exasol_dm']:.2f} "
              f"pandas={d['pandas_dm']:.2f} diff={d['diff']:.4f}")

    if not correctness_ok:
        print("\nERROR: Correctness check failed. Timing results would be meaningless.")
        print("Aborting benchmark.")
        sys.exit(1)

    print(f"  Correctness: PASS (all within {TOLERANCE_DM} °C·min)")

    print(f"\n[3/4] Timing {N_REPEATS} repetitions each...")
    exasol_times = []
    for i in range(N_REPEATS):
        _, t = run_exasol(c, SHIPMENT_ID)
        exasol_times.append(t)
        print(f"  Exasol rep {i+1:2d}: {t*1000:.1f} ms")

    pandas_times = []
    for i in range(N_REPEATS):
        _, t = run_pandas(df_r, df_h, product_min_c, product_max_c)
        pandas_times.append(t)
        print(f"  pandas rep {i+1:2d}: {t*1000:.1f} ms")

    ex_ms = [t * 1000 for t in exasol_times]
    pd_ms = [t * 1000 for t in pandas_times]

    summary = {
        "exasol_median_ms": round(float(np.median(ex_ms)), 2),
        "exasol_min_ms":    round(float(np.min(ex_ms)), 2),
        "exasol_max_ms":    round(float(np.max(ex_ms)), 2),
        "pandas_median_ms": round(float(np.median(pd_ms)), 2),
        "pandas_min_ms":    round(float(np.min(pd_ms)), 2),
        "pandas_max_ms":    round(float(np.max(pd_ms)), 2),
    }

    print(f"\n[4/4] Writing reports...")
    env = environment_info()

    report_data = {
        "_label": "Developer-laptop benchmark -- not a production workload comparison.",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "shipment_id": SHIPMENT_ID,
        "reading_count": len(df_r),
        "handoff_count": len(df_h),
        "n_repeats": N_REPEATS,
        "max_gap_seconds": MAX_GAP_SECONDS,
        "product_range_c": [product_min_c, product_max_c],
        "environment": env,
        "correctness": correctness_ok,
        "per_handoff_correctness": correctness_detail,
        "exasol_timings_s": [round(t, 6) for t in exasol_times],
        "pandas_timings_s": [round(t, 6) for t in pandas_times],
        "summary": summary,
    }

    json_path = REPORTS_DIR / "benchmark_results.json"
    md_path   = REPORTS_DIR / "benchmark_results.md"
    write_json(report_data, json_path)
    write_md(report_data, md_path)

    print()
    print("=" * 72)
    print(f"  Exasol (view query + fetch): median {summary['exasol_median_ms']:.1f} ms")
    print(f"  pandas  (in-process):        median {summary['pandas_median_ms']:.1f} ms")
    print(f"  Correctness: {'PASS' if correctness_ok else 'FAIL'}")
    print("=" * 72)
    print()
    print("  Interpretation note: Exasol is measured over a loopback TCP connection;")
    print("  pandas runs in-process. At 301 readings the network round-trip")
    print("  dominates Exasol's measured time. This is expected, not a flaw.")


if __name__ == "__main__":
    main()
