-- ============================================================
-- HandoffGuard — Master Exasol Setup Script
-- ExaThon India 2026 | Pharmaceutical Cold-Chain Attribution
-- ============================================================
-- This script creates the complete database schema for HandoffGuard,
-- including core entity tables, aliases/views for shipment_legs and
-- temperature_telemetry, and the analytical interval-join views.
--
-- IMPORTANT CONSTRAINT:
-- logger_readings has NO handoff_id column.
-- Reading-to-handoff association is derived strictly via interval join on time.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS HANDOFFGUARD;
OPEN SCHEMA HANDOFFGUARD;

-- ------------------------------------------------------------
-- Table: products
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.products (
    product_id                DECIMAL(18,0)   NOT NULL,
    name                      VARCHAR(200)    NOT NULL,
    min_temp_c                DOUBLE          NOT NULL,
    max_temp_c                DOUBLE          NOT NULL,
    allowed_excursion_minutes INTEGER         NOT NULL,
    thermal_mass_class        VARCHAR(50)     NOT NULL,
    created_at                TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_products PRIMARY KEY (product_id)
);

-- ------------------------------------------------------------
-- Table: shipments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.shipments (
    shipment_id               DECIMAL(18,0)   NOT NULL,
    shipment_code             VARCHAR(100)    NOT NULL,
    product_id                DECIMAL(18,0)   NOT NULL,
    origin                    VARCHAR(200)    NOT NULL,
    destination               VARCHAR(200)    NOT NULL,
    dispatched_at             TIMESTAMP       NOT NULL,
    expected_delivery_at      TIMESTAMP       NOT NULL,
    status                    VARCHAR(50)     NOT NULL,
    created_at                TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_shipments PRIMARY KEY (shipment_id),
    CONSTRAINT uq_shipment_code UNIQUE (shipment_code),
    CONSTRAINT fk_shipment_product FOREIGN KEY (product_id)
        REFERENCES HANDOFFGUARD.products(product_id)
);

-- ------------------------------------------------------------
-- Table: handoffs (shipment legs)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.handoffs (
    handoff_id                DECIMAL(18,0)   NOT NULL,
    shipment_id               DECIMAL(18,0)   NOT NULL,
    sequence_no               INTEGER         NOT NULL,
    handoff_type              VARCHAR(50)     NOT NULL,
    from_party                VARCHAR(200)    NOT NULL,
    to_party                  VARCHAR(200)    NOT NULL,
    location                  VARCHAR(200)    NOT NULL,
    window_start_utc          TIMESTAMP       NOT NULL,
    window_end_utc            TIMESTAMP       NOT NULL,
    reported_start_utc        TIMESTAMP,
    reported_end_utc          TIMESTAMP,
    clock_skew_seconds        DOUBLE          DEFAULT 0,
    dwell_minutes             DOUBLE          DEFAULT 0,
    created_at                TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_handoffs PRIMARY KEY (handoff_id),
    CONSTRAINT fk_handoff_shipment FOREIGN KEY (shipment_id)
        REFERENCES HANDOFFGUARD.shipments(shipment_id)
);

-- Compatibility view: shipment_legs -> handoffs
CREATE OR REPLACE VIEW HANDOFFGUARD.shipment_legs AS
SELECT
    handoff_id       AS leg_id,
    handoff_id,
    shipment_id,
    sequence_no,
    handoff_type     AS leg_type,
    from_party,
    to_party,
    location,
    window_start_utc,
    window_end_utc,
    reported_start_utc,
    reported_end_utc,
    clock_skew_seconds,
    dwell_minutes,
    created_at
FROM HANDOFFGUARD.handoffs;

-- ------------------------------------------------------------
-- Table: logger_devices
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.logger_devices (
    logger_id                 DECIMAL(18,0)   NOT NULL,
    device_code               VARCHAR(100)    NOT NULL,
    model                     VARCHAR(100)    NOT NULL,
    firmware                  VARCHAR(50),
    assigned_shipment_id      DECIMAL(18,0)   NOT NULL,
    clock_skew_seconds        DOUBLE          DEFAULT 0,
    data_quality_flag         VARCHAR(50)     DEFAULT 'good',
    created_at                TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_logger_devices PRIMARY KEY (logger_id),
    CONSTRAINT fk_logger_shipment FOREIGN KEY (assigned_shipment_id)
        REFERENCES HANDOFFGUARD.shipments(shipment_id)
);

-- ------------------------------------------------------------
-- Table: logger_readings
-- CRITICAL REQUIREMENT: NO handoff_id column
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.logger_readings (
    reading_id                DECIMAL(18,0)   NOT NULL,
    logger_id                 DECIMAL(18,0)   NOT NULL,
    reading_at_utc            TIMESTAMP       NOT NULL,
    temperature_c             DOUBLE          NOT NULL,
    battery_pct               DOUBLE,
    created_at                TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_logger_readings PRIMARY KEY (reading_id),
    CONSTRAINT fk_reading_logger FOREIGN KEY (logger_id)
        REFERENCES HANDOFFGUARD.logger_devices(logger_id)
);

-- Compatibility view: temperature_telemetry -> logger_readings
CREATE OR REPLACE VIEW HANDOFFGUARD.temperature_telemetry AS
SELECT
    reading_id        AS telemetry_id,
    reading_id,
    logger_id,
    reading_at_utc    AS recorded_at_utc,
    reading_at_utc,
    temperature_c,
    battery_pct,
    created_at
FROM HANDOFFGUARD.logger_readings;

-- ------------------------------------------------------------
-- Table: excursions
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.excursions (
    excursion_id              DECIMAL(18,0)   NOT NULL,
    shipment_id               DECIMAL(18,0)   NOT NULL,
    product_id                DECIMAL(18,0)   NOT NULL,
    started_at_utc            TIMESTAMP       NOT NULL,
    ended_at_utc              TIMESTAMP       NOT NULL,
    min_temp_c                DOUBLE,
    max_temp_c                DOUBLE,
    peak_temp_c               DOUBLE          NOT NULL,
    duration_minutes          DOUBLE          NOT NULL,
    severity                  VARCHAR(50)     NOT NULL,
    detected_by               VARCHAR(100)    DEFAULT 'system',
    ground_truth_handoff_id   DECIMAL(18,0),
    ground_truth_cause        VARCHAR(500),
    created_at                TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_excursions PRIMARY KEY (excursion_id),
    CONSTRAINT fk_excursion_shipment FOREIGN KEY (shipment_id)
        REFERENCES HANDOFFGUARD.shipments(shipment_id),
    CONSTRAINT fk_excursion_product FOREIGN KEY (product_id)
        REFERENCES HANDOFFGUARD.products(product_id)
);

-- ------------------------------------------------------------
-- Table: attribution_results
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.attribution_results (
    excursion_id              DECIMAL(18,0)   NOT NULL,
    handoff_id                DECIMAL(18,0)   NOT NULL,
    exposure_degree_minutes   DOUBLE          NOT NULL,
    exposure_share_pct        DOUBLE          NOT NULL,
    confidence_score          DOUBLE          NOT NULL,
    confidence_label          VARCHAR(50)     NOT NULL,
    evidence_json             VARCHAR(4000)   NOT NULL,
    created_at                TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_attribution PRIMARY KEY (excursion_id, handoff_id)
);

-- ------------------------------------------------------------
-- Table: prevention_suggestions
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.prevention_suggestions (
    shipment_id               DECIMAL(18,0)   NOT NULL,
    handoff_id                DECIMAL(18,0)   NOT NULL,
    risk_score                DOUBLE          NOT NULL,
    suggestion                VARCHAR(1000)   NOT NULL,
    rationale                 VARCHAR(1000)   NOT NULL,
    prototype_flag            BOOLEAN         DEFAULT TRUE,
    created_at                TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_prevention PRIMARY KEY (shipment_id, handoff_id)
);

-- ============================================================
-- ANALYTICAL VIEWS
-- ============================================================

-- 1. Interval Join: v_reading_handoff_membership
CREATE OR REPLACE VIEW HANDOFFGUARD.v_reading_handoff_membership AS
WITH
corrected AS (
    SELECT
        r.reading_id,
        r.logger_id,
        r.reading_at_utc,
        ADD_SECONDS(r.reading_at_utc, -ld.clock_skew_seconds) AS corrected_at_utc,
        r.temperature_c,
        r.battery_pct,
        ld.assigned_shipment_id,
        ld.clock_skew_seconds
    FROM HANDOFFGUARD.logger_readings r
    JOIN HANDOFFGUARD.logger_devices ld ON r.logger_id = ld.logger_id
),
matched AS (
    SELECT
        c.reading_id,
        c.logger_id,
        c.reading_at_utc,
        c.corrected_at_utc,
        c.temperature_c,
        c.battery_pct,
        c.assigned_shipment_id AS shipment_id,
        c.clock_skew_seconds,
        h.handoff_id,
        h.handoff_type,
        h.from_party,
        h.to_party,
        h.window_start_utc,
        h.window_end_utc,
        CASE
            WHEN c.corrected_at_utc < h.window_start_utc
                THEN SECONDS_BETWEEN(c.corrected_at_utc, h.window_start_utc)
            WHEN c.corrected_at_utc > h.window_end_utc
                THEN SECONDS_BETWEEN(h.window_end_utc, c.corrected_at_utc)
            ELSE 0
        END AS boundary_skew_seconds
    FROM corrected c
    JOIN HANDOFFGUARD.handoffs h
        ON h.shipment_id = c.assigned_shipment_id
        AND c.corrected_at_utc
            BETWEEN ADD_SECONDS(h.window_start_utc, -120)
                AND ADD_SECONDS(h.window_end_utc, 120)
),
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
    m.clock_skew_seconds AS skew_seconds,
    m.boundary_skew_seconds,
    mc.match_count,
    CASE
        WHEN mc.match_count > 1 THEN 'ambiguous'
        WHEN m.boundary_skew_seconds > 0 THEN 'matched_with_skew'
        ELSE 'matched'
    END AS membership_status,
    CASE WHEN mc.match_count > 1 THEN TRUE ELSE FALSE END AS ambiguity_flag
FROM matched m
JOIN match_counts mc ON m.reading_id = mc.reading_id;

-- 2. Exposure view: v_handoff_thermal_exposure
CREATE OR REPLACE VIEW HANDOFFGUARD.v_handoff_thermal_exposure AS
WITH
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
    JOIN HANDOFFGUARD.shipments s ON m.shipment_id = s.shipment_id
    JOIN HANDOFFGUARD.products p ON s.product_id = p.product_id
),
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
        COALESCE(
            SECONDS_BETWEEN(
                corrected_at_utc,
                LEAD(corrected_at_utc) OVER (
                    PARTITION BY handoff_id
                    ORDER BY corrected_at_utc
                )
            ) / 60.0,
            5.0
        ) AS interval_minutes
    FROM readings_with_context
)
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
    SECONDS_BETWEEN(h.window_start_utc, h.window_end_utc) / 60.0 AS window_duration_minutes,
    COUNT(ri.reading_id) AS reading_count,
    MIN(ri.temperature_c) AS min_temp_c,
    MAX(ri.temperature_c) AS max_temp_c,
    AVG(ri.temperature_c) AS avg_temp_c,
    MIN(ri.min_temp_c) AS safe_min_temp_c,
    MIN(ri.max_temp_c) AS safe_max_temp_c,
    SUM(CASE WHEN ri.temperature_c > ri.max_temp_c
             THEN ri.interval_minutes ELSE 0 END) AS minutes_above_safe,
    SUM(CASE WHEN ri.temperature_c < ri.min_temp_c
             THEN ri.interval_minutes ELSE 0 END) AS minutes_below_safe,
    SUM(CASE WHEN ri.temperature_c > ri.max_temp_c
             THEN (ri.temperature_c - ri.max_temp_c) * ri.interval_minutes
             ELSE 0 END) AS degree_minutes_above,
    SUM(CASE WHEN ri.temperature_c < ri.min_temp_c
             THEN (ri.min_temp_c - ri.temperature_c) * ri.interval_minutes
             ELSE 0 END) AS degree_minutes_below,
    SUM(CASE WHEN ri.ambiguity_flag THEN 1 ELSE 0 END) AS ambiguous_reading_count,
    CASE
        WHEN SUM(CASE WHEN ri.temperature_c > ri.max_temp_c
                      THEN (ri.temperature_c - ri.max_temp_c) * ri.interval_minutes
                      ELSE 0 END) > 100 THEN 'critical'
        WHEN SUM(CASE WHEN ri.temperature_c > ri.max_temp_c
                      THEN (ri.temperature_c - ri.max_temp_c) * ri.interval_minutes
                      ELSE 0 END) > 20 THEN 'high'
        WHEN SUM(CASE WHEN ri.temperature_c > ri.max_temp_c
                      THEN (ri.temperature_c - ri.max_temp_c) * ri.interval_minutes
                      ELSE 0 END) > 0 THEN 'medium'
        ELSE 'none'
    END AS exposure_severity
FROM readings_with_interval ri
JOIN HANDOFFGUARD.handoffs h ON ri.handoff_id = h.handoff_id
GROUP BY
    ri.handoff_id,
    h.shipment_id, h.sequence_no, h.handoff_type, h.from_party,
    h.to_party, h.location, h.window_start_utc, h.window_end_utc;

-- 3. Attribution view: v_excursion_attribution
CREATE OR REPLACE VIEW HANDOFFGUARD.v_excursion_attribution AS
WITH
candidates AS (
    SELECT
        e.excursion_id,
        e.shipment_id,
        e.started_at_utc AS exc_start,
        e.ended_at_utc AS exc_end,
        e.peak_temp_c,
        e.duration_minutes AS exc_duration_minutes,
        h.handoff_id,
        h.sequence_no,
        h.handoff_type,
        h.from_party,
        h.to_party,
        h.window_start_utc,
        h.window_end_utc,
        h.clock_skew_seconds,
        SECONDS_BETWEEN(
            GREATEST(e.started_at_utc, h.window_start_utc),
            LEAST(e.ended_at_utc, h.window_end_utc)
        ) / 60.0 AS overlap_minutes
    FROM HANDOFFGUARD.excursions e
    JOIN HANDOFFGUARD.handoffs h ON h.shipment_id = e.shipment_id
    WHERE h.window_start_utc < e.ended_at_utc
      AND h.window_end_utc > e.started_at_utc
),
candidates_with_exposure AS (
    SELECT
        c.*,
        COALESCE(exp.degree_minutes_above, 0) AS handoff_degree_minutes_above,
        COALESCE(exp.degree_minutes_below, 0) AS handoff_degree_minutes_below,
        COALESCE(exp.reading_count, 0) AS reading_count,
        COALESCE(exp.ambiguous_reading_count, 0) AS ambiguous_reading_count
    FROM candidates c
    LEFT JOIN HANDOFFGUARD.v_handoff_thermal_exposure exp
           ON c.handoff_id = exp.handoff_id
),
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
    CASE
        WHEN et.total_degree_minutes > 0
        THEN (cwe.handoff_degree_minutes_above + cwe.handoff_degree_minutes_below)
             / et.total_degree_minutes
        ELSE 0
    END AS exposure_share,
    CASE WHEN ABS(cwe.clock_skew_seconds) > 120 THEN 0.10 ELSE 0 END AS skew_penalty,
    CASE WHEN cwe.ambiguous_reading_count > 0
         THEN LEAST(0.15, cwe.ambiguous_reading_count * 0.03) ELSE 0 END AS ambiguity_penalty,
    CASE WHEN cwe.reading_count = 0 THEN 0.20 ELSE 0 END AS missing_data_penalty,
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
    ) AS attribution_score,
    CASE
        WHEN GREATEST(0.0,
            CASE WHEN et.total_degree_minutes > 0
                 THEN (cwe.handoff_degree_minutes_above + cwe.handoff_degree_minutes_below)
                      / et.total_degree_minutes ELSE 0 END
            - CASE WHEN ABS(cwe.clock_skew_seconds) > 120 THEN 0.10 ELSE 0 END
            - CASE WHEN cwe.ambiguous_reading_count > 0
                   THEN LEAST(0.15, cwe.ambiguous_reading_count * 0.03) ELSE 0 END
            - CASE WHEN cwe.reading_count = 0 THEN 0.20 ELSE 0 END
        ) >= 0.60 THEN 'high'
        WHEN GREATEST(0.0,
            CASE WHEN et.total_degree_minutes > 0
                 THEN (cwe.handoff_degree_minutes_above + cwe.handoff_degree_minutes_below)
                      / et.total_degree_minutes ELSE 0 END
            - CASE WHEN ABS(cwe.clock_skew_seconds) > 120 THEN 0.10 ELSE 0 END
            - CASE WHEN cwe.ambiguous_reading_count > 0
                   THEN LEAST(0.15, cwe.ambiguous_reading_count * 0.03) ELSE 0 END
            - CASE WHEN cwe.reading_count = 0 THEN 0.20 ELSE 0 END
        ) >= 0.35 THEN 'medium'
        WHEN et.total_degree_minutes = 0 THEN 'inconclusive'
        ELSE 'low'
    END AS confidence_level
FROM candidates_with_exposure cwe
JOIN excursion_totals et ON cwe.excursion_id = et.excursion_id;
