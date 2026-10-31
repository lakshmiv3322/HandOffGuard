"""
End-to-end API smoke test for HandoffGuard analytics endpoints.
Tests both sparse (SHP-2026-0881) and dense (SHP-SYNTH-DENSE-01) scenarios.
Exits nonzero on any failure.
"""
import json
import sys
import requests

BASE_URL = "http://localhost:8000"

SPARSE_SHIPMENT = "SHP-2026-0881"
DENSE_SHIPMENT  = "SHP-SYNTH-DENSE-01"
SPARSE_EXCURSION = "EXC-1002"
DENSE_EXCURSION  = "EXC-SYNTH-01"

failures = []

def check(test_name, cond, detail=""):
    if cond:
        print(f"  PASS  {test_name}")
    else:
        print(f"  FAIL  {test_name}  {detail}")
        failures.append(f"{test_name}: {detail}")


def test_membership(shipment_id, expect_engine="exasol"):
    print(f"\n--- Membership: {shipment_id} ---")
    r = requests.get(f"{BASE_URL}/api/shipments/{shipment_id}/membership", timeout=30)
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        return None
    d = r.json()
    check("engine=exasol", d.get("engine") == expect_engine, d.get("engine"))
    check("has counts", "counts" in d)
    check("has items list", isinstance(d.get("items"), list))
    check("shipment_id matches", str(d.get("shipment_id")) == str(shipment_id))
    check("has disclaimer", bool(d.get("disclaimer")))
    print(f"         counts: {d.get('counts')}, items: {len(d.get('items', []))}")
    return d


def test_exposure(shipment_id, expect_engine="exasol"):
    print(f"\n--- Exposure: {shipment_id} ---")
    r = requests.get(f"{BASE_URL}/api/shipments/{shipment_id}/exposure", timeout=30)
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        print("  Body:", r.text[:400])
        return None
    d = r.json()
    check("shipment_id matches", str(d.get("shipment_id")) == str(shipment_id))
    check("has handoffs", isinstance(d.get("handoffs"), list))
    check("has disclaimer", bool(d.get("disclaimer")))
    for h in d.get("handoffs", []):
        check(f"  handoff {h.get('sequence_no')} has coverage_status",
              "coverage_status" in h, str(h.get("coverage_status")))
        check(f"  handoff {h.get('sequence_no')} has supported_observation_minutes",
              "supported_observation_minutes" in h)
    print(f"         handoffs: {len(d.get('handoffs', []))}, "
          f"total_dm: {d.get('total_shipment_degree_minutes')}")
    return d


def test_attribution(excursion_id, expect_evidence_status=None, expect_coverage_status=None):
    print(f"\n--- Attribution: {excursion_id} ---")
    r = requests.get(f"{BASE_URL}/api/excursions/{excursion_id}/attribution", timeout=30)
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        print("  Body:", r.text[:400])
        return None
    d = r.json()
    check("has ranked_handoffs", isinstance(d.get("ranked_handoffs"), list))
    check("has disclaimer", bool(d.get("disclaimer")))
    check("has limitations", isinstance(d.get("limitations"), list) and len(d.get("limitations", [])) > 0)
    for rh in d.get("ranked_handoffs", []):
        ev = rh.get("evidence_notes", [])
        check(f"  rank {rh.get('rank')} has evidence_notes", len(ev) > 0)
        if expect_evidence_status:
            any_match = any(expect_evidence_status in n for n in ev)
            check(f"  rank {rh.get('rank')} note contains '{expect_evidence_status}'", any_match,
                  f"notes: {ev[:2]}")
    print(f"         ranked_handoffs: {len(d.get('ranked_handoffs', []))}")
    if d.get("top_ranked_handoff"):
        top = d["top_ranked_handoff"]
        label = (top.get('handoff_label') or '').encode('ascii', 'replace').decode('ascii')
        print(f"         top: {label}, dm={top.get('exposure_degree_minutes')}, "
              f"conf={top.get('confidence_label')}")
    return d


def test_telemetry(shipment_id):
    print(f"\n--- Telemetry Drilldown: {shipment_id} ---")
    r = requests.get(f"{BASE_URL}/api/shipments/{shipment_id}/telemetry-drilldown", timeout=30)
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code != 200:
        print("  Body:", r.text[:400])
        return None
    d = r.json()
    check("shipment_id matches", str(d.get("shipment_id")) == str(shipment_id))
    check("has readings", isinstance(d.get("readings"), list))
    check("has handoffs", isinstance(d.get("handoffs"), list))
    check("has gaps list", isinstance(d.get("gaps"), list))
    # Check skew correction sign
    for rd in d.get("readings", [])[:3]:
        skew = rd.get("clock_skew_seconds", 0)
        raw_ts = rd.get("reading_at_utc", "")
        adj_ts = rd.get("adjusted_reading_at_utc", "")
        if skew != 0 and raw_ts and adj_ts:
            # adjusted = raw - skew  (if skew > 0, adj < raw)
            check(f"  reading skew sign correct (skew={skew}s)",
                  (raw_ts > adj_ts) == (skew > 0) or (raw_ts < adj_ts) == (skew < 0))
    print(f"         readings: {len(d.get('readings', []))}, "
          f"gaps: {len(d.get('gaps', []))}")
    return d


def test_health():
    print(f"\n--- Health ---")
    r = requests.get(f"{BASE_URL}/health", timeout=15)
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    d = r.json()
    db_status = d.get("database_connection_status") or d.get("db_status", "")
    check("DB connected", "connected" in str(db_status).lower() or "ok" in str(db_status).lower(),
          f"db_status={db_status}")
    print(f"         status={d.get('status')}, db={db_status}")
    return d


if __name__ == "__main__":
    print("=" * 60)
    print("HandoffGuard API Endpoint Tests")
    print("=" * 60)

    test_health()

    # Sparse shipment
    test_membership(SPARSE_SHIPMENT)
    sparse_exp = test_exposure(SPARSE_SHIPMENT)
    if sparse_exp:
        for h in sparse_exp.get("handoffs", []):
            cs = h.get("coverage_status", "")
            check(f"  sparse handoff {h.get('sequence_no')} coverage_status=INCONCLUSIVE or NO_SUPPORTED",
                  "INCONCLUSIVE" in cs or "NO_SUPPORTED" in cs or "PARTIAL" in cs, cs)
    test_attribution(SPARSE_EXCURSION, expect_evidence_status="INCONCLUSIVE")
    test_telemetry(SPARSE_SHIPMENT)

    # Dense shipment
    test_membership(DENSE_SHIPMENT)
    dense_exp = test_exposure(DENSE_SHIPMENT)
    if dense_exp:
        for h in dense_exp.get("handoffs", []):
            if h.get("total_degree_minutes", 0) > 0:
                check(f"  dense handoff {h.get('sequence_no')} has positive exposure",
                      h["total_degree_minutes"] > 0, str(h["total_degree_minutes"]))
    test_attribution(DENSE_EXCURSION, expect_evidence_status="Unvalidated")
    test_telemetry(DENSE_SHIPMENT)

    print("\n" + "=" * 60)
    if failures:
        print(f"RESULT: {len(failures)} FAILURE(S)")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("RESULT: ALL TESTS PASSED")
        sys.exit(0)
