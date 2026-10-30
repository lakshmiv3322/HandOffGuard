"""
HandoffGuard — Attribution Validation Script
ExaThon India 2026

Validates the custody-attribution engine against synthetic shipments
with known injected ground-truth fault locations.

Calculates:
- Top-1 accuracy
- Top-3 accuracy
- Mean confidence score
- High-confidence precision
- Low-confidence recall
- Average attribution score

Outputs:
- reports/attribution_validation.json
"""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timedelta, timezone

# Ensure backend is in python path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, backend_dir)

from app.core.domain.models import Handoff, Logger, Product, Shipment, TemperatureReading, ExcursionEvent
from app.core.services.exposure_service import ExposureService
from app.core.services.attribution_service import AttributionService


def generate_validation_scenarios(n_scenarios: int = 25):
    """
    Generate synthetic test scenarios where a thermal excursion is injected
    into a known ground-truth handoff leg across multi-modal custody.
    """
    scenarios = []
    base_time = datetime(2026, 10, 20, 6, 0, 0)
    product = Product(
        product_id=1,
        name="mRNA Vaccine 2C-8C",
        min_temp_c=2.0,
        max_temp_c=8.0,
        allowed_excursion_minutes=120,
        thermal_mass_class="Low",
    )

    handoff_types = ["pickup", "transit", "transfer", "storage", "delivery"]

    for i in range(1, n_scenarios + 1):
        shipment = Shipment(
            shipment_id=i,
            shipment_code=f"VAL-SHP-{i:03d}",
            product_id=product.product_id,
            origin="Plant Alpha",
            destination="Hospital Beta",
            dispatched_at=base_time,
            expected_delivery_at=base_time + timedelta(hours=15),
            status="delivered",
            product=product,
        )

        # 5 Handoffs (3 hours each)
        handoffs = []
        for seq in range(1, 6):
            ws = base_time + timedelta(hours=(seq - 1) * 3)
            we = ws + timedelta(hours=3)
            # Inject slight clock skew on some handoffs
            skew = 15.0 if seq % 2 == 0 else 0.0
            handoffs.append(
                Handoff(
                    handoff_id=i * 100 + seq,
                    shipment_id=shipment.shipment_id,
                    sequence_no=seq,
                    handoff_type=handoff_types[seq - 1],
                    from_party=f"Carrier {seq}",
                    to_party=f"Carrier {seq+1}",
                    location=f"Hub {seq}",
                    window_start_utc=ws,
                    window_end_utc=we,
                    reported_start_utc=ws,
                    reported_end_utc=we,
                    clock_skew_seconds=skew,
                    dwell_minutes=30.0 if seq in [1, 3, 5] else 0.0,
                )
            )

        # Select one ground truth handoff to inject the severe thermal excursion
        gt_index = (i % 5)  # 0 to 4
        gt_handoff = handoffs[gt_index]

        # Injected excursion window
        exc_start = gt_handoff.window_start_utc + timedelta(minutes=30)
        exc_end = gt_handoff.window_end_utc - timedelta(minutes=30)
        duration_m = (exc_end - exc_start).total_seconds() / 60.0

        excursion = ExcursionEvent(
            excursion_id=i,
            shipment_id=shipment.shipment_id,
            started_at_utc=exc_start,
            ended_at_utc=exc_end,
            duration_minutes=duration_m,
            peak_temp_c=15.2,
            severity="critical",
            ground_truth_handoff_id=gt_handoff.handoff_id,
            ground_truth_cause=f"Injected simulation fault in leg {gt_handoff.sequence_no}",
        )

        # Logger
        logger = Logger(
            logger_id=i,
            device_type="TT-ULTRA",
            assigned_shipment_id=shipment.shipment_id,
            sampling_interval_seconds=300,
            clock_skew_seconds=0.0,
            data_quality_flag="good",
        )

        # Readings across 15 hours
        readings = []
        curr = base_time
        rid = 1
        while curr <= base_time + timedelta(hours=15):
            temp = 4.5
            if exc_start <= curr <= exc_end:
                temp = 15.2
            elif i % 3 == 0 and gt_index > 0:
                # Add a brief naive-crossing spike in an earlier leg to test naive vs guard difference
                earlier_h = handoffs[0]
                if earlier_h.window_start_utc + timedelta(minutes=30) <= curr <= earlier_h.window_start_utc + timedelta(minutes=45):
                    temp = 8.3  # slight breach for 15 mins

            readings.append(
                TemperatureReading(
                    reading_id=i * 1000 + rid,
                    logger_id=logger.logger_id,
                    recorded_at_utc=curr,
                    temperature_c=temp,
                    humidity_pct=50.0,
                    battery_pct=95.0,
                    quality_flag="good",
                )
            )
            rid += 1
            curr += timedelta(minutes=5)

        scenarios.append({
            "scenario_id": i,
            "shipment": shipment,
            "product": product,
            "handoffs": handoffs,
            "loggers": [logger],
            "readings_by_logger": {logger.logger_id: readings},
            "excursion": excursion,
            "ground_truth_handoff_id": gt_handoff.handoff_id,
        })

    return scenarios


def run_validation():
    print("=" * 60)
    print("HandoffGuard — Attribution Ground-Truth Validation")
    print("=" * 60)

    exposure_svc = ExposureService()
    attribution_svc = AttributionService(exposure_svc)

    scenarios = generate_validation_scenarios(30)
    print(f"Generated {len(scenarios)} validation scenarios with known ground-truth faults.")

    top_1_hits = 0
    top_3_hits = 0
    total_scenarios = len(scenarios)
    scores = []
    confidence_values = []
    high_conf_hits = 0
    high_conf_total = 0
    low_conf_count = 0
    scenario_results = []

    for sc in scenarios:
        computed_attrs, naive_res, evidence_list = attribution_svc.compute_attribution(
            shipment=sc["shipment"],
            product=sc["product"],
            excursion=sc["excursion"],
            handoffs=sc["handoffs"],
            loggers=sc["loggers"],
            readings_by_logger=sc["readings_by_logger"],
        )

        gt_id = sc["ground_truth_handoff_id"]
        ranked_ids = [attr.handoff_id for attr in computed_attrs]

        top_1_match = len(ranked_ids) > 0 and ranked_ids[0] == gt_id
        top_3_match = gt_id in ranked_ids[:3]

        if top_1_match:
            top_1_hits += 1
        if top_3_match:
            top_3_hits += 1

        top_score = computed_attrs[0].confidence_score if computed_attrs else 0.0
        top_conf = computed_attrs[0].confidence_label if computed_attrs else "low"
        scores.append(top_score)
        confidence_values.append(top_score)

        if top_conf == "high":
            high_conf_total += 1
            if top_1_match:
                high_conf_hits += 1
        elif top_conf == "low":
            low_conf_count += 1

        scenario_results.append({
            "scenario_id": sc["scenario_id"],
            "ground_truth_handoff_id": gt_id,
            "predicted_top_handoff_id": ranked_ids[0] if ranked_ids else None,
            "top_1_match": top_1_match,
            "top_3_match": top_3_match,
            "confidence_score": top_score,
            "confidence_label": top_conf,
            "naive_baseline_agrees": naive_res.agree,
        })

    top_1_accuracy = round((top_1_hits / total_scenarios) * 100.0, 1)
    top_3_accuracy = round((top_3_hits / total_scenarios) * 100.0, 1)
    mean_conf = round(sum(confidence_values) / len(confidence_values), 3) if confidence_values else 0.0
    high_conf_prec = round((high_conf_hits / max(1, high_conf_total)) * 100.0, 1)
    avg_score = round(sum(scores) / len(scores), 3) if scores else 0.0

    print(f"\nValidation Results:")
    print(f"  Top-1 Accuracy          : {top_1_accuracy}% ({top_1_hits}/{total_scenarios})")
    print(f"  Top-3 Accuracy          : {top_3_accuracy}% ({top_3_hits}/{total_scenarios})")
    print(f"  Mean Confidence Score   : {mean_conf}")
    print(f"  High-Confidence Precision: {high_conf_prec}% ({high_conf_hits}/{high_conf_total})")
    print(f"  Average Attribution Score: {avg_score}")

    os.makedirs("reports", exist_ok=True)
    report_path = os.path.join("reports", "attribution_validation.json")

    report_payload = {
        "benchmark_date": datetime.now(timezone.utc).isoformat(),
        "total_validation_scenarios": total_scenarios,
        "metrics": {
            "top_1_accuracy_pct": top_1_accuracy,
            "top_3_accuracy_pct": top_3_accuracy,
            "mean_confidence_score": mean_conf,
            "high_confidence_precision_pct": high_conf_prec,
            "low_confidence_recall_pct": round((low_conf_count / max(1, total_scenarios)) * 100.0, 1),
            "average_attribution_score": avg_score,
        },
        "system_specs": {
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "cpu_count": os.cpu_count(),
        },
        "scenarios": scenario_results,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    print(f"\nSaved validation report to {report_path}")
    return report_payload


if __name__ == "__main__":
    run_validation()
