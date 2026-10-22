"""
PreventionService — rule-based risk evaluation and proactive suggestions.

Generates prototype recommendations for upcoming shipments using deterministic rules.
Clearly flagged as a prototype advisory system.
"""

from __future__ import annotations

from typing import Optional

from app.core.domain.models import (
    Handoff,
    Logger,
    PreventionSuggestion,
    Product,
    Shipment,
)

PROTOTYPE_DISCLAIMER: str = (
    "Prototype suggestion based on synthetic historical patterns. "
    "Not an operational or legal recommendation."
)


class PreventionService:
    """Evaluates upcoming handoff risk and generates rule-based mitigations."""

    def evaluate_shipment_risk(
        self,
        shipment: Shipment,
        product: Product,
        handoffs: list[Handoff],
        loggers: list[Logger],
    ) -> tuple[Handoff, PreventionSuggestion]:
        """
        Evaluate risks across upcoming handoffs for a shipment and return the riskiest
        handoff along with a rule-based prevention suggestion.
        """
        if not handoffs:
            dummy_handoff = Handoff(
                handoff_id=0,
                shipment_id=shipment.shipment_id,
                sequence_no=1,
                handoff_type="transfer",
                from_party="Unknown",
                to_party="Unknown",
                location="Unknown",
                window_start_utc=shipment.dispatched_at,
                window_end_utc=shipment.expected_delivery_at,
                reported_start_utc=None,
                reported_end_utc=None,
                clock_skew_seconds=0,
                dwell_minutes=0,
            )
            return dummy_handoff, PreventionSuggestion(
                shipment_id=shipment.shipment_id,
                handoff_id=0,
                risk_score=0.1,
                suggestion="No handoffs scheduled; maintain standard cold-chain handling.",
                rationale="Shipment has no granular custody segments registered.",
                prototype_flag=True,
            )

        # Rule evaluation scores per handoff
        highest_score = -1.0
        riskiest_handoff = handoffs[0]
        selected_suggestion = ""
        selected_rationale = ""

        has_skew_issue = any(abs(lg.clock_skew_seconds) > 180 for lg in loggers)
        has_quality_issue = any(lg.data_quality_flag != "good" for lg in loggers)

        for h in handoffs:
            score = 0.2  # baseline
            suggestion_parts = []
            rationale_parts = []

            # Rule 1: Extended Dwell or Transfer Docks
            if h.dwell_minutes > 45 or "dock" in h.location.lower() or "cross-dock" in h.location.lower() or h.handoff_type.lower() == "storage":
                dock_score = 0.35 + min(0.4, (h.dwell_minutes / 120.0) * 0.3)
                score += dock_score
                suggestion_parts.append(
                    "Require pre-cooled staging lane and limit ambient dock dwell time to < 20 minutes."
                )
                rationale_parts.append(
                    f"Cross-docking and warehouse apron handoffs historically exhibit ambient heat infiltration during dwell ({int(h.dwell_minutes)}m scheduled at {h.location})."
                )

            # Rule 2: Last-Mile Delivery (bike, van, local agent)
            if (
                "bike" in h.handoff_type.lower()
                or "local agent" in h.to_party.lower()
                or "courier" in h.from_party.lower()
                or h.sequence_no == len(handoffs)
            ):
                score += 0.3
                suggestion_parts.append(
                    "Deploy validated VIP (Vacuum Insulated Panel) thermal shippers and schedule early morning dispatch."
                )
                rationale_parts.append(
                    f"Final distribution step ({h.from_party} → {h.to_party}) is highly susceptible to unconditioned ambient exposure."
                )

            # Rule 3: Product sensitivity (thermal mass and tight limits)
            if product.max_temp_c <= 8.0 and product.min_temp_c >= 2.0:
                score += 0.15
                if product.thermal_mass_class.lower() == "low":
                    score += 0.1
                    suggestion_parts.append(
                        "Add PCM (Phase Change Material) buffer packs to counteract rapid warming of low-thermal-mass payload."
                    )
                    rationale_parts.append(
                        f"Product '{product.name}' has low thermal mass and strict 2°C–8°C parameters."
                    )

            # Rule 4: Device / Clock Skew or Data Quality
            if has_skew_issue or has_quality_issue:
                score += 0.1
                suggestion_parts.append(
                    "Perform logger NFC/Bluetooth time-synchronization and verify battery level before handoff."
                )
                rationale_parts.append(
                    "One or more loggers show clock skew or non-optimal data quality flags."
                )

            score = min(0.95, round(score, 2))

            if score > highest_score:
                highest_score = score
                riskiest_handoff = h
                selected_suggestion = (
                    " ".join(suggestion_parts)
                    if suggestion_parts
                    else "Maintain standard verified reefer protocol with dual-probe temperature logging."
                )
                selected_rationale = (
                    " ".join(rationale_parts)
                    if rationale_parts
                    else f"Standard transfer window at {h.location}."
                )

        suggestion = PreventionSuggestion(
            shipment_id=shipment.shipment_id,
            handoff_id=riskiest_handoff.handoff_id,
            risk_score=highest_score,
            suggestion=selected_suggestion,
            rationale=selected_rationale,
            prototype_flag=True,
        )

        return riskiest_handoff, suggestion
