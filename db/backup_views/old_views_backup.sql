-- ============================================================
-- HandoffGuard: Backup of Existing Exasol Views
-- Backed up on: 2026-10-31
-- Schema: HANDOFFGUARD
-- ============================================================

OPEN SCHEMA HANDOFFGUARD;

-- ------------------------------------------------------------
-- View 1: v_reading_handoff_membership
-- ------------------------------------------------------------
-- Original definition dumped directly from SYS.EXA_ALL_VIEWS
CREATE OR REPLACE VIEW v_reading_handoff_membership AS
SELECT 
    r.reading_id,
    r.logger_id,
    r.reading_at_utc,
    r.temperature_c,
    d.assigned_shipment_id AS shipment_id,
    h.id AS handoff_id,
    h.from_party AS handler_name,
    h.handoff_type AS transport_mode,
    CASE 
        WHEN h.id IS NOT NULL THEN 'MATCHED'
        ELSE 'UNMATCHED'
    END AS membership_status
FROM logger_readings r
JOIN logger_devices d ON r.logger_id = d.logger_id
LEFT JOIN handoffs h ON d.assigned_shipment_id = h.shipment_id
    AND r.reading_at_utc >= h.actual_start_at
    AND r.reading_at_utc <= h.actual_end_at;

-- ------------------------------------------------------------
-- View 2: v_handoff_thermal_exposure
-- ------------------------------------------------------------
-- Original definition dumped directly from SYS.EXA_ALL_VIEWS
CREATE OR REPLACE VIEW v_handoff_thermal_exposure AS
SELECT 
    shipment_id,
    handoff_id,
    handler_name,
    transport_mode,
    COUNT(*) AS total_readings,
    ROUND(MIN(temperature_c), 2) AS min_recorded_temp,
    ROUND(MAX(temperature_c), 2) AS max_recorded_temp,
    ROUND(AVG(temperature_c), 2) AS avg_recorded_temp,
    ROUND(SUM(CASE WHEN temperature_c > 8.0 THEN (temperature_c - 8.0) * 5 ELSE 0 END), 2) AS degree_minutes_above,
    ROUND(SUM(CASE WHEN temperature_c < 2.0 THEN (2.0 - temperature_c) * 5 ELSE 0 END), 2) AS degree_minutes_below
FROM v_reading_handoff_membership
GROUP BY shipment_id, handoff_id, handler_name, transport_mode;

-- ------------------------------------------------------------
-- View 3: v_excursion_attribution
-- ------------------------------------------------------------
-- Original definition dumped directly from SYS.EXA_ALL_VIEWS
CREATE OR REPLACE VIEW v_excursion_attribution AS
SELECT 
    e.excursion_id,
    e.shipment_id,
    te.handoff_id,
    te.handler_name AS liable_party,
    te.transport_mode,
    te.degree_minutes_above,
    RANK() OVER (PARTITION BY e.excursion_id ORDER BY te.degree_minutes_above DESC) AS risk_rank,
    CASE 
        WHEN te.degree_minutes_above > 500 THEN 'HIGH'
        WHEN te.degree_minutes_above > 100 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS liability_confidence
FROM excursions e
JOIN v_handoff_thermal_exposure te ON e.shipment_id = te.shipment_id
WHERE te.degree_minutes_above > 0;
