-- ============================================================
-- HandoffGuard — Migration 001: Create Schema
-- ExaThon India 2026 | Exasol Personal
-- ============================================================
-- Run this as SYS or a user with CREATE SCHEMA privilege.
-- Safe to rerun: schema creation is skipped if it already exists.

CREATE SCHEMA IF NOT EXISTS HANDOFFGUARD;

-- Set default schema for subsequent statements
OPEN SCHEMA HANDOFFGUARD;
