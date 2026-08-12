# Phase D — Datetime Integrity Plan

## Problem

All timestamp/datetime columns use `TEXT` (ISO-8601 strings) instead of native PostgreSQL `TIMESTAMP WITH TIME ZONE`. This means:
- No DB-level date arithmetic (can't use `+ INTERVAL '30 days'`)
- No timezone awareness (all strings are UTC, but the DB doesn't enforce it)
- No automatic `updated_at` maintenance
- No DB-level validation of timestamp format

## Scope

Convert the most critical operational timestamp columns. Full conversion of ALL tables is impractical in one phase.

## Target PostgreSQL Type

`TIMESTAMP WITH TIME ZONE` (also known as `TIMESTAMPTZ`)

## SQLite Strategy

SQLite has no native datetime type — `TEXT` ISO-8601 is the standard pattern. Keep `TEXT` for SQLite.

## Critical Tables to Migrate (Phase D)

### Priority 1: Operational timestamps

| Table | Column(s) | Why |
|-------|-----------|-----|
| trips | created_at, start_date, end_date, payment_date, deleted_at | Core scheduling |
| invoices | issue_date, due_date, created_at, updated_at, paid_at | Financial compliance |
| route_history_v2 | created_at, last_calculated_at, archived_at | Route planning |
| gps_telemetry | recorded_at, created_at | Fleet tracking |
| operation_events | created_at | Audit trail |

### Priority 2: Maintenance & tracking

| Table | Column(s) | Why |
|-------|-----------|-----|
| truck_route_assignments | assigned_at, started_at, completed_at, archived_at | Dispatch |
| trip_status_history | created_at | Status tracking |
| alerts | created_at, resolved_at | Alerting |
| documents | uploaded_at, updated_at, expiry_date | Document management |

### Priority 3: Everything else (future)
Remaining ~40 tables with ~80 timestamp columns. Deferred.

## `updated_at` Trigger

Create a PostgreSQL function and trigger for automatic `updated_at` maintenance:

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW() AT TIME ZONE 'UTC';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_trips_updated_at
    BEFORE UPDATE ON trips
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

Apply to all tables that have an `updated_at` column.

## Migration Strategy

1 Alembic migration that:
- Creates `update_updated_at_column()` function
- For each priority-1 column: `ALTER COLUMN ... TYPE TIMESTAMPTZ USING ...`
- Handles empty string timestamps (`USING CASE WHEN column = '' THEN NULL ELSE column::TIMESTAMPTZ END`)
- Adds `updated_at` triggers where applicable
- Is reversible

## Risk

- Empty string timestamps in existing data will fail `::TIMESTAMPTZ` cast
- Data before the year 1582 (Gregorian calendar) may fail
- Text timestamps without timezone info will be treated as local time by PostgreSQL
