-- ============================================================
-- HandoffGuard — Migration 003: Create Indexes
-- ExaThon India 2026 | Exasol Personal
-- ============================================================
-- Exasol is a columnar MPP database. Traditional row-store
-- indexes do not apply. Exasol uses distribution keys and
-- sort keys instead. These statements create the optimal
-- distribution keys for the interval join workload.
--
-- NOTE: In Exasol, CREATE INDEX syntax is not supported.
-- Performance is achieved through proper distribution keys
-- (set at table creation) and Exasol's columnar architecture.
-- This migration documents the distribution strategy and
-- adds any valid Exasol performance hints.
--
-- The tables in 002_create_tables.sql use default distribution.
-- For production, recreate tables with explicit DISTRIBUTE BY
-- clauses as shown below (kept as comments for reference):
--
-- HANDOFFGUARD.logger_readings DISTRIBUTE BY logger_id
-- HANDOFFGUARD.handoffs        DISTRIBUTE BY shipment_id
-- HANDOFFGUARD.shipments       DISTRIBUTE BY product_id
-- HANDOFFGUARD.excursions      DISTRIBUTE BY shipment_id
--
-- This file is intentionally minimal because Exasol Personal
-- (single-node) does not benefit from distribution keys but
-- does benefit from Exasol's built-in columnar compression
-- and zone-map pruning which applies automatically.

-- Verify tables exist (safe no-op query)
SELECT
    TABLE_NAME,
    ROW_COUNT
FROM SYS.EXA_ALL_TABLES
WHERE TABLE_SCHEMA = 'HANDOFFGUARD'
ORDER BY TABLE_NAME;
