# Phase C — Financial Precision Migration Plan

## Problem

All monetary columns use `REAL` (SQLite) / `DOUBLE PRECISION` (PostgreSQL), which are IEEE 754 binary floating-point types. These cannot represent decimal fractions like 0.01 exactly, causing rounding errors in VAT calculations, invoice totals, and profit computations. For an ERP handling invoices, VAT returns, and financial reporting, this is unacceptable.

## Target PostgreSQL Type

`NUMERIC(12,2)` for monetary columns — exact decimal with 12 significant digits, 2 decimal places.

Exceptions:
- `exchange_rate`: `NUMERIC(8,6)` (exchange rates need higher precision)
- `vat_percent`, `tax_rate`: `NUMERIC(5,2)` (percentages)
- `match_confidence`: `NUMERIC(5,4)` (ML confidence scores)
- `fuel_consumption`, `mileage`, `distance_km`, `duration_min`, `speed_kmh`, `latitude`, `longitude`: keep `DOUBLE PRECISION` (measurement data, not money)
- `compliance_pct`: `NUMERIC(5,2)` (percentage)
- `gross_weight_kg`, `volume_m3`, `max_payload_kg`, `odometer_km`, `interval_km`, `last_done_km`, `km_at_service`, `km`: keep `DOUBLE PRECISION` (measurements, not money)

## SQLite Strategy

SQLite ignores column type declarations for numeric precision — everything is stored as IEEE 64-bit float internally. The precision safety net is at the **application layer** (Pydantic `Decimal` model fields). The SQLite schema file will use `REAL` for backward compatibility; the new `Decimal` Pydantic fields prevent precision loss in Python before values reach the DB.

## Column Inventory

### Group 1: Monetary Columns (→ NUMERIC(12,2))

| Table | Column | Current Type | Notes |
|-------|--------|-------------|-------|
| invoices | total_amount | REAL | Invoice grand total |
| invoices | subtotal_net | REAL | Added via migration |
| invoices | total_vat | REAL | Added via migration |
| invoices | total_gross | REAL | Added via migration |
| invoices | amount_paid | REAL | Added via migration |
| invoices | amount_remaining | REAL | Added via migration |
| invoices | exchange_rate | REAL | → NUMERIC(8,6) — needs higher precision |
| trips | total_price_eur | REAL | Trip revenue |
| trips | rate_per_km | REAL | |
| trips | gross_per_km | REAL | |
| trips | net_profit | REAL | Trip profit |
| trips | extra_costs | REAL | |
| trips | fuel_cost | REAL | |
| trips | toll_cost | REAL | |
| trips | salary_cost | REAL | |
| trips | price_pre_vat | REAL | Added via migration |
| trips | vat_percent | REAL | → NUMERIC(5,2) |
| trucks | monthly_rate | REAL | Leasing cost |
| trucks | max_payload_kg | REAL | → DOUBLE PRECISION (measurement) |
| drivers | monthly_salary | REAL | |
| clients | credit_limit_eur | REAL | |
| clients | default_rate_per_km | REAL | |
| proforma_invoices | subtotal | REAL | |
| proforma_invoices | discount_value | REAL | |
| proforma_invoices | discount_amount | REAL | |
| proforma_invoices | tax_rate | REAL | → NUMERIC(5,2) |
| proforma_invoices | tax_amount | REAL | |
| proforma_invoices | grand_total | REAL | |
| receipts | amount | REAL | |
| receipts | vat_rate | REAL | → NUMERIC(5,2) |
| receipts | vat_amount | REAL | |
| receipts | total | REAL | |
| receipts | mileage | REAL | → DOUBLE PRECISION |
| receipts | fuel | REAL | |
| receipts | accommodation | REAL | |
| receipts | meals | REAL | |
| receipts | parking | REAL | |
| receipts | tolls | REAL | |
| receipts | other_expense | REAL | |
| route_history | fuel_cost | REAL | |
| route_history | toll_cost | REAL | |
| route_history | total_cost | REAL | |
| route_history | price_recommended | REAL | |
| maintenance_records | cost | REAL | |
| contracts | value_eur | REAL | |

### Group 2: Non-Monetary `REAL` Columns (keep `DOUBLE PRECISION`)

| Table | Column | Reason |
|-------|--------|--------|
| trips | distance_km | Measurement |
| trips | truck_consumption_l_per_100km | Measurement |
| trips | gross_weight_kg | Measurement |
| trips | volume_m3 | Measurement |
| trucks | fuel_consumption | Measurement |
| trucks | mileage | Measurement |
| trucks | maintenance_due | Measurement (km) |
| trucks | max_payload_kg | Measurement |
| route_history_v2 | total_distance_km | Measurement |
| route_history_v2 | duration_min | Measurement |
| route_history | distance_km | Measurement |
| route_history | duration_min | Measurement |
| maintenance_records | km | Measurement |
| maintenance_schedules | interval_km | Measurement |
| maintenance_schedules | last_done_km | Measurement |
| tacho_driver_activity | distance_km | Measurement |
| tacho_vehicle_data | odometer_km | Measurement |
| gps_telemetry | latitude | Geolocation |
| gps_telemetry | longitude | Geolocation |
| gps_telemetry | speed_kmh | Measurement |
| document_pipeline_runs | match_confidence | ML metric (→ NUMERIC(5,4)) |
| truck_health_scores | compliance_pct | Percentage (→ NUMERIC(5,2)) |

### Group 3: Percentage/Precision Columns (→ custom NUMERIC)

| Table | Column | Target Type |
|-------|--------|-------------|
| invoices | exchange_rate | NUMERIC(8,6) |
| trips | vat_percent | NUMERIC(5,2) |
| proforma_invoices | tax_rate | NUMERIC(5,2) |
| receipts | vat_rate | NUMERIC(5,2) |
| truck_health_scores | compliance_pct | NUMERIC(5,2) |
| document_pipeline_runs | match_confidence | NUMERIC(5,4) |

## Pydantic Model Changes

### `models/common.py` — `Money` class
```python
# BEFORE
class Money(BaseModel):
    amount: float
    currency: str = "EUR"

# AFTER
from decimal import Decimal
class Money(BaseModel):
    amount: Decimal
    currency: str = "EUR"
```

### All Pydantic models that represent financial data need `Decimal` field types

This applies to trip models, invoice models, receipt models, proforma models, etc.

## Migration Strategy

### Step 1: Update `database/schema_pg.sql`
Replace all `DOUBLE PRECISION` for monetary columns with `NUMERIC(12,2)` (or appropriate precision).

### Step 2: Create Alembic migration
For PostgreSQL production, one migration file that:
- Alters each monetary column using `ALTER COLUMN ... TYPE NUMERIC(12,2) USING ...`
- Handles NULL-to-DEFAULT conversions
- Is reversible (downgrade back to DOUBLE PRECISION if needed)

### Step 3: Update Pydantic models
Change all financial `float` fields to `Decimal`.

### Step 4: Add precision regression tests
- Arithmetic consistency test: 0.1 + 0.2 == 0.3 (proving no float drift)
- VAT calculation test: round-trip through Decimal fields
- Migration data preservation test

## Risks

1. **Numeric overflow**: Existing data with values > 10^10 (10 billion) would overflow NUMERIC(12,2). Mitigation: audit current data before migration.
2. **Rounding changes**: Existing code that depends on float arithmetic behavior may behave differently with Decimal. Mitigation: add regression tests for known calculations.
3. **Performance**: NUMERIC operations are slower than DOUBLE PRECISION. For financial fields this is acceptable. For high-throughput analytics, keep DOUBLE PRECISION on non-monetary measurements.

## Execution Order

1. Update `database/schema_pg.sql` with new types
2. Create Alembic migration file
3. Create rollback migration
4. Update Pydantic models (`Money`, trip, invoice, receipt, proforma)
5. Add precision regression tests
6. Run against PostgreSQL test database
7. Verify data preservation
