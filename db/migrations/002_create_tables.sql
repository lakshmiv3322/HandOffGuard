-- ============================================================
-- HandoffGuard — Migration 002: Create Tables
-- ExaThon India 2026 | Exasol Personal
-- ============================================================
-- IMPORTANT: logger_readings has NO handoff_id column.
-- Handoff assignment is derived at query time via interval join.
-- Run after 001_create_schema.sql

OPEN SCHEMA HANDOFFGUARD;

-- ------------------------------------------------------------
-- products
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.products (
    product_id              DECIMAL(18,0)   NOT NULL,
    name                    VARCHAR(200)    NOT NULL,
    min_temp_c              DOUBLE          NOT NULL,
    max_temp_c              DOUBLE          NOT NULL,
    allowed_excursion_minutes INTEGER       NOT NULL,
    thermal_mass_class      VARCHAR(50)     NOT NULL,
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_products PRIMARY KEY (product_id)
);

-- ------------------------------------------------------------
-- shipments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.shipments (
    shipment_id             DECIMAL(18,0)   NOT NULL,
    shipment_code           VARCHAR(100)    NOT NULL,
    product_id              DECIMAL(18,0)   NOT NULL,
    origin                  VARCHAR(200)    NOT NULL,
    destination             VARCHAR(200)    NOT NULL,
    dispatched_at           TIMESTAMP       NOT NULL,
    expected_delivery_at    TIMESTAMP       NOT NULL,
    status                  VARCHAR(50)     NOT NULL,
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_shipments  PRIMARY KEY (shipment_id),
    CONSTRAINT uq_shipment_code UNIQUE (shipment_code),
    CONSTRAINT fk_shipment_product FOREIGN KEY (product_id)
        REFERENCES HANDOFFGUARD.products(product_id)
);

-- ------------------------------------------------------------
-- handoffs
-- Each row is one custody segment. window_start/end are the
-- actual windows used for interval joins; reported_start/end
-- are what the party self-reported (used for skew detection).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.handoffs (
    handoff_id              DECIMAL(18,0)   NOT NULL,
    shipment_id             DECIMAL(18,0)   NOT NULL,
    sequence_no             INTEGER         NOT NULL,
    handoff_type            VARCHAR(50)     NOT NULL,
    from_party              VARCHAR(200)    NOT NULL,
    to_party                VARCHAR(200)    NOT NULL,
    location                VARCHAR(200)    NOT NULL,
    window_start_utc        TIMESTAMP       NOT NULL,
    window_end_utc          TIMESTAMP       NOT NULL,
    reported_start_utc      TIMESTAMP,
    reported_end_utc        TIMESTAMP,
    clock_skew_seconds      DOUBLE          DEFAULT 0,
    dwell_minutes           DOUBLE          DEFAULT 0,
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_handoffs  PRIMARY KEY (handoff_id),
    CONSTRAINT fk_handoff_shipment FOREIGN KEY (shipment_id)
        REFERENCES HANDOFFGUARD.shipments(shipment_id)
);

-- ------------------------------------------------------------
-- logger_devices
-- Physical temperature loggers. assigned_shipment_id links
-- a device to the shipment it is tracking.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.logger_devices (
    logger_id               DECIMAL(18,0)   NOT NULL,
    device_code             VARCHAR(100)    NOT NULL,
    model                   VARCHAR(100)    NOT NULL,
    firmware                VARCHAR(50),
    assigned_shipment_id    DECIMAL(18,0)   NOT NULL,
    clock_skew_seconds      DOUBLE          DEFAULT 0,
    data_quality_flag       VARCHAR(50)     DEFAULT 'good',
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_logger_devices PRIMARY KEY (logger_id),
    CONSTRAINT fk_logger_shipment FOREIGN KEY (assigned_shipment_id)
        REFERENCES HANDOFFGUARD.shipments(shipment_id)
);

-- ------------------------------------------------------------
-- logger_readings
-- *** CRITICAL CONSTRAINT: NO handoff_id column. ***
-- Handoff association is computed at query time by checking
-- whether reading_at_utc falls within a handoff's window.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.logger_readings (
    reading_id              DECIMAL(18,0)   NOT NULL,
    logger_id               DECIMAL(18,0)   NOT NULL,
    reading_at_utc          TIMESTAMP       NOT NULL,
    temperature_c           DOUBLE          NOT NULL,
    battery_pct             DOUBLE,
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_logger_readings PRIMARY KEY (reading_id),
    CONSTRAINT fk_reading_logger FOREIGN KEY (logger_id)
        REFERENCES HANDOFFGUARD.logger_devices(logger_id)
);

-- ------------------------------------------------------------
-- excursions
-- A detected temperature excursion event.
-- ground_truth_handoff_id is populated only in demo/test data
-- where the injected fault location is known.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.excursions (
    excursion_id            DECIMAL(18,0)   NOT NULL,
    shipment_id             DECIMAL(18,0)   NOT NULL,
    product_id              DECIMAL(18,0)   NOT NULL,
    started_at_utc          TIMESTAMP       NOT NULL,
    ended_at_utc            TIMESTAMP       NOT NULL,
    min_temp_c              DOUBLE,
    max_temp_c              DOUBLE,
    peak_temp_c             DOUBLE          NOT NULL,
    duration_minutes        DOUBLE          NOT NULL,
    severity                VARCHAR(50)     NOT NULL,
    detected_by             VARCHAR(100)    DEFAULT 'system',
    ground_truth_handoff_id DECIMAL(18,0),
    ground_truth_cause      VARCHAR(500),
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_excursions PRIMARY KEY (excursion_id),
    CONSTRAINT fk_excursion_shipment FOREIGN KEY (shipment_id)
        REFERENCES HANDOFFGUARD.shipments(shipment_id),
    CONSTRAINT fk_excursion_product FOREIGN KEY (product_id)
        REFERENCES HANDOFFGUARD.products(product_id)
);

-- ------------------------------------------------------------
-- attribution_results
-- Persisted scores from the attribution engine.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.attribution_results (
    excursion_id            DECIMAL(18,0)   NOT NULL,
    handoff_id              DECIMAL(18,0)   NOT NULL,
    exposure_degree_minutes DOUBLE          NOT NULL,
    exposure_share_pct      DOUBLE          NOT NULL,
    confidence_score        DOUBLE          NOT NULL,
    confidence_label        VARCHAR(50)     NOT NULL,
    evidence_json           VARCHAR(4000)   NOT NULL,
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_attribution PRIMARY KEY (excursion_id, handoff_id)
);

-- ------------------------------------------------------------
-- prevention_suggestions
-- Rule-based prevention hints for upcoming handoffs.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HANDOFFGUARD.prevention_suggestions (
    shipment_id             DECIMAL(18,0)   NOT NULL,
    handoff_id              DECIMAL(18,0)   NOT NULL,
    risk_score              DOUBLE          NOT NULL,
    suggestion              VARCHAR(1000)   NOT NULL,
    rationale               VARCHAR(1000)   NOT NULL,
    prototype_flag          BOOLEAN         DEFAULT TRUE,
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_prevention PRIMARY KEY (shipment_id, handoff_id)
);
