-- ============================================================
-- HandoffGuard — Migration 005: Repair Analytical Views
-- Schema: HANDOFFGUARD
--
-- Incorporates all mandatory architectural revisions:
-- 1. Configurable prototype gap assumption: default 600 seconds (10 min).
--    (Engineering/demo prototype assumption, not a validated pharmaceutical standard).
-- 2. Requires actual timestamps (ACTUAL_START_AT, ACTUAL_END_AT) for actual-custody attribution.
--    Handoffs with planned-only timestamps are marked PLANNED_ONLY and excluded.
-- 3. Segment-level ambiguity detection: overlapping custody intervals are conservatively
--    excluded from single-party attributable exposure and flagged.
-- 4. Single-logger MVP rule: multi-logger assignments produce explicit warnings/inconclusive status.
-- 5. Excursion-specific attribution: segments intersect BOTH handoff and excursion windows.
-- 6. Replaces judicial liability terminology with objective evidence-aid terms:
--    associated_party, evidence_status, and mandatory quality-team disclaimer.
-- ============================================================

OPEN SCHEMA HANDOFFGUARD;

-- ------------------------------------------------------------
-- VIEW 1: V_READING_HANDOFF_MEMBERSHIP
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW HANDOFFGUARD.V_READING_HANDOFF_MEMBERSHIP AS
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
    FROM HANDOFFGUARD.logger_readings r
    JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id
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
    LEFT JOIN HANDOFFGUARD.handoffs h 
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
FROM counts;


-- ------------------------------------------------------------
-- VIEW 2: V_HANDOFF_THERMAL_EXPOSURE
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW HANDOFFGUARD.V_HANDOFF_THERMAL_EXPOSURE AS
WITH logger_counts AS (
    SELECT 
        assigned_shipment_id AS shipment_id,
        COUNT(DISTINCT logger_id) AS assigned_logger_count
    FROM HANDOFFGUARD.logger_devices
    GROUP BY assigned_shipment_id
),
handoff_conflicts AS (
    SELECT 
        h1.id AS handoff_id,
        h2.id AS other_handoff_id,
        GREATEST(h1.actual_start_at, h2.actual_start_at) AS conflict_start,
        LEAST(h1.actual_end_at, h2.actual_end_at) AS conflict_end
    FROM HANDOFFGUARD.handoffs h1
    JOIN HANDOFFGUARD.handoffs h2 
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
    FROM HANDOFFGUARD.logger_readings r
    JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id
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
    FROM HANDOFFGUARD.handoffs h
    JOIN HANDOFFGUARD.shipments sh ON h.shipment_id = sh.id
    JOIN HANDOFFGUARD.products p ON sh.product_id = p.id
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
    ec.window_start_utc, ec.window_end_utc, lc.assigned_logger_count;


-- ------------------------------------------------------------
-- VIEW 3: V_EXCURSION_ATTRIBUTION
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW HANDOFFGUARD.V_EXCURSION_ATTRIBUTION AS
WITH logger_counts AS (
    SELECT 
        assigned_shipment_id AS shipment_id,
        COUNT(DISTINCT logger_id) AS assigned_logger_count
    FROM HANDOFFGUARD.logger_devices
    GROUP BY assigned_shipment_id
),
handoff_conflicts AS (
    SELECT 
        h1.id AS handoff_id,
        h2.id AS other_handoff_id,
        GREATEST(h1.actual_start_at, h2.actual_start_at) AS conflict_start,
        LEAST(h1.actual_end_at, h2.actual_end_at) AS conflict_end
    FROM HANDOFFGUARD.handoffs h1
    JOIN HANDOFFGUARD.handoffs h2 
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
    FROM HANDOFFGUARD.logger_readings r
    JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id
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
    FROM HANDOFFGUARD.excursions e
    JOIN HANDOFFGUARD.handoffs h ON e.shipment_id = h.shipment_id
    JOIN HANDOFFGUARD.shipments sh ON h.shipment_id = sh.id
    JOIN HANDOFFGUARD.products p ON sh.product_id = p.id
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
JOIN totals t ON a.excursion_id = t.excursion_id;
