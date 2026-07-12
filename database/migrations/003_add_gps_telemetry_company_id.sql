-- Migration 003: Add company_id to gps_telemetry for multi-tenant isolation
ALTER TABLE gps_telemetry ADD COLUMN company_id INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_gps_telemetry_company_id ON gps_telemetry(company_id);
