"""
HandoffGuard Exasol SQL Integration Test Suite
Executes isolated tests in schema HANDOFFGUARD_TEST.
Does NOT modify or touch HANDOFFGUARD demo data.
Exits with code 0 on success, 1 on failure.
"""

import sys
import ssl
import pyexasol

def main():
    print("=" * 72)
    print("STARTING EXASOL SQL INTEGRATION TESTS (Schema: HANDOFFGUARD_TEST)")
    print("=" * 72)

    c = pyexasol.connect(
        dsn="localhost:8563",
        user="sys",
        password="exasol",
        encryption=True,
        fetch_dict=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
    )

    # 1. Setup isolated test schema
    c.execute("CREATE SCHEMA IF NOT EXISTS HANDOFFGUARD_TEST")
    c.execute("OPEN SCHEMA HANDOFFGUARD_TEST")

    # 2. Create isolated tables
    c.execute("""
    CREATE OR REPLACE TABLE PRODUCTS (
        ID VARCHAR(36) PRIMARY KEY,
        NAME VARCHAR(120),
        MIN_TEMP_C DECIMAL(5,2),
        MAX_TEMP_C DECIMAL(5,2),
        MAX_EXCURSION_MINUTES DECIMAL(18,0)
    )
    """)

    c.execute("""
    CREATE OR REPLACE TABLE SHIPMENTS (
        ID VARCHAR(36) PRIMARY KEY,
        SHIPMENT_CODE VARCHAR(30),
        PRODUCT_ID VARCHAR(36)
    )
    """)

    c.execute("""
    CREATE OR REPLACE TABLE LOGGER_DEVICES (
        LOGGER_ID VARCHAR(50) PRIMARY KEY,
        DEVICE_CODE VARCHAR(50),
        ASSIGNED_SHIPMENT_ID VARCHAR(36),
        CLOCK_SKEW_SECONDS DECIMAL(18,0)
    )
    """)

    c.execute("""
    CREATE OR REPLACE TABLE LOGGER_READINGS (
        READING_ID VARCHAR(50) PRIMARY KEY,
        LOGGER_ID VARCHAR(50),
        READING_AT_UTC TIMESTAMP(3),
        TEMPERATURE_C DOUBLE,
        BATTERY_PCT DOUBLE
    )
    """)

    c.execute("""
    CREATE OR REPLACE TABLE HANDOFFS (
        ID VARCHAR(36) PRIMARY KEY,
        SHIPMENT_ID VARCHAR(36),
        SEQUENCE_NUMBER DECIMAL(18,0),
        HANDOFF_TYPE VARCHAR(40),
        FROM_PARTY VARCHAR(120),
        TO_PARTY VARCHAR(120),
        LOCATION VARCHAR(150),
        PLANNED_START_AT TIMESTAMP(3),
        ACTUAL_START_AT TIMESTAMP(3),
        PLANNED_END_AT TIMESTAMP(3),
        ACTUAL_END_AT TIMESTAMP(3)
    )
    """)

    c.execute("""
    CREATE OR REPLACE TABLE EXCURSIONS (
        EXCURSION_ID VARCHAR(50) PRIMARY KEY,
        SHIPMENT_ID VARCHAR(50),
        PRODUCT_ID VARCHAR(50),
        STARTED_AT_UTC TIMESTAMP(3),
        ENDED_AT_UTC TIMESTAMP(3),
        MIN_TEMP_C DOUBLE,
        MAX_TEMP_C DOUBLE,
        DETECTED_BY VARCHAR(100)
    )
    """)

    # 3. Create Repaired Views in HANDOFFGUARD_TEST

    # View 1: V_READING_HANDOFF_MEMBERSHIP
    c.execute("""
    CREATE OR REPLACE VIEW V_READING_HANDOFF_MEMBERSHIP AS
    WITH corrected AS (
        SELECT 
            r.reading_id,
            r.logger_id,
            r.reading_at_utc,
            ADD_SECONDS(r.reading_at_utc, -COALESCE(ld.clock_skew_seconds, 0)) AS corrected_at_utc,
            r.temperature_c,
            r.battery_pct,
            ld.assigned_shipment_id AS shipment_id,
            COALESCE(ld.clock_skew_seconds, 0) AS clock_skew_seconds
        FROM logger_readings r
        JOIN logger_devices ld ON r.logger_id = ld.logger_id
    ),
    matched_readings AS (
        SELECT
            c.reading_id,
            c.logger_id,
            c.reading_at_utc,
            c.corrected_at_utc,
            c.temperature_c,
            c.battery_pct,
            c.shipment_id,
            c.clock_skew_seconds,
            h.id AS handoff_id,
            h.sequence_number AS sequence_no,
            h.handoff_type,
            h.from_party,
            h.to_party,
            h.actual_start_at,
            h.actual_end_at,
            CASE 
                WHEN h.actual_start_at IS NOT NULL AND h.actual_end_at IS NOT NULL THEN 'ACTUAL'
                WHEN h.planned_start_at IS NOT NULL THEN 'PLANNED_ONLY'
                ELSE 'UNKNOWN'
            END AS window_source
        FROM corrected c
        LEFT JOIN handoffs h 
            ON c.shipment_id = h.shipment_id
           AND h.actual_start_at IS NOT NULL 
           AND h.actual_end_at IS NOT NULL
           AND c.corrected_at_utc >= h.actual_start_at
           AND c.corrected_at_utc < h.actual_end_at
    ),
    counts AS (
        SELECT 
            m.*,
            COUNT(m.handoff_id) OVER (PARTITION BY m.reading_id) AS candidate_count
        FROM matched_readings m
    )
    SELECT 
        reading_id,
        logger_id,
        reading_at_utc,
        corrected_at_utc,
        temperature_c,
        battery_pct,
        shipment_id,
        handoff_id,
        sequence_no,
        handoff_type,
        from_party,
        to_party,
        actual_start_at AS window_start_utc,
        actual_end_at AS window_end_utc,
        window_source,
        clock_skew_seconds,
        candidate_count,
        CASE 
            WHEN candidate_count = 0 THEN 'UNMATCHED'
            WHEN candidate_count = 1 THEN 'MATCHED'
            ELSE 'AMBIGUOUS'
        END AS membership_status,
        CASE WHEN candidate_count > 1 THEN TRUE ELSE FALSE END AS ambiguity_flag
    FROM counts
    """)

    # View 2: V_HANDOFF_THERMAL_EXPOSURE
    # Default prototype gap: 600s
    c.execute("""
    CREATE OR REPLACE VIEW V_HANDOFF_THERMAL_EXPOSURE AS
    WITH logger_counts AS (
        SELECT 
            assigned_shipment_id AS shipment_id,
            COUNT(DISTINCT logger_id) AS assigned_logger_count
        FROM logger_devices
        GROUP BY assigned_shipment_id
    ),
    handoff_conflicts AS (
        SELECT 
            h1.id AS handoff_id,
            h2.id AS other_handoff_id,
            GREATEST(h1.actual_start_at, h2.actual_start_at) AS conflict_start,
            LEAST(h1.actual_end_at, h2.actual_end_at) AS conflict_end
        FROM handoffs h1
        JOIN handoffs h2 
          ON h1.shipment_id = h2.shipment_id
         AND h1.id != h2.id
         AND h1.actual_start_at IS NOT NULL
         AND h1.actual_end_at IS NOT NULL
         AND h2.actual_start_at IS NOT NULL
         AND h2.actual_end_at IS NOT NULL
         AND h1.actual_start_at < h2.actual_end_at
         AND h1.actual_end_at > h2.actual_start_at
    ),
    corrected AS (
        SELECT 
            r.reading_id,
            r.logger_id,
            r.reading_at_utc,
            ADD_SECONDS(r.reading_at_utc, -COALESCE(ld.clock_skew_seconds, 0)) AS corrected_at_utc,
            r.temperature_c,
            r.battery_pct,
            ld.assigned_shipment_id AS shipment_id,
            COALESCE(ld.clock_skew_seconds, 0) AS clock_skew_seconds
        FROM logger_readings r
        JOIN logger_devices ld ON r.logger_id = ld.logger_id
    ),
    segments AS (
        SELECT 
            c.reading_id,
            c.logger_id,
            c.shipment_id,
            c.reading_at_utc,
            c.corrected_at_utc AS segment_start,
            LEAD(c.corrected_at_utc) OVER (
                PARTITION BY c.logger_id 
                ORDER BY c.corrected_at_utc, c.reading_id
            ) AS segment_end,
            c.temperature_c,
            c.clock_skew_seconds
        FROM corrected c
    ),
    supported_segments AS (
        SELECT 
            s.*,
            SECONDS_BETWEEN(s.segment_end, s.segment_start) AS duration_seconds,
            CASE 
                WHEN s.segment_end IS NOT NULL 
                 AND SECONDS_BETWEEN(s.segment_end, s.segment_start) > 0 
                 AND SECONDS_BETWEEN(s.segment_end, s.segment_start) <= 600 
                THEN TRUE 
                ELSE FALSE 
            END AS is_supported
        FROM segments s
    ),
    handoff_overlaps AS (
        SELECT 
            h.id AS handoff_id,
            h.shipment_id,
            h.sequence_number AS sequence_no,
            h.handoff_type,
            h.from_party,
            h.to_party,
            h.location,
            h.actual_start_at AS window_start_utc,
            h.actual_end_at AS window_end_utc,
            CASE 
                WHEN h.actual_start_at IS NOT NULL AND h.actual_end_at IS NOT NULL THEN 'ACTUAL'
                ELSE 'PLANNED_ONLY'
            END AS window_source,
            p.min_temp_c,
            p.max_temp_c,
            ss.reading_id,
            ss.temperature_c,
            ss.is_supported,
            GREATEST(ss.segment_start, h.actual_start_at) AS overlap_start,
            LEAST(ss.segment_end, h.actual_end_at) AS overlap_end
        FROM handoffs h
        JOIN shipments sh ON h.shipment_id = sh.id
        JOIN products p ON sh.product_id = p.id
        LEFT JOIN supported_segments ss
            ON h.shipment_id = ss.shipment_id
           AND ss.is_supported = TRUE
           AND h.actual_start_at IS NOT NULL
           AND h.actual_end_at IS NOT NULL
           AND ss.segment_start < h.actual_end_at
           AND ss.segment_end > h.actual_start_at
    ),
    overlap_annotated AS (
        SELECT 
            ho.*,
            CASE 
                WHEN hc.handoff_id IS NOT NULL THEN TRUE 
                ELSE FALSE 
            END AS is_ambiguous_overlap
        FROM handoff_overlaps ho
        LEFT JOIN handoff_conflicts hc
            ON ho.handoff_id = hc.handoff_id
           AND ho.overlap_start < hc.conflict_end
           AND ho.overlap_end > hc.conflict_start
    ),
    exposure_calcs AS (
        SELECT 
            oa.*,
            CASE 
                WHEN oa.reading_id IS NOT NULL 
                 AND oa.overlap_end > oa.overlap_start
                 AND oa.is_ambiguous_overlap = FALSE
                THEN SECONDS_BETWEEN(oa.overlap_end, oa.overlap_start) / 60.0
                ELSE 0.0
            END AS supported_overlap_minutes,
            CASE 
                WHEN oa.reading_id IS NOT NULL 
                 AND oa.overlap_end > oa.overlap_start
                 AND oa.is_ambiguous_overlap = TRUE
                THEN SECONDS_BETWEEN(oa.overlap_end, oa.overlap_start) / 60.0
                ELSE 0.0
            END AS ambiguous_overlap_minutes,
            CASE 
                WHEN oa.reading_id IS NOT NULL 
                 AND oa.overlap_end > oa.overlap_start
                 AND oa.is_ambiguous_overlap = FALSE
                 AND oa.temperature_c > oa.max_temp_c
                THEN (oa.temperature_c - oa.max_temp_c) * (SECONDS_BETWEEN(oa.overlap_end, oa.overlap_start) / 60.0)
                ELSE 0.0
            END AS above_dm,
            CASE 
                WHEN oa.reading_id IS NOT NULL 
                 AND oa.overlap_end > oa.overlap_start
                 AND oa.is_ambiguous_overlap = FALSE
                 AND oa.temperature_c < oa.min_temp_c
                THEN (oa.min_temp_c - oa.temperature_c) * (SECONDS_BETWEEN(oa.overlap_end, oa.overlap_start) / 60.0)
                ELSE 0.0
            END AS below_dm
        FROM overlap_annotated oa
    )
    SELECT 
        ec.handoff_id,
        ec.shipment_id,
        ec.sequence_no,
        ec.handoff_type,
        ec.from_party,
        ec.to_party,
        ec.location,
        ec.window_source,
        ec.window_start_utc,
        ec.window_end_utc,
        COALESCE(lc.assigned_logger_count, 0) AS assigned_logger_count,
        CASE 
            WHEN ec.window_source = 'ACTUAL'
            THEN SECONDS_BETWEEN(ec.window_end_utc, ec.window_start_utc) / 60.0 
            ELSE 0.0 
        END AS custody_duration_minutes,
        COUNT(DISTINCT ec.reading_id) AS reading_count,
        ROUND(SUM(ec.supported_overlap_minutes), 2) AS supported_observation_minutes,
        ROUND(SUM(ec.ambiguous_overlap_minutes), 2) AS ambiguous_minutes,
        ROUND(GREATEST(0.0, 
            (CASE WHEN ec.window_source = 'ACTUAL' THEN SECONDS_BETWEEN(ec.window_end_utc, ec.window_start_utc) / 60.0 ELSE 0.0 END) 
            - SUM(ec.supported_overlap_minutes) 
            - SUM(ec.ambiguous_overlap_minutes)
        ), 2) AS unsupported_gap_minutes,
        CASE 
            WHEN ec.window_source = 'ACTUAL' AND SECONDS_BETWEEN(ec.window_end_utc, ec.window_start_utc) > 0
            THEN ROUND((SUM(ec.supported_overlap_minutes) / (SECONDS_BETWEEN(ec.window_end_utc, ec.window_start_utc) / 60.0)) * 100.0, 1)
            ELSE 0.0
        END AS coverage_pct,
        MIN(ec.temperature_c) AS min_temp_c,
        MAX(ec.temperature_c) AS max_temp_c,
        ROUND(AVG(ec.temperature_c), 2) AS avg_temp_c,
        MIN(ec.min_temp_c) AS safe_min_temp_c,
        MAX(ec.max_temp_c) AS safe_max_temp_c,
        ROUND(SUM(CASE WHEN ec.temperature_c > ec.max_temp_c AND ec.is_ambiguous_overlap = FALSE THEN ec.supported_overlap_minutes ELSE 0 END), 2) AS minutes_above_safe,
        ROUND(SUM(CASE WHEN ec.temperature_c < ec.min_temp_c AND ec.is_ambiguous_overlap = FALSE THEN ec.supported_overlap_minutes ELSE 0 END), 2) AS minutes_below_safe,
        ROUND(SUM(ec.above_dm), 2) AS degree_minutes_above,
        ROUND(SUM(ec.below_dm), 2) AS degree_minutes_below,
        ROUND(SUM(ec.above_dm + ec.below_dm), 2) AS total_degree_minutes,
        CASE 
            WHEN ec.window_source = 'PLANNED_ONLY' THEN 'EXCLUDED_PLANNED_ONLY'
            WHEN COALESCE(lc.assigned_logger_count, 0) > 1 THEN 'MULTI_LOGGER_WARNING'
            WHEN SUM(ec.ambiguous_overlap_minutes) > 0 THEN 'AMBIGUOUS_CUSTODY_EXCLUSION'
            WHEN SUM(ec.supported_overlap_minutes) = 0 THEN 'NO_SUPPORTED_OBSERVATIONS'
            WHEN GREATEST(0.0, (SECONDS_BETWEEN(ec.window_end_utc, ec.window_start_utc) / 60.0) - SUM(ec.supported_overlap_minutes)) > 0 THEN 'PARTIAL_GAP_WARNING'
            ELSE 'ADEQUATELY_COVERED'
        END AS coverage_status
    FROM exposure_calcs ec
    LEFT JOIN logger_counts lc ON ec.shipment_id = lc.shipment_id
    GROUP BY 
        ec.handoff_id, ec.shipment_id, ec.sequence_no, ec.handoff_type, 
        ec.from_party, ec.to_party, ec.location, ec.window_source,
        ec.window_start_utc, ec.window_end_utc, lc.assigned_logger_count
    """)

    # View 3: V_EXCURSION_ATTRIBUTION
    c.execute("""
    CREATE OR REPLACE VIEW V_EXCURSION_ATTRIBUTION AS
    WITH logger_counts AS (
        SELECT 
            assigned_shipment_id AS shipment_id,
            COUNT(DISTINCT logger_id) AS assigned_logger_count
        FROM logger_devices
        GROUP BY assigned_shipment_id
    ),
    handoff_conflicts AS (
        SELECT 
            h1.id AS handoff_id,
            h2.id AS other_handoff_id,
            GREATEST(h1.actual_start_at, h2.actual_start_at) AS conflict_start,
            LEAST(h1.actual_end_at, h2.actual_end_at) AS conflict_end
        FROM handoffs h1
        JOIN handoffs h2 
          ON h1.shipment_id = h2.shipment_id
         AND h1.id != h2.id
         AND h1.actual_start_at IS NOT NULL
         AND h1.actual_end_at IS NOT NULL
         AND h2.actual_start_at IS NOT NULL
         AND h2.actual_end_at IS NOT NULL
         AND h1.actual_start_at < h2.actual_end_at
         AND h1.actual_end_at > h2.actual_start_at
    ),
    corrected AS (
        SELECT 
            r.reading_id,
            r.logger_id,
            r.reading_at_utc,
            ADD_SECONDS(r.reading_at_utc, -COALESCE(ld.clock_skew_seconds, 0)) AS corrected_at_utc,
            r.temperature_c,
            r.battery_pct,
            ld.assigned_shipment_id AS shipment_id,
            COALESCE(ld.clock_skew_seconds, 0) AS clock_skew_seconds
        FROM logger_readings r
        JOIN logger_devices ld ON r.logger_id = ld.logger_id
    ),
    segments AS (
        SELECT 
            c.reading_id,
            c.logger_id,
            c.shipment_id,
            c.reading_at_utc,
            c.corrected_at_utc AS segment_start,
            LEAD(c.corrected_at_utc) OVER (
                PARTITION BY c.logger_id 
                ORDER BY c.corrected_at_utc, c.reading_id
            ) AS segment_end,
            c.temperature_c,
            c.clock_skew_seconds
        FROM corrected c
    ),
    supported_segments AS (
        SELECT 
            s.*,
            SECONDS_BETWEEN(s.segment_end, s.segment_start) AS duration_seconds,
            CASE 
                WHEN s.segment_end IS NOT NULL 
                 AND SECONDS_BETWEEN(s.segment_end, s.segment_start) > 0 
                 AND SECONDS_BETWEEN(s.segment_end, s.segment_start) <= 600 
                THEN TRUE 
                ELSE FALSE 
            END AS is_supported
        FROM segments s
    ),
    candidate_intersections AS (
        SELECT 
            e.excursion_id,
            e.shipment_id,
            e.started_at_utc AS exc_start,
            e.ended_at_utc AS exc_end,
            SECONDS_BETWEEN(e.ended_at_utc, e.started_at_utc) / 60.0 AS exc_duration_minutes,
            e.max_temp_c AS exc_peak_temp_c,
            h.id AS handoff_id,
            h.sequence_number AS sequence_no,
            h.handoff_type,
            h.from_party AS associated_party,
            h.to_party,
            h.location,
            h.actual_start_at AS window_start_utc,
            h.actual_end_at AS window_end_utc,
            CASE 
                WHEN h.actual_start_at IS NOT NULL AND h.actual_end_at IS NOT NULL THEN 'ACTUAL'
                ELSE 'PLANNED_ONLY'
            END AS window_source,
            p.min_temp_c AS product_min_c,
            p.max_temp_c AS product_max_c,
            ss.reading_id,
            ss.temperature_c,
            GREATEST(ss.segment_start, h.actual_start_at, e.started_at_utc) AS overlap_start,
            LEAST(ss.segment_end, h.actual_end_at, e.ended_at_utc) AS overlap_end
        FROM excursions e
        JOIN handoffs h ON e.shipment_id = h.shipment_id
        JOIN shipments sh ON h.shipment_id = sh.id
        JOIN products p ON sh.product_id = p.id
        LEFT JOIN supported_segments ss
            ON h.shipment_id = ss.shipment_id
           AND ss.is_supported = TRUE
           AND h.actual_start_at IS NOT NULL
           AND h.actual_end_at IS NOT NULL
           AND ss.segment_start < LEAST(h.actual_end_at, e.ended_at_utc)
           AND ss.segment_end > GREATEST(h.actual_start_at, e.started_at_utc)
        WHERE (
            -- Either overlaps actual window or is planned only
            (h.actual_start_at IS NOT NULL AND h.actual_end_at IS NOT NULL AND h.actual_start_at < e.ended_at_utc AND h.actual_end_at > e.started_at_utc)
            OR (h.actual_start_at IS NULL AND h.planned_start_at < e.ended_at_utc AND h.planned_end_at > e.started_at_utc)
        )
    ),
    intersection_annotated AS (
        SELECT 
            ci.*,
            CASE 
                WHEN hc.handoff_id IS NOT NULL THEN TRUE 
                ELSE FALSE 
            END AS is_ambiguous_overlap
        FROM candidate_intersections ci
        LEFT JOIN handoff_conflicts hc
            ON ci.handoff_id = hc.handoff_id
           AND ci.overlap_start < hc.conflict_end
           AND ci.overlap_end > hc.conflict_start
    ),
    calcs AS (
        SELECT 
            ia.*,
            CASE 
                WHEN ia.reading_id IS NOT NULL 
                 AND ia.overlap_end > ia.overlap_start
                 AND ia.is_ambiguous_overlap = FALSE
                THEN SECONDS_BETWEEN(ia.overlap_end, ia.overlap_start) / 60.0
                ELSE 0.0
            END AS supported_overlap_minutes,
            CASE 
                WHEN ia.reading_id IS NOT NULL 
                 AND ia.overlap_end > ia.overlap_start
                 AND ia.is_ambiguous_overlap = TRUE
                THEN SECONDS_BETWEEN(ia.overlap_end, ia.overlap_start) / 60.0
                ELSE 0.0
            END AS ambiguous_overlap_minutes,
            CASE 
                WHEN ia.reading_id IS NOT NULL 
                 AND ia.overlap_end > ia.overlap_start
                 AND ia.is_ambiguous_overlap = FALSE
                 AND ia.temperature_c > ia.product_max_c
                THEN (ia.temperature_c - ia.product_max_c) * (SECONDS_BETWEEN(ia.overlap_end, ia.overlap_start) / 60.0)
                ELSE 0.0
            END AS above_dm,
            CASE 
                WHEN ia.reading_id IS NOT NULL 
                 AND ia.overlap_end > ia.overlap_start
                 AND ia.is_ambiguous_overlap = FALSE
                 AND ia.temperature_c < ia.product_min_c
                THEN (ia.product_min_c - ia.temperature_c) * (SECONDS_BETWEEN(ia.overlap_end, ia.overlap_start) / 60.0)
                ELSE 0.0
            END AS below_dm
        FROM intersection_annotated ia
    ),
    aggregated AS (
        SELECT 
            c.excursion_id,
            c.shipment_id,
            c.handoff_id,
            c.sequence_no,
            c.handoff_type,
            c.associated_party,
            c.to_party,
            c.location,
            c.window_source,
            c.window_start_utc,
            c.window_end_utc,
            c.exc_start,
            c.exc_end,
            c.exc_duration_minutes,
            c.exc_peak_temp_c,
            COALESCE(lc.assigned_logger_count, 0) AS assigned_logger_count,
            COUNT(DISTINCT c.reading_id) AS reading_count,
            ROUND(SUM(c.supported_overlap_minutes), 2) AS supported_observation_minutes,
            ROUND(SUM(c.ambiguous_overlap_minutes), 2) AS ambiguous_minutes,
            ROUND(SUM(c.above_dm), 2) AS handoff_degree_minutes_above,
            ROUND(SUM(c.below_dm), 2) AS handoff_degree_minutes_below,
            ROUND(SUM(c.above_dm + c.below_dm), 2) AS handoff_total_dm
        FROM calcs c
        LEFT JOIN logger_counts lc ON c.shipment_id = lc.shipment_id
        GROUP BY 
            c.excursion_id, c.shipment_id, c.handoff_id, c.sequence_no, c.handoff_type,
            c.associated_party, c.to_party, c.location, c.window_source,
            c.window_start_utc, c.window_end_utc, c.exc_start, c.exc_end,
            c.exc_duration_minutes, c.exc_peak_temp_c, lc.assigned_logger_count
    ),
    totals AS (
        SELECT 
            excursion_id,
            SUM(handoff_total_dm) AS total_excursion_dm,
            SUM(supported_observation_minutes) AS total_supported_obs_min
        FROM aggregated
        GROUP BY excursion_id
    )
    SELECT 
        a.excursion_id,
        a.shipment_id,
        a.handoff_id,
        a.sequence_no,
        a.handoff_type,
        a.associated_party,
        a.to_party,
        a.location,
        a.window_source,
        a.window_start_utc,
        a.window_end_utc,
        a.exc_start,
        a.exc_end,
        a.exc_duration_minutes,
        a.exc_peak_temp_c,
        a.assigned_logger_count,
        a.reading_count,
        a.supported_observation_minutes,
        a.ambiguous_minutes,
        a.handoff_degree_minutes_above,
        a.handoff_degree_minutes_below,
        a.handoff_total_dm,
        t.total_excursion_dm,
        t.total_supported_obs_min,
        CASE 
            WHEN t.total_excursion_dm > 0 
            THEN ROUND(a.handoff_total_dm / t.total_excursion_dm, 4)
            ELSE 0.0 
        END AS exposure_share,
        DENSE_RANK() OVER (
            PARTITION BY a.excursion_id 
            ORDER BY a.handoff_total_dm DESC
        ) AS attribution_rank,
        CASE 
            WHEN a.window_source = 'PLANNED_ONLY' THEN 'EXCLUDED_PLANNED_ONLY'
            WHEN a.assigned_logger_count > 1 THEN 'INCONCLUSIVE_MULTI_LOGGER'
            WHEN t.total_supported_obs_min = 0 THEN 'INCONCLUSIVE_INSUFFICIENT_DATA'
            WHEN t.total_excursion_dm = 0 THEN 'NO_EXCURSION_OBSERVED'
            ELSE 'Unvalidated prototype ranking'
        END AS evidence_status,
        'Estimated from logger observations and stated modelling assumptions. Not a determination of product-core temperature, root cause or legal liability. Product disposition remains with the quality team.' AS disclaimer
    FROM aggregated a
    JOIN totals t ON a.excursion_id = t.excursion_id
    """)

    print("Isolated test tables and repaired views successfully created.")
    print("-" * 72)

    # 4. Insert Fixtures and Run Isolated Tests
    all_passed = True
    test_results = []

    def record_test(name, passed, detail=""):
        nonlocal all_passed
        status = "PASS" if passed else "FAIL"
        test_results.append((name, status, detail))
        if not passed:
            all_passed = False
        print(f"[{status}] {name}")
        if detail:
            print(f"       {detail}")

    # ── Product Fixtures ─────────────────────────────────────────
    c.execute("""
    INSERT INTO PRODUCTS VALUES 
      ('P_VACC', 'mRNA Vaccine', 2.0, 8.0, 30),
      ('P_CART', 'CAR-T Cell Therapy', -25.0, -15.0, 15),
      ('P_ALBU', 'Human Albumin', 15.0, 25.0, 60)
    """)

    # ── Test 1 & Test 2: Half-Open Boundary + Clock Skew ──────────
    c.execute("INSERT INTO SHIPMENTS VALUES ('S1', 'SHP-TEST-01', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L1', 'DEV-1', 'S1', 120)") # +120s clock skew
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H1', 'S1', 1, 'Reefer Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00'),
      ('H2', 'S1', 2, 'Warehouse Dock', 'Party B', 'Party C', 'Loc 2',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00',
       TIMESTAMP '2026-10-30 14:00:00', TIMESTAMP '2026-10-30 14:00:00')
    """)
    # Reading at raw 12:02:00 -> corrected = 12:02:00 - 120s = 12:00:00.
    # Exactly at boundary 12:00:00.
    # Must belong to H2 (>= 12:00), NOT H1 (< 12:00).
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_BOUND', 'L1', TIMESTAMP '2026-10-30 12:02:00', 5.0, 99.0)
    """)

    res = c.execute("SELECT * FROM V_READING_HANDOFF_MEMBERSHIP WHERE reading_id = 'R_BOUND'").fetchall()
    row = res[0]
    expected_corr = "2026-10-30 12:00:00.000000"
    t1_pass = (row["HANDOFF_ID"] == "H2" and row["MEMBERSHIP_STATUS"] == "MATCHED")
    t2_pass = (str(row["CORRECTED_AT_UTC"]) == expected_corr)

    record_test("Test 1: Half-open boundary at 12:00 belongs to H2, not H1", t1_pass,
                f"Assigned handoff: {row['HANDOFF_ID']}, status: {row['MEMBERSHIP_STATUS']}")
    record_test("Test 2: +120s clock skew subtracted (12:02:00 -> 12:00:00)", t2_pass,
                f"Raw: {row['READING_AT_UTC']}, Corrected: {row['CORRECTED_AT_UTC']}")

    # ── Test 3, 4, 5: Supported Segment, Splits, and Product Bounds ──
    c.execute("INSERT INTO SHIPMENTS VALUES ('S2', 'SHP-TEST-02', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L2', 'DEV-2', 'S2', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H2_1', 'S2', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00'),
      ('H2_2', 'S2', 2, 'Dock', 'Party B', 'Party C', 'Loc 2',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00',
       TIMESTAMP '2026-10-30 14:00:00', TIMESTAMP '2026-10-30 14:00:00')
    """)
    # Segment crossing boundary:
    # Reading 1: 11:58:00 at 10.0°C (safe max 8.0°C -> breach 2.0°C).
    # Reading 2: 12:03:00 at 10.0°C (segment duration = 5 min = 300s <= 600s).
    # Reading 3: 12:08:00 at 0.0°C (safe min 2.0°C -> below breach 2.0°C, duration = 5 min).
    # Reading 4: 12:13:00 at 5.0°C (end of segment 3).
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_SEG1', 'L2', TIMESTAMP '2026-10-30 11:58:00', 10.0, 99.0),
      ('R_SEG2', 'L2', TIMESTAMP '2026-10-30 12:03:00', 10.0, 99.0),
      ('R_SEG3', 'L2', TIMESTAMP '2026-10-30 12:08:00', 0.0, 99.0),
      ('R_SEG4', 'L2', TIMESTAMP '2026-10-30 12:13:00', 5.0, 99.0)
    """)

    exp_rows = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S2' ORDER BY sequence_no").fetchall()
    h2_1 = exp_rows[0]
    h2_2 = exp_rows[1]

    t3_pass = (float(h2_2["DEGREE_MINUTES_ABOVE"]) == 16.0) # 6.0 + 10.0
    t4_pass = (float(h2_2["DEGREE_MINUTES_BELOW"]) == 10.0) # 10.0 below
    t5_pass = (float(h2_1["DEGREE_MINUTES_ABOVE"]) == 4.0 and float(h2_1["SUPPORTED_OBSERVATION_MINUTES"]) == 2.0)

    record_test("Test 3: Constant 10°C for supported segment with 8°C max produces correct degree-minutes", t3_pass,
                f"H2_2 above DM: {h2_2['DEGREE_MINUTES_ABOVE']} (expected 16.0 = 6.0 split + 10.0)")
    record_test("Test 4: Constant 0°C for 5 minutes with 2°C min produces 10 °C·min below range", t4_pass,
                f"H2_2 below DM: {h2_2['DEGREE_MINUTES_BELOW']} (expected 10.0)")
    record_test("Test 5: Segment crossing boundary (11:58 to 12:03) split across H1 (2m) and H2 (3m)", t5_pass,
                f"H2_1 obs min: {h2_1['SUPPORTED_OBSERVATION_MINUTES']} (expected 2.0), DM: {h2_1['DEGREE_MINUTES_ABOVE']} (expected 4.0)")

    # ── Test 6: Gap above 600s contributes 0 supported exposure ──
    c.execute("INSERT INTO SHIPMENTS VALUES ('S3', 'SHP-TEST-03', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L3', 'DEV-3', 'S3', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H3_1', 'S3', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 10:00:00', TIMESTAMP '2026-10-30 10:00:00')
    """)
    # Gap: 08:00 to 08:20 (1200 seconds > 600s default max gap limit!)
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_GAP1', 'L3', TIMESTAMP '2026-10-30 08:00:00', 15.0, 99.0),
      ('R_GAP2', 'L3', TIMESTAMP '2026-10-30 08:20:00', 15.0, 99.0)
    """)
    h3_row = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S3'").fetchall()[0]
    t6_pass = (float(h3_row["SUPPORTED_OBSERVATION_MINUTES"]) == 0.0 and float(h3_row["TOTAL_DEGREE_MINUTES"]) == 0.0 and float(h3_row["UNSUPPORTED_GAP_MINUTES"]) == 120.0)
    record_test("Test 6: Gap above configured 600s contributes 0 supported exposure and flags gap", t6_pass,
                f"Supported min: {h3_row['SUPPORTED_OBSERVATION_MINUTES']}, Total DM: {h3_row['TOTAL_DEGREE_MINUTES']}, Gap min: {h3_row['UNSUPPORTED_GAP_MINUTES']}")

    # ── Test 7: Excursion covering only part of segment ──────────
    c.execute("INSERT INTO SHIPMENTS VALUES ('S4', 'SHP-TEST-04', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L4', 'DEV-4', 'S4', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H4_1', 'S4', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00',
       TIMESTAMP '2026-10-30 14:00:00', TIMESTAMP '2026-10-30 14:00:00')
    """)
    # Reading segment: 12:00 to 12:08 (8 min = 480s <= 600s) at 12.0°C (safe max 8.0°C).
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_EXC1', 'L4', TIMESTAMP '2026-10-30 12:00:00', 12.0, 99.0),
      ('R_EXC2', 'L4', TIMESTAMP '2026-10-30 12:08:00', 5.0, 99.0)
    """)
    # Excursion from 12:03 to 12:08 (5 min overlap with segment).
    c.execute("""
    INSERT INTO EXCURSIONS VALUES 
      ('EXC_PART', 'S4', 'P_VACC',
       TIMESTAMP '2026-10-30 12:03:00', TIMESTAMP '2026-10-30 12:08:00',
       12.0, 12.0, 'Automated Monitor')
    """)
    exc_row = c.execute("SELECT * FROM V_EXCURSION_ATTRIBUTION WHERE excursion_id = 'EXC_PART'").fetchall()[0]
    t7_pass = (float(exc_row["HANDOFF_TOTAL_DM"]) == 20.0 and float(exc_row["SUPPORTED_OBSERVATION_MINUTES"]) == 5.0)
    record_test("Test 7: Excursion covering only part of segment counts only that part", t7_pass,
                f"Obs minutes: {exc_row['SUPPORTED_OBSERVATION_MINUTES']} (expected 5.0), Excursion DM: {exc_row['HANDOFF_TOTAL_DM']} (expected 20.0)")

    # ── Test 8: Different product limits produce different results ─
    c.execute("INSERT INTO SHIPMENTS VALUES ('S5', 'SHP-TEST-05', 'P_CART')") # CAR-T max -15.0°C
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L5', 'DEV-5', 'S5', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H5_1', 'S5', 1, 'Cryo Reefer', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 10:00:00', TIMESTAMP '2026-10-30 10:00:00')
    """)
    # 5 min at 10.0°C: for CAR-T (max -15°C), breach is 10 - (-15) = 25.0°C!
    # Exposure = 25.0 * 5 = 125.0 °C·min.
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_CART1', 'L5', TIMESTAMP '2026-10-30 08:00:00', 10.0, 99.0),
      ('R_CART2', 'L5', TIMESTAMP '2026-10-30 08:05:00', 10.0, 99.0)
    """)
    h5_row = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S5'").fetchall()[0]
    t8_pass = (float(h5_row["DEGREE_MINUTES_ABOVE"]) == 125.0)
    record_test("Test 8: Product limits from PRODUCTS (-25 to -15°C) produce 125.0 °C·min", t8_pass,
                f"CAR-T above DM: {h5_row['DEGREE_MINUTES_ABOVE']} (expected 125.0)")

    # ── Test 9: Segment overlapping custody excluded from single-party exposure ──
    c.execute("INSERT INTO SHIPMENTS VALUES ('S6', 'SHP-TEST-06', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L6', 'DEV-6', 'S6', 0)")
    # Overlapping custody: H6_1 ends at 12:10, H6_2 starts at 12:00.
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H6_1', 'S6', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 10:00:00', TIMESTAMP '2026-10-30 10:00:00',
       TIMESTAMP '2026-10-30 12:10:00', TIMESTAMP '2026-10-30 12:10:00'),
      ('H6_2', 'S6', 2, 'Dock', 'Party B', 'Party C', 'Loc 2',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00',
       TIMESTAMP '2026-10-30 14:00:00', TIMESTAMP '2026-10-30 14:00:00')
    """)
    # Reading at 12:02 to 12:06 (falls inside the 12:00-12:10 overlap window)
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_OV1', 'L6', TIMESTAMP '2026-10-30 12:02:00', 12.0, 99.0),
      ('R_OV2', 'L6', TIMESTAMP '2026-10-30 12:06:00', 12.0, 99.0)
    """)
    h6_rows = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S6' ORDER BY sequence_no").fetchall()
    h6_1 = h6_rows[0]
    h6_2 = h6_rows[1]
    # Under conservative policy: overlap interval is excluded from single-party attributable exposure
    # Contributes to ambiguous_minutes (4.0 min), 0.0 to degree_minutes_above
    t9_pass = (
        float(h6_1["AMBIGUOUS_MINUTES"]) == 4.0 and
        float(h6_2["AMBIGUOUS_MINUTES"]) == 4.0 and
        float(h6_1["DEGREE_MINUTES_ABOVE"]) == 0.0 and
        float(h6_2["DEGREE_MINUTES_ABOVE"]) == 0.0 and
        h6_1["COVERAGE_STATUS"] == "AMBIGUOUS_CUSTODY_EXCLUSION"
    )
    record_test("Test 9: Overlapping custody segment excluded from attributable exposure and flagged", t9_pass,
                f"H6_1 ambiguous min: {h6_1['AMBIGUOUS_MINUTES']}, status: {h6_1['COVERAGE_STATUS']}")

    # ── Test 10: Missing actual timestamps (PLANNED_ONLY) excluded ─
    c.execute("INSERT INTO SHIPMENTS VALUES ('S7', 'SHP-TEST-07', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L7', 'DEV-7', 'S7', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H7_PLAN', 'S7', 1, 'Planned Flight', 'Air Carrier', 'Ground Agent', 'Airport',
       TIMESTAMP '2026-10-30 08:00:00', NULL,
       TIMESTAMP '2026-10-30 12:00:00', NULL)
    """)
    h7_row = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S7'").fetchall()[0]
    t10_pass = (h7_row["WINDOW_SOURCE"] == "PLANNED_ONLY" and h7_row["COVERAGE_STATUS"] == "EXCLUDED_PLANNED_ONLY")
    record_test("Test 10: Missing actual timestamps marked PLANNED_ONLY and excluded", t10_pass,
                f"Window source: {h7_row['WINDOW_SOURCE']}, status: {h7_row['COVERAGE_STATUS']}")

    # ── Test 11: No readings at all returns INCONCLUSIVE ─────────
    c.execute("INSERT INTO SHIPMENTS VALUES ('S8', 'SHP-TEST-08', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L8', 'DEV-8', 'S8', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H8_1', 'S8', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00')
    """)
    c.execute("""
    INSERT INTO EXCURSIONS VALUES 
      ('EXC_NODATA', 'S8', 'P_VACC',
       TIMESTAMP '2026-10-30 09:00:00', TIMESTAMP '2026-10-30 10:00:00',
       12.0, 12.0, 'Automated Monitor')
    """)
    exc_nodata = c.execute("SELECT * FROM V_EXCURSION_ATTRIBUTION WHERE excursion_id = 'EXC_NODATA'").fetchall()[0]
    t11_pass = (exc_nodata["EVIDENCE_STATUS"] == "INCONCLUSIVE_INSUFFICIENT_DATA")
    record_test("Test 11: No readings at all returns INCONCLUSIVE_INSUFFICIENT_DATA", t11_pass,
                f"Status: {exc_nodata['EVIDENCE_STATUS']}")

    # ── Test 12: Multiple assigned loggers returns INCONCLUSIVE ──
    c.execute("INSERT INTO SHIPMENTS VALUES ('S9', 'SHP-TEST-09', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L9_A', 'DEV-9A', 'S9', 0), ('L9_B', 'DEV-9B', 'S9', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H9_1', 'S9', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 12:00:00', TIMESTAMP '2026-10-30 12:00:00')
    """)
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_M1', 'L9_A', TIMESTAMP '2026-10-30 08:00:00', 12.0, 99.0),
      ('R_M2', 'L9_A', TIMESTAMP '2026-10-30 08:05:00', 12.0, 99.0)
    """)
    c.execute("""
    INSERT INTO EXCURSIONS VALUES 
      ('EXC_MULTI', 'S9', 'P_VACC',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:05:00',
       12.0, 12.0, 'Monitor')
    """)
    exc_multi = c.execute("SELECT * FROM V_EXCURSION_ATTRIBUTION WHERE excursion_id = 'EXC_MULTI'").fetchall()[0]
    t12_pass = (exc_multi["EVIDENCE_STATUS"] == "INCONCLUSIVE_MULTI_LOGGER")
    record_test("Test 12: Multiple assigned loggers returns INCONCLUSIVE_MULTI_LOGGER", t12_pass,
                f"Status: {exc_multi['EVIDENCE_STATUS']}")

    # ── Test 13: Duplicate timestamps produce 0 duration ─────────
    c.execute("INSERT INTO SHIPMENTS VALUES ('S10', 'SHP-TEST-10', 'P_VACC')")
    c.execute("INSERT INTO LOGGER_DEVICES VALUES ('L10', 'DEV-10', 'S10', 0)")
    c.execute("""
    INSERT INTO HANDOFFS VALUES 
      ('H10_1', 'S10', 1, 'Truck', 'Party A', 'Party B', 'Loc 1',
       TIMESTAMP '2026-10-30 08:00:00', TIMESTAMP '2026-10-30 08:00:00',
       TIMESTAMP '2026-10-30 10:00:00', TIMESTAMP '2026-10-30 10:00:00')
    """)
    # Two readings at exact same timestamp
    c.execute("""
    INSERT INTO LOGGER_READINGS VALUES 
      ('R_DUP1', 'L10', TIMESTAMP '2026-10-30 08:00:00', 12.0, 99.0),
      ('R_DUP2', 'L10', TIMESTAMP '2026-10-30 08:00:00', 14.0, 99.0),
      ('R_DUP3', 'L10', TIMESTAMP '2026-10-30 08:05:00', 12.0, 99.0)
    """)
    h10_row = c.execute("SELECT * FROM V_HANDOFF_THERMAL_EXPOSURE WHERE shipment_id = 'S10'").fetchall()[0]
    t13_pass = (float(h10_row["SUPPORTED_OBSERVATION_MINUTES"]) == 5.0)
    record_test("Test 13: Duplicate timestamps contribute 0 duration, no inflated exposure", t13_pass,
                f"Obs minutes: {h10_row['SUPPORTED_OBSERVATION_MINUTES']} (expected 5.0)")

    # ── Test 14: Time before first reading & after last reading ──
    # In S10: Handoff is 08:00 to 10:00 (120 minutes).
    # Readings end at 08:05:00.
    # Time from 08:05 to 10:00 (115 min) must be unsupported gap, NOT carried forward!
    t14_pass = (float(h10_row["UNSUPPORTED_GAP_MINUTES"]) == 115.0)
    record_test("Test 14: Time after last reading is unsupported gap, does not extend indefinitely", t14_pass,
                f"Unsupported gap: {h10_row['UNSUPPORTED_GAP_MINUTES']} (expected 115.0 min)")

    # 5. Clean up isolated test schema
    c.execute("DROP SCHEMA IF EXISTS HANDOFFGUARD_TEST CASCADE")
    print("-" * 72)
    print("Cleaned up isolated schema HANDOFFGUARD_TEST.")
    c.close()

    print("=" * 72)
    print(f"SUMMARY: {len(test_results)} Tests Executed. All Passed: {all_passed}")
    print("=" * 72)

    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
