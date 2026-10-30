-- ============================================================
-- HandoffGuard — Migration 004: Create Views
-- ExaThon India 2026 | Exasol Personal
-- ============================================================
-- Three analytical views that form the core technical
-- differentiator of HandoffGuard.
--
-- v_reading_handoff_membership  — interval join (Phase 3)
-- v_handoff_thermal_exposure    — degree-minutes per handoff (Phase 4)
-- v_excursion_attribution       — ranked attribution (Phase 5)
--
-- CRITICAL: logger_readings has NO handoff_id column.
-- All association is derived here via time-window overlap.

OPEN SCHEMA HANDOFFGUARD;

-- ============================================================
-- VIEW 1: v_reading_handoff_membership
-- Derives which handoff window each reading belongs to by
-- comparing reading_at_utc against handoff window boundaries.
-- Applies a configurable clock-skew tolerance (default 120 s).
-- ============================================================
CREATE OR REPLACE VIEW HANDOFFGUARD.v_reading_handoff_membership AS
WITH
-- Step 1: apply each logger's clock skew to get corrected timestamp
corrected AS (
    SELECT
        r.reading_id,
        r.logger_id,
        r.reading_at_utc,
        -- Corrected timestamp = raw - skew (if skew > 0, device is ahead)
        ADD_SECONDS(r.reading_at_utc, -ld.clock_skew_seconds)  AS corrected_at_utc,
        r.temperature_c,
        r.battery_pct,
        ld.assigned_shipment_id,
        ld.clock_skew_seconds
    FROM HANDOFFGUARD.logger_readings r
    JOIN HANDOFFGUARD.logger_devices  ld ON r.logger_id = ld.logger_id
),
-- Step 2: interval join — match corrected timestamp to handoff window ± 120 s tolerance
matched AS (
    SELECT
        c.reading_id,
        c.logger_id,
        c.reading_at_utc,
        c.corrected_at_utc,
        c.temperature_c,
        c.battery_pct,
        c.assigned_shipment_id                          AS shipment_id,
        c.clock_skew_seconds,
        h.handoff_id,
        h.handoff_type,
        h.from_party,
        h.to_party,
        h.window_start_utc,
        h.window_end_utc,
        -- How many seconds the corrected reading is from the nearest window boundary
        CASE
            WHEN c.corrected_at_utc < h.window_start_utc
                THEN SECONDS_BETWEEN(c.corrected_at_utc, h.window_start_utc)
            WHEN c.corrected_at_utc > h.window_end_utc
                THEN SECONDS_BETWEEN(h.window_end_utc, c.corrected_at_utc)
            ELSE 0
        END                                             AS boundary_skew_seconds
    FROM corrected c
    JOIN HANDOFFGUARD.handoffs h
        ON  h.shipment_id = c.assigned_shipment_id
        AND c.corrected_at_utc
            BETWEEN ADD_SECONDS(h.window_start_utc, -120)
                AND ADD_SECONDS(h.window_end_utc,    120)
),
-- Step 3: count how many handoffs each reading matched (for ambiguity detection)
match_counts AS (
    SELECT reading_id, COUNT(*) AS match_count
    FROM matched
    GROUP BY reading_id
)
SELECT
    m.reading_id,
    m.logger_id,
    m.reading_at_utc,
    m.corrected_at_utc,
    m.temperature_c,
    m.battery_pct,
    m.shipment_id,
    m.handoff_id,
    m.handoff_type,
    m.from_party,
    m.to_party,
    m.window_start_utc,
    m.window_end_utc,
    m.clock_skew_seconds                                    AS skew_seconds,
    m.boundary_skew_seconds,
    mc.match_count,
    -- Membership status classification
    CASE
        WHEN mc.match_count > 1                             THEN 'ambiguous'
        WHEN m.boundary_skew_seconds > 0                   THEN 'matched_with_skew'
        ELSE                                                     'matched'
    END                                                     AS membership_status,
    CASE WHEN mc.match_count > 1 THEN TRUE ELSE FALSE END   AS ambiguity_flag
FROM matched m
JOIN match_counts mc ON m.reading_id = mc.reading_id;

-- Note: readings that match NO handoff window are NOT in this view.
-- They appear as 'unmatched' when queried as:
--   SELECT r.* FROM logger_readings r
--   WHERE r.reading_id NOT IN (SELECT reading_id FROM v_reading_handoff_membership)
-- The API layer combines both queries and labels them accordingly.


-- ============================================================
-- VIEW 2: v_handoff_thermal_exposure
-- Aggregates degree-minutes of thermal exposure per handoff.
-- Degree-minutes = (temp - safe_threshold) × minutes_at_temp
-- Sampling interval is approximated from consecutive readings.
-- ============================================================
CREATE OR REPLACE VIEW HANDOFFGUARD.v_handoff_thermal_exposure AS
WITH
-- Step 1: join readings to handoff membership + product safe range
readings_with_context AS (
    SELECT
        m.handoff_id,
        m.shipment_id,
        m.reading_id,
        m.reading_at_utc,
        m.corrected_at_utc,
        m.temperature_c,
        m.membership_status,
        m.ambiguity_flag,
        p.min_temp_c,
        p.max_temp_c,
        p.product_id,
        p.allowed_excursion_minutes
    FROM HANDOFFGUARD.v_reading_handoff_membership m
    JOIN HANDOFFGUARD.shipments  s ON m.shipment_id = s.shipment_id
    JOIN HANDOFFGUARD.products   p ON s.product_id  = p.product_id
),
-- Step 2: estimate interval per reading (minutes between this and next reading in same handoff)
readings_with_interval AS (
    SELECT
        handoff_id,
        shipment_id,
        reading_id,
        corrected_at_utc,
        temperature_c,
        membership_status,
        ambiguity_flag,
        min_temp_c,
        max_temp_c,
        product_id,
        -- Interval = seconds to next reading in same handoff ÷ 60, default 5 min if last
        COALESCE(
            SECONDS_BETWEEN(
                corrected_at_utc,
                LEAD(corrected_at_utc) OVER (
                    PARTITION BY handoff_id
                    ORDER BY corrected_at_utc
                )
            ) / 60.0,
            5.0   -- assume 5-minute interval for the last reading in a window
        )                               AS interval_minutes
    FROM readings_with_context
)
-- Step 3: aggregate per handoff
SELECT
    ri.handoff_id,
    h.shipment_id,
    h.sequence_no,
    h.handoff_type,
    h.from_party,
    h.to_party,
    h.location,
    h.window_start_utc,
    h.window_end_utc,
    SECONDS_BETWEEN(h.window_start_utc, h.window_end_utc) / 60.0   AS window_duration_minutes,
    COUNT(ri.reading_id)                                            AS reading_count,
    MIN(ri.temperature_c)                                           AS min_temp_c,
    MAX(ri.temperature_c)                                           AS max_temp_c,
    AVG(ri.temperature_c)                                           AS avg_temp_c,
    MIN(ri.min_temp_c)                                              AS safe_min_temp_c,
    MIN(ri.max_temp_c)                                              AS safe_max_temp_c,
    -- Minutes above safe max
    SUM(CASE WHEN ri.temperature_c > ri.max_temp_c
             THEN ri.interval_minutes ELSE 0 END)                   AS minutes_above_safe,
    -- Minutes below safe min
    SUM(CASE WHEN ri.temperature_c < ri.min_temp_c
             THEN ri.interval_minutes ELSE 0 END)                   AS minutes_below_safe,
    -- Degree-minutes above (area above safe max)
    SUM(CASE WHEN ri.temperature_c > ri.max_temp_c
             THEN (ri.temperature_c - ri.max_temp_c) * ri.interval_minutes
             ELSE 0 END)                                            AS degree_minutes_above,
    -- Degree-minutes below (area below safe min, as positive number)
    SUM(CASE WHEN ri.temperature_c < ri.min_temp_c
             THEN (ri.min_temp_c - ri.temperature_c) * ri.interval_minutes
             ELSE 0 END)                                            AS degree_minutes_below,
    -- Ambiguous reading count
    SUM(CASE WHEN ri.ambiguity_flag THEN 1 ELSE 0 END)              AS ambiguous_reading_count,
    -- Severity classification
    CASE
        WHEN SUM(CASE WHEN ri.temperature_c > ri.max_temp_c
                      THEN (ri.temperature_c - ri.max_temp_c) * ri.interval_minutes
                      ELSE 0 END) > 100  THEN 'critical'
        WHEN SUM(CASE WHEN ri.temperature_c > ri.max_temp_c
                      THEN (ri.temperature_c - ri.max_temp_c) * ri.interval_minutes
                      ELSE 0 END) > 20   THEN 'high'
        WHEN SUM(CASE WHEN ri.temperature_c > ri.max_temp_c
                      THEN (ri.temperature_c - ri.max_temp_c) * ri.interval_minutes
                      ELSE 0 END) > 0    THEN 'medium'
        ELSE 'none'
    END                                                             AS exposure_severity
FROM readings_with_interval ri
JOIN HANDOFFGUARD.handoffs h ON ri.handoff_id = h.handoff_id
GROUP BY
    ri.handoff_id,
    h.shipment_id, h.sequence_no, h.handoff_type, h.from_party,
    h.to_party, h.location, h.window_start_utc, h.window_end_utc;


-- ============================================================
-- VIEW 3: v_excursion_attribution
-- Ranks handoffs by likely contribution to each excursion.
-- Uses degree-minutes overlap + penalties for data-quality
-- issues to produce a defensible attribution score.
--
-- IMPORTANT: This is an investigation aid, not proof.
-- ============================================================
CREATE OR REPLACE VIEW HANDOFFGUARD.v_excursion_attribution AS
WITH
-- Step 1: Candidate handoffs — those whose window overlaps the excursion window
candidates AS (
    SELECT
        e.excursion_id,
        e.shipment_id,
        e.started_at_utc                                    AS exc_start,
        e.ended_at_utc                                      AS exc_end,
        e.peak_temp_c,
        e.duration_minutes                                  AS exc_duration_minutes,
        h.handoff_id,
        h.sequence_no,
        h.handoff_type,
        h.from_party,
        h.to_party,
        h.window_start_utc,
        h.window_end_utc,
        h.clock_skew_seconds,
        -- Overlap duration in minutes
        SECONDS_BETWEEN(
            GREATEST(e.started_at_utc, h.window_start_utc),
            LEAST(e.ended_at_utc,      h.window_end_utc)
        ) / 60.0                                            AS overlap_minutes
    FROM HANDOFFGUARD.excursions e
    JOIN HANDOFFGUARD.handoffs   h ON h.shipment_id = e.shipment_id
    WHERE h.window_start_utc < e.ended_at_utc
      AND h.window_end_utc   > e.started_at_utc
),
-- Step 2: Join with exposure view to get degree-minutes within each candidate handoff
candidates_with_exposure AS (
    SELECT
        c.*,
        COALESCE(exp.degree_minutes_above, 0)               AS handoff_degree_minutes_above,
        COALESCE(exp.degree_minutes_below, 0)               AS handoff_degree_minutes_below,
        COALESCE(exp.reading_count, 0)                      AS reading_count,
        COALESCE(exp.ambiguous_reading_count, 0)            AS ambiguous_reading_count
    FROM candidates c
    LEFT JOIN HANDOFFGUARD.v_handoff_thermal_exposure exp
           ON c.handoff_id = exp.handoff_id
),
-- Step 3: Total degree-minutes per excursion (for share calculation)
excursion_totals AS (
    SELECT
        excursion_id,
        SUM(handoff_degree_minutes_above + handoff_degree_minutes_below) AS total_degree_minutes
    FROM candidates_with_exposure
    GROUP BY excursion_id
)
SELECT
    cwe.excursion_id,
    cwe.shipment_id,
    cwe.handoff_id,
    cwe.sequence_no,
    cwe.handoff_type,
    cwe.from_party,
    cwe.to_party,
    cwe.window_start_utc,
    cwe.window_end_utc,
    cwe.exc_start,
    cwe.exc_end,
    cwe.exc_duration_minutes,
    cwe.overlap_minutes,
    cwe.peak_temp_c,
    cwe.handoff_degree_minutes_above,
    cwe.handoff_degree_minutes_below,
    cwe.reading_count,
    cwe.ambiguous_reading_count,
    et.total_degree_minutes,
    -- Exposure share (fraction of excursion attributed to this handoff)
    CASE
        WHEN et.total_degree_minutes > 0
        THEN (cwe.handoff_degree_minutes_above + cwe.handoff_degree_minutes_below)
             / et.total_degree_minutes
        ELSE 0
    END                                                     AS exposure_share,
    -- Penalties (each reduces the attribution score)
    CASE WHEN ABS(cwe.clock_skew_seconds) > 120 THEN 0.10 ELSE 0 END  AS skew_penalty,
    CASE WHEN cwe.ambiguous_reading_count > 0
         THEN LEAST(0.15, cwe.ambiguous_reading_count * 0.03)          ELSE 0 END
                                                            AS ambiguity_penalty,
    CASE WHEN cwe.reading_count = 0 THEN 0.20 ELSE 0 END   AS missing_data_penalty,
    -- Final attribution score (capped 0–1)
    GREATEST(0.0,
        CASE
            WHEN et.total_degree_minutes > 0
            THEN (cwe.handoff_degree_minutes_above + cwe.handoff_degree_minutes_below)
                 / et.total_degree_minutes
            ELSE 0
        END
        - CASE WHEN ABS(cwe.clock_skew_seconds) > 120 THEN 0.10 ELSE 0 END
        - CASE WHEN cwe.ambiguous_reading_count > 0
               THEN LEAST(0.15, cwe.ambiguous_reading_count * 0.03) ELSE 0 END
        - CASE WHEN cwe.reading_count = 0 THEN 0.20 ELSE 0 END
    )                                                       AS attribution_score,
    -- Confidence level
    CASE
        WHEN GREATEST(0.0,
            CASE WHEN et.total_degree_minutes > 0
                 THEN (cwe.handoff_degree_minutes_above + cwe.handoff_degree_minutes_below)
                      / et.total_degree_minutes ELSE 0 END
            - CASE WHEN ABS(cwe.clock_skew_seconds) > 120 THEN 0.10 ELSE 0 END
            - CASE WHEN cwe.ambiguous_reading_count > 0
                   THEN LEAST(0.15, cwe.ambiguous_reading_count * 0.03) ELSE 0 END
            - CASE WHEN cwe.reading_count = 0 THEN 0.20 ELSE 0 END
        ) >= 0.60                                           THEN 'high'
        WHEN GREATEST(0.0,
            CASE WHEN et.total_degree_minutes > 0
                 THEN (cwe.handoff_degree_minutes_above + cwe.handoff_degree_minutes_below)
                      / et.total_degree_minutes ELSE 0 END
            - CASE WHEN ABS(cwe.clock_skew_seconds) > 120 THEN 0.10 ELSE 0 END
            - CASE WHEN cwe.ambiguous_reading_count > 0
                   THEN LEAST(0.15, cwe.ambiguous_reading_count * 0.03) ELSE 0 END
            - CASE WHEN cwe.reading_count = 0 THEN 0.20 ELSE 0 END
        ) >= 0.35                                           THEN 'medium'
        WHEN et.total_degree_minutes = 0                   THEN 'inconclusive'
        ELSE                                                     'low'
    END                                                     AS confidence_level
FROM candidates_with_exposure cwe
JOIN excursion_totals et ON cwe.excursion_id = et.excursion_id;
