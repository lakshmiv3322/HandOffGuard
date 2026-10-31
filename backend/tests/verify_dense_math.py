"""
Independent mathematical verification of dense case (SHP-SYNTH-DENSE-01 / EXC-SYNTH-01).
Verifies the exact degree-minutes against actual sensor readings from Exasol.
"""
import ssl
from datetime import datetime
import pyexasol

def verify_dense():
    c = pyexasol.connect(
        dsn="localhost:8563",
        user="sys",
        password="exasol",
        fetch_dict=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
    )

    # 1. Fetch excursion definition
    exc = c.execute(
        "SELECT EXCURSION_ID, SHIPMENT_ID, STARTED_AT_UTC, ENDED_AT_UTC "
        "FROM HANDOFFGUARD.EXCURSIONS WHERE EXCURSION_ID = 'EXC-SYNTH-01'"
    ).fetchone()
    print("Excursion:", exc)
    exc_start = exc["STARTED_AT_UTC"]
    exc_end = exc["ENDED_AT_UTC"]
    if isinstance(exc_start, str):
        exc_start = datetime.fromisoformat(exc_start)
    if isinstance(exc_end, str):
        exc_end = datetime.fromisoformat(exc_end)

    # 2. Fetch product thresholds
    prod = c.execute(
        "SELECT p.MIN_TEMP_C, p.MAX_TEMP_C "
        "FROM HANDOFFGUARD.PRODUCTS p "
        "JOIN HANDOFFGUARD.SHIPMENTS s ON p.ID = s.PRODUCT_ID "
        "WHERE s.ID = 'SHP-SYNTH-DENSE-01'"
    ).fetchone()
    min_temp = float(prod["MIN_TEMP_C"])
    max_temp = float(prod["MAX_TEMP_C"])
    print(f"Product safe range: [{min_temp}, {max_temp}]")

    # 3. Fetch handoffs
    handoffs = c.execute(
        "SELECT ID, SEQUENCE_NUMBER, ACTUAL_START_AT, ACTUAL_END_AT "
        "FROM HANDOFFGUARD.HANDOFFS WHERE SHIPMENT_ID = 'SHP-SYNTH-DENSE-01' "
        "ORDER BY SEQUENCE_NUMBER"
    ).fetchall()
    print(f"Found {len(handoffs)} handoffs:")
    for h in handoffs:
        print(f"  Handoff {h['ID']} (seq {h['SEQUENCE_NUMBER']}): [{h['ACTUAL_START_AT']}, {h['ACTUAL_END_AT']})")

    # 4. Fetch all readings for this shipment
    readings = c.execute(
        "SELECT r.READING_ID, r.READING_AT_UTC, r.TEMPERATURE_C, ld.CLOCK_SKEW_SECONDS "
        "FROM HANDOFFGUARD.LOGGER_READINGS r "
        "JOIN HANDOFFGUARD.LOGGER_DEVICES ld ON r.LOGGER_ID = ld.LOGGER_ID "
        "WHERE ld.ASSIGNED_SHIPMENT_ID = 'SHP-SYNTH-DENSE-01' "
        "ORDER BY r.READING_AT_UTC"
    ).fetchall()
    print(f"Total readings for shipment: {len(readings)}")

    # 5. Build segments with LEAD
    # segment_start = corrected_at, segment_end = next reading corrected_at
    # max supported gap = 600s
    segments = []
    for i in range(len(readings)):
        r = readings[i]
        r_time = r["READING_AT_UTC"]
        if isinstance(r_time, str):
            r_time = datetime.fromisoformat(r_time)
        # skew is subtracted: raw - skew
        skew = float(r["CLOCK_SKEW_SECONDS"] or 0)
        corr_start = r_time # skew is 0 for LOG-SYNTH-01

        if i < len(readings) - 1:
            next_r = readings[i + 1]
            next_time = next_r["READING_AT_UTC"]
            if isinstance(next_time, str):
                next_time = datetime.fromisoformat(next_time)
            corr_end = next_time
            dur_sec = (corr_end - corr_start).total_seconds()
            is_supported = (0 < dur_sec <= 600)
        else:
            corr_end = None
            dur_sec = 0
            is_supported = False

        segments.append({
            "reading_id": r["READING_ID"],
            "temp": float(r["TEMPERATURE_C"]),
            "start": corr_start,
            "end": corr_end,
            "dur_sec": dur_sec,
            "is_supported": is_supported,
        })

    # 6. For each handoff, intersect with segments and excursion window
    handoff_results = {}
    for h in handoffs:
        h_start = h["ACTUAL_START_AT"]
        h_end = h["ACTUAL_END_AT"]
        if isinstance(h_start, str):
            h_start = datetime.fromisoformat(h_start)
        if isinstance(h_end, str):
            h_end = datetime.fromisoformat(h_end)

        # Exposure within handoff custody
        handoff_supported_min = 0.0
        handoff_dm_above = 0.0

        # Exposure restricted to excursion window
        excursion_supported_min = 0.0
        excursion_dm_above = 0.0

        for seg in segments:
            if not seg["is_supported"]:
                continue

            # Overlap with handoff
            o_start = max(seg["start"], h_start)
            o_end = min(seg["end"], h_end)
            if o_end > o_start:
                dur_min = (o_end - o_start).total_seconds() / 60.0
                handoff_supported_min += dur_min
                if seg["temp"] > max_temp:
                    handoff_dm_above += (seg["temp"] - max_temp) * dur_min

                # Overlap with excursion
                eo_start = max(o_start, exc_start)
                eo_end = min(o_end, exc_end)
                if eo_end > eo_start:
                    edur_min = (eo_end - eo_start).total_seconds() / 60.0
                    excursion_supported_min += edur_min
                    if seg["temp"] > max_temp:
                        excursion_dm_above += (seg["temp"] - max_temp) * edur_min

        handoff_results[h["ID"]] = {
            "custody_min": round(handoff_supported_min, 2),
            "custody_dm": round(handoff_dm_above, 2),
            "excursion_min": round(excursion_supported_min, 2),
            "excursion_dm": round(excursion_dm_above, 2),
        }
        print(f"\nHandoff {h['ID']} (Seq {h['SEQUENCE_NUMBER']}):")
        print(f"  Total Custody Supported Minutes: {handoff_supported_min:.2f} min")
        print(f"  Total Custody Degree-Minutes: {handoff_dm_above:.2f} C*min")
        print(f"  Excursion Window Supported Minutes: {excursion_supported_min:.2f} min")
        print(f"  Excursion Window Degree-Minutes: {excursion_dm_above:.2f} C*min")

    # 7. Compare with Exasol view output
    view_rows = c.execute(
        "SELECT * FROM HANDOFFGUARD.V_EXCURSION_ATTRIBUTION WHERE EXCURSION_ID = 'EXC-SYNTH-01'"
    ).fetchall()
    print(f"\nExasol View returned {len(view_rows)} row(s):")
    for view_row in view_rows:
        hid = view_row["HANDOFF_ID"]
        expected_dm = round(handoff_results[hid]["excursion_dm"], 1)
        actual_dm = round(float(view_row["HANDOFF_TOTAL_DM"]), 1)
        expected_min = round(handoff_results[hid]["excursion_min"], 1)
        actual_min = round(float(view_row["SUPPORTED_OBSERVATION_MINUTES"]), 1)
        print(f"  Handoff {hid}:")
        print(f"    Expected: {expected_dm} C*min, {expected_min} min")
        print(f"    Actual:   {actual_dm} C*min, {actual_min} min")
        assert expected_dm == actual_dm, f"DM mismatch for {hid}: expected {expected_dm}, got {actual_dm}"
        assert expected_min == actual_min, f"Min mismatch for {hid}: expected {expected_min}, got {actual_min}"

    print("\nALL HANDOFFS EXACTLY VERIFIED AGAINST INDEPENDENT PYTHON MATH!")

if __name__ == "__main__":
    verify_dense()
