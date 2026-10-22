"""
Synthetic Seed Data Loader for HandoffGuard.

Creates sample pharmaceutical products, shipments, handoffs, loggers,
temperature readings, and excursion events that exercise all edge cases:
1. Multi-logger shipments with overlapping handoff windows
2. Clock-skewed loggers requiring alignment
3. Missing readings creating timeline data gaps
4. Multiple excursion events on a single shipment
5. Scenario where naive baseline differs from HandoffGuard attribution
6. Minimum 5 handoffs per shipment across multi-modal custody
7. In-transit shipments for prevention evaluation
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_backend
from app.infrastructure.db.dev_db import (
    AttributionResultORM,
    DevDatabaseBackend,
    ExcursionEventORM,
    HandoffORM,
    LoggerORM,
    PreventionSuggestionORM,
    ProductORM,
    ShipmentORM,
    TemperatureReadingORM,
)


async def seed():
    """Populates the database with realistic synthetic test datasets."""
    backend = get_db_backend()
    if not isinstance(backend, DevDatabaseBackend):
        print("Seed script is currently configured for DevDatabaseBackend.")
        return

    await backend.create_tables()

    async with backend.get_session() as session:
        # Clear existing data in reverse FK order
        print("Clearing existing records...")
        await session.execute(delete(PreventionSuggestionORM))
        await session.execute(delete(AttributionResultORM))
        await session.execute(delete(TemperatureReadingORM))
        await session.execute(delete(ExcursionEventORM))
        await session.execute(delete(LoggerORM))
        await session.execute(delete(HandoffORM))
        await session.execute(delete(ShipmentORM))
        await session.execute(delete(ProductORM))
        await session.flush()

        print("Seeding products...")
        vaccine = ProductORM(
            name="VaxPro mRNA Booster (2C - 8C)",
            min_temp_c=2.0,
            max_temp_c=8.0,
            allowed_excursion_minutes=120,
            thermal_mass_class="Low",
        )
        blood = ProductORM(
            name="CryoPlasma Fresh Frozen (-20C to -15C)",
            min_temp_c=-20.0,
            max_temp_c=-15.0,
            allowed_excursion_minutes=60,
            thermal_mass_class="Medium",
        )
        insulin = ProductORM(
            name="NovoInsulin Glargine (2C - 8C)",
            min_temp_c=2.0,
            max_temp_c=8.0,
            allowed_excursion_minutes=180,
            thermal_mass_class="Low",
        )
        session.add_all([vaccine, blood, insulin])
        await session.flush()

        # Base time: 2026-10-20 06:00:00 UTC
        base_t = datetime(2026, 10, 20, 6, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)

        print("Seeding shipments & handoffs...")

        # -------------------------------------------------------------
        # Shipment 1: SHP-2026-0881 — mRNA Vaccine with Excursion
        # Edge cases: 2 loggers, overlapping handoffs, clock skew (+180s on logger 2),
        # data gap during handoff 3, and Naive Baseline DIFFERENCE!
        # Naive: Handoff 2 crossed 8.1°C briefly for 10 mins.
        # HandoffGuard: Handoff 4 (dock dwell) had massive 14.5°C exposure for 60 mins.
        # -------------------------------------------------------------
        shp1 = ShipmentORM(
            shipment_code="SHP-2026-0881",
            product_id=vaccine.product_id,
            origin="Hyderabad Pharma Hub",
            destination="Bengaluru Apollo Hospital",
            dispatched_at=base_t,
            expected_delivery_at=base_t + timedelta(hours=14),
            status="delivered",
        )
        session.add(shp1)
        await session.flush()

        # 5 Handoffs for Shipment 1
        h1_1 = HandoffORM(
            shipment_id=shp1.shipment_id,
            sequence_no=1,
            handoff_type="pickup",
            from_party="Pharma Hub Warehouse",
            to_party="ColdFleet Reefer Truck A1",
            location="Hyderabad Logistics Park",
            window_start_utc=base_t,
            window_end_utc=base_t + timedelta(hours=2),
            reported_start_utc=base_t + timedelta(minutes=5),
            reported_end_utc=base_t + timedelta(hours=1, minutes=55),
            clock_skew_seconds=0,
            dwell_minutes=25,
        )
        h1_2 = HandoffORM(
            shipment_id=shp1.shipment_id,
            sequence_no=2,
            handoff_type="transit",
            from_party="ColdFleet Reefer Truck A1",
            to_party="Central Cross-Dock",
            location="NH-44 Highway Transit",
            window_start_utc=base_t + timedelta(hours=2),
            window_end_utc=base_t + timedelta(hours=5),
            reported_start_utc=base_t + timedelta(hours=2),
            reported_end_utc=base_t + timedelta(hours=5),
            clock_skew_seconds=15,
            dwell_minutes=0,
        )
        # H1_3 overlaps with H1_2 by 15 minutes!
        h1_3 = HandoffORM(
            shipment_id=shp1.shipment_id,
            sequence_no=3,
            handoff_type="transfer",
            from_party="Central Cross-Dock",
            to_party="Kurnool Hub Staging",
            location="Kurnool Airport Terminal",
            window_start_utc=base_t + timedelta(hours=4, minutes=45),
            window_end_utc=base_t + timedelta(hours=7),
            reported_start_utc=base_t + timedelta(hours=4, minutes=50),
            reported_end_utc=base_t + timedelta(hours=6, minutes=50),
            clock_skew_seconds=0,
            dwell_minutes=40,
        )
        h1_4 = HandoffORM(
            shipment_id=shp1.shipment_id,
            sequence_no=4,
            handoff_type="storage",
            from_party="Kurnool Hub Staging",
            to_party="Express Van Route 9",
            location="Bengaluru Urban Depot Dock",
            window_start_utc=base_t + timedelta(hours=7),
            window_end_utc=base_t + timedelta(hours=11),
            reported_start_utc=base_t + timedelta(hours=7, minutes=10),
            reported_end_utc=base_t + timedelta(hours=10, minutes=55),
            clock_skew_seconds=-30,
            dwell_minutes=85,  # Extended dock dwell
        )
        h1_5 = HandoffORM(
            shipment_id=shp1.shipment_id,
            sequence_no=5,
            handoff_type="delivery",
            from_party="Express Van Route 9",
            to_party="Apollo Hospital Pharmacy",
            location="Bengaluru Bannerghatta",
            window_start_utc=base_t + timedelta(hours=11),
            window_end_utc=base_t + timedelta(hours=14),
            reported_start_utc=base_t + timedelta(hours=11, minutes=5),
            reported_end_utc=base_t + timedelta(hours=13, minutes=45),
            clock_skew_seconds=0,
            dwell_minutes=20,
        )
        session.add_all([h1_1, h1_2, h1_3, h1_4, h1_5])
        await session.flush()

        # Loggers for Shipment 1: 2 loggers
        lg1_1 = LoggerORM(
            device_type="TempTale Ultra Ble",
            assigned_shipment_id=shp1.shipment_id,
            sampling_interval_seconds=300,  # 5 min
            clock_skew_seconds=0,
            data_quality_flag="good",
        )
        lg1_2 = LoggerORM(
            device_type="Sensitech ColdStream",
            assigned_shipment_id=shp1.shipment_id,
            sampling_interval_seconds=300,  # 5 min
            clock_skew_seconds=180,  # +3 min skew
            data_quality_flag="good",
        )
        session.add_all([lg1_1, lg1_2])
        await session.flush()

        # Generate temperature readings for Shipment 1 (14 hours, every 5 min = 168 readings per logger)
        print("Generating readings for shipment 1...")
        curr_t = base_t
        end_t = base_t + timedelta(hours=14)
        readings_to_add = []

        while curr_t <= end_t:
            hours_from_start = (curr_t - base_t).total_seconds() / 3600.0

            # Default safe temp 4.5°C
            temp1 = 4.5
            temp2 = 4.7

            # During handoff 2 (hours 3.0 to 3.3): brief threshold breach to 8.4°C (naive baseline trigger)
            if 3.0 <= hours_from_start <= 3.3:
                temp1 = 8.4
                temp2 = 8.5
            # During handoff 4 (hours 8.0 to 10.0): severe excursion to 14.8°C!
            elif 8.0 <= hours_from_start <= 10.0:
                temp1 = 14.2 + (0.6 if hours_from_start > 8.5 else 0.0)
                temp2 = 14.5 + (0.5 if hours_from_start > 8.5 else 0.0)
            elif 10.0 < hours_from_start <= 10.8:
                # Cooling down back to safe
                temp1 = 10.5 - (hours_from_start - 10.0) * 5.0
                temp2 = 10.7 - (hours_from_start - 10.0) * 5.0

            # Data gap in logger 1 between hours 5.2 and 6.5
            is_gap = 5.2 <= hours_from_start <= 6.5
            if not is_gap:
                readings_to_add.append(
                    TemperatureReadingORM(
                        logger_id=lg1_1.logger_id,
                        recorded_at_utc=curr_t,
                        temperature_c=round(temp1, 2),
                        humidity_pct=52.0,
                        battery_pct=94.0,
                        quality_flag="good",
                    )
                )

            # Logger 2 has raw recorded_at_utc without the 180s skew (it is skewed in device clock)
            # Its clock is 180s ahead, so recorded_at_utc = curr_t - 180s
            readings_to_add.append(
                TemperatureReadingORM(
                    logger_id=lg1_2.logger_id,
                    recorded_at_utc=curr_t - timedelta(seconds=lg1_2.clock_skew_seconds),
                    temperature_c=round(temp2, 2),
                    humidity_pct=54.0,
                    battery_pct=88.0,
                    quality_flag="good",
                )
            )

            curr_t += timedelta(minutes=5)

        session.add_all(readings_to_add)
        await session.flush()

        # Excursion event for Shipment 1
        exc1 = ExcursionEventORM(
            shipment_id=shp1.shipment_id,
            started_at_utc=base_t + timedelta(hours=3),
            ended_at_utc=base_t + timedelta(hours=10, minutes=45),
            duration_minutes=140.0,
            peak_temp_c=14.8,
            severity="critical",
            ground_truth_handoff_id=h1_4.handoff_id,
            ground_truth_cause="Reefer truck refrigeration unit shut down on depot apron during shift turnover.",
        )
        session.add(exc1)
        await session.flush()

        # -------------------------------------------------------------
        # Shipment 2: SHP-2026-0904 — CryoPlasma (Blood Product)
        # Multiple excursions (two distinct events), normal baseline agreement
        # -------------------------------------------------------------
        shp2 = ShipmentORM(
            shipment_code="SHP-2026-0904",
            product_id=blood.product_id,
            origin="Mumbai Blood Bank Central",
            destination="Pune Ruby Hall Clinic",
            dispatched_at=base_t + timedelta(days=1),
            expected_delivery_at=base_t + timedelta(days=1, hours=8),
            status="delivered",
        )
        session.add(shp2)
        await session.flush()

        base_t2 = base_t + timedelta(days=1)
        h2_1 = HandoffORM(
            shipment_id=shp2.shipment_id,
            sequence_no=1,
            handoff_type="pickup",
            from_party="Mumbai Blood Bank",
            to_party="CryoExpress Logistics",
            location="Parel Central Mumbai",
            window_start_utc=base_t2,
            window_end_utc=base_t2 + timedelta(hours=1, minutes=30),
            clock_skew_seconds=0,
            dwell_minutes=15,
        )
        h2_2 = HandoffORM(
            shipment_id=shp2.shipment_id,
            sequence_no=2,
            handoff_type="transit",
            from_party="CryoExpress Logistics",
            to_party="Expressway Checkpost",
            location="Mumbai-Pune Expressway",
            window_start_utc=base_t2 + timedelta(hours=1, minutes=30),
            window_end_utc=base_t2 + timedelta(hours=4),
            clock_skew_seconds=0,
            dwell_minutes=0,
        )
        h2_3 = HandoffORM(
            shipment_id=shp2.shipment_id,
            sequence_no=3,
            handoff_type="transfer",
            from_party="Expressway Checkpost",
            to_party="Pune City Feeder",
            location="Toll Plaza Intermediate Dock",
            window_start_utc=base_t2 + timedelta(hours=4),
            window_end_utc=base_t2 + timedelta(hours=5),
            clock_skew_seconds=0,
            dwell_minutes=30,
        )
        h2_4 = HandoffORM(
            shipment_id=shp2.shipment_id,
            sequence_no=4,
            handoff_type="delivery",
            from_party="Pune City Feeder",
            to_party="Ruby Hall Transfusion Center",
            location="Pune Dhole Patil Rd",
            window_start_utc=base_t2 + timedelta(hours=5),
            window_end_utc=base_t2 + timedelta(hours=7),
            clock_skew_seconds=0,
            dwell_minutes=15,
        )
        h2_5 = HandoffORM(
            shipment_id=shp2.shipment_id,
            sequence_no=5,
            handoff_type="storage",
            from_party="Ruby Hall Transfusion Center",
            to_party="Hospital Deep-Freeze",
            location="Hospital Basement Vault",
            window_start_utc=base_t2 + timedelta(hours=7),
            window_end_utc=base_t2 + timedelta(hours=8),
            clock_skew_seconds=0,
            dwell_minutes=10,
        )
        session.add_all([h2_1, h2_2, h2_3, h2_4, h2_5])
        await session.flush()

        lg2 = LoggerORM(
            device_type="CryoTag Ultra",
            assigned_shipment_id=shp2.shipment_id,
            sampling_interval_seconds=300,
            clock_skew_seconds=0,
            data_quality_flag="good",
        )
        session.add(lg2)
        await session.flush()

        # Readings for Shipment 2: Two separate warming spikes above -15°C
        curr_t = base_t2
        end_t = base_t2 + timedelta(hours=8)
        readings_shp2 = []
        while curr_t <= end_t:
            hours = (curr_t - base_t2).total_seconds() / 3600.0
            temp = -18.5
            if 2.0 <= hours <= 2.8:
                temp = -12.0  # Excursion 1
            elif 4.2 <= hours <= 4.7:
                temp = -11.5  # Excursion 2
            readings_shp2.append(
                TemperatureReadingORM(
                    logger_id=lg2.logger_id,
                    recorded_at_utc=curr_t,
                    temperature_c=temp,
                    humidity_pct=None,
                    battery_pct=98.0,
                    quality_flag="good",
                )
            )
            curr_t += timedelta(minutes=5)
        session.add_all(readings_shp2)
        await session.flush()

        # Two Excursion Events for Shipment 2
        exc2_1 = ExcursionEventORM(
            shipment_id=shp2.shipment_id,
            started_at_utc=base_t2 + timedelta(hours=2),
            ended_at_utc=base_t2 + timedelta(hours=2, minutes=48),
            duration_minutes=48.0,
            peak_temp_c=-12.0,
            severity="medium",
            ground_truth_handoff_id=h2_2.handoff_id,
            ground_truth_cause="Dry ice sublimation accelerated due to compromised secondary seal.",
        )
        exc2_2 = ExcursionEventORM(
            shipment_id=shp2.shipment_id,
            started_at_utc=base_t2 + timedelta(hours=4, minutes=12),
            ended_at_utc=base_t2 + timedelta(hours=4, minutes=42),
            duration_minutes=30.0,
            peak_temp_c=-11.5,
            severity="medium",
            ground_truth_handoff_id=h2_3.handoff_id,
            ground_truth_cause="Uninsulated transfer on open dock during vehicle change.",
        )
        session.add_all([exc2_1, exc2_2])
        await session.flush()

        # -------------------------------------------------------------
        # Shipment 3: SHP-2026-1042 — Upcoming In-Transit Shipment (for Prevention Screen)
        # Status = "in_transit"
        # -------------------------------------------------------------
        shp3 = ShipmentORM(
            shipment_code="SHP-2026-1042",
            product_id=insulin.product_id,
            origin="Ahmedabad Manufacturing SEZ",
            destination="Jaipur SMS Medical College",
            dispatched_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2),
            expected_delivery_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=10),
            status="in_transit",
        )
        session.add(shp3)
        await session.flush()

        now_t = datetime.now(timezone.utc).replace(tzinfo=None)
        h3_1 = HandoffORM(
            shipment_id=shp3.shipment_id,
            sequence_no=1,
            handoff_type="pickup",
            from_party="Ahmedabad SEZ Plant",
            to_party="NorthLine Express Truck 4",
            location="Ahmedabad Cargo Terminal",
            window_start_utc=now_t - timedelta(hours=2),
            window_end_utc=now_t - timedelta(hours=1),
            clock_skew_seconds=0,
            dwell_minutes=20,
        )
        h3_2 = HandoffORM(
            shipment_id=shp3.shipment_id,
            sequence_no=2,
            handoff_type="transit",
            from_party="NorthLine Express Truck 4",
            to_party="Udaipur Cross-Dock",
            location="Rajasthan Corridor",
            window_start_utc=now_t - timedelta(hours=1),
            window_end_utc=now_t + timedelta(hours=3),
            clock_skew_seconds=0,
            dwell_minutes=0,
        )
        h3_3 = HandoffORM(
            shipment_id=shp3.shipment_id,
            sequence_no=3,
            handoff_type="storage",
            from_party="Udaipur Cross-Dock",
            to_party="Jaipur Route Van",
            location="Udaipur Distribution Center Apron",
            window_start_utc=now_t + timedelta(hours=3),
            window_end_utc=now_t + timedelta(hours=5),
            clock_skew_seconds=0,
            dwell_minutes=75,  # High risk dock dwell!
        )
        h3_4 = HandoffORM(
            shipment_id=shp3.shipment_id,
            sequence_no=4,
            handoff_type="transit",
            from_party="Jaipur Route Van",
            to_party="Jaipur City Hub",
            location="Jaipur Bypass",
            window_start_utc=now_t + timedelta(hours=5),
            window_end_utc=now_t + timedelta(hours=8),
            clock_skew_seconds=0,
            dwell_minutes=0,
        )
        h3_5 = HandoffORM(
            shipment_id=shp3.shipment_id,
            sequence_no=5,
            handoff_type="delivery",
            from_party="Jaipur City Hub",
            to_party="SMS Medical College Pharmacy",
            location="Jaipur Central",
            window_start_utc=now_t + timedelta(hours=8),
            window_end_utc=now_t + timedelta(hours=10),
            clock_skew_seconds=0,
            dwell_minutes=15,
        )
        session.add_all([h3_1, h3_2, h3_3, h3_4, h3_5])
        await session.flush()

        lg3 = LoggerORM(
            device_type="TempTale GEO LTE",
            assigned_shipment_id=shp3.shipment_id,
            sampling_interval_seconds=300,
            clock_skew_seconds=45,
            data_quality_flag="good",
        )
        session.add(lg3)
        await session.flush()

        # Add ongoing readings for shipment 3 (all safe so far)
        curr_t = now_t - timedelta(hours=2)
        while curr_t <= now_t:
            session.add(
                TemperatureReadingORM(
                    logger_id=lg3.logger_id,
                    recorded_at_utc=curr_t,
                    temperature_c=4.8,
                    humidity_pct=48.0,
                    battery_pct=99.0,
                    quality_flag="good",
                )
            )
            curr_t += timedelta(minutes=5)

        await session.commit()
        print("Seed data successfully inserted!")


if __name__ == "__main__":
    asyncio.run(seed())
