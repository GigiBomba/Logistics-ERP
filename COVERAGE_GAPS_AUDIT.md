# Operion ERP — Repository Test Coverage Audit

**Report Date:** 2026-07-09
**Audited Repositories:** 12
**Total Untested Methods:** 118
**Total Untested Tables:** 24

---

## EXECUTIVE SUMMARY

This audit consolidates findings from 12 repository audits covering data access layers that currently lack dedicated test coverage. These repositories handle critical ERP operations including:

- **Tacho/Compliance Data** (3 repos) — Regulatory compliance, driver activity tracking
- **Fleet Operations** (2 repos) — Truck-driver assignments, route assignments
- **Document Pipeline** (1 repo) — 29 methods for document automation workflows
- **Contact Management** (1 repo) — Client contact handling with transaction risks
- **Proforma/Invoicing** (2 repos) — Invoice numbering, successive carriers
- **Automail System** (1 repo) — 32 methods across templates, schedules, overrides
- **Event Tracking** (1 repo) — Route event logging with tenant isolation risks
- **Tagging System** (1 repo) — Client tagging with silent error handling

### Risk Distribution

| Risk Level | Count | Primary Issues |
|-------------|-------|----------------|
| **CRITICAL** | 4 | Data leaks (no company filter), TOCTOU races, admin injection |
| **HIGH** | 5 | Missing transaction rollback, IntegrityError swallowing, NULL handling |
| **MEDIUM** | 3 | Missing rowcount checks, batch transaction issues |

### Estimated Test Effort

| Category | Methods | Recommended Tests | Estimated LOC |
|----------|---------|------------------|--------------|
| Tacho Repositories | 14 | 45-60 | 800-1200 |
| Assignment Repositories | 13 | 40-50 | 600-800 |
| Pipeline Repository | 29 | 80-100 | 1500-2000 |
| Automail Repository | 32 | 90-120 | 1800-2400 |
| Other Repositories | 30 | 60-80 | 1000-1400 |
| **TOTAL** | **118** | **315-410** | **5700-7800** |

---

## REPOSITORY AUDIT TABLE

| # | Repository | Methods | Tables | Priority Methods | Highest Priority | Est. Tests |
|---|------------|---------|--------|------------------|------------------|------------|
| 1 | `automail_repository.py` | 32 | 6 | `upsert_override` (TOCTOU), `reorder_schedules` (batch), `create_schedule` (auto-sort) | `upsert_override` | 90-120 |
| 2 | `contact_repository.py` | 7 | 1 | `set_primary` (no rollback), `create` (datetime injection), `update` (no rowcount) | `set_primary` | 15-20 |
| 3 | `driver_truck_assignment_repository.py` | 10 | 3 | `swap` (no rollback), `assign` (upsert semantics), `get_truck_plate_for_driver` (NULL→"") | `swap` | 25-35 |
| 4 | `pipeline_repository.py` | 29 | 4 | `append_related_document` (read-modify-write), `recover_stuck_runs` (recovery), `get_match_signals` (JSON), `create_run` (input cleaning) | `append_related_document` | 80-100 |
| 5 | `proforma_repository.py` | 10 | 1 | `get_next_number` (MAX+1 race), `create` (exception swallow), `update` (allowlist) | `get_next_number` | 20-30 |
| 6 | `route_event_repository.py` | 2 | 2 | `delete_orphans` (correlated subquery), `create` (NULL route_id, admin injection) | `delete_orphans` | 10-15 |
| 7 | `successive_carrier_repository.py` | 6 | 1 | `replace_for_trip` (no rollback), `get_by_trip` (tenant), `update` (no rowcount) | `replace_for_trip` | 15-20 |
| 8 | `tacho_driver_activity_repository.py` | 4 | 1 | `create` (company injection), `delete_by_import` (destructive, no return) | `create` | 10-15 |
| 9 | `tacho_import_repository.py` | 4 | 1 | `create` (column validation), `get_by_hash` (dedup) | `create` | 10-15 |
| 10 | `tacho_vehicle_data_repository.py` | 6 | 3 | `get_tacho_status_data` (NO company filter—**DATA LEAK**), `get_latest_per_truck` (NO company filter), `create` (admin injection) | `get_tacho_status_data` | 15-20 |
| 11 | `tag_repository.py` | 5 | 1 | `add` (IntegrityError swallow), `remove` (no rowcount), `get_by_client` (scoping) | `add` | 10-15 |
| 12 | `truck_route_assignment_repository.py` | 3 | 2 | `complete` (ambiguous bool), `assign` (type coercion), `get_by_truck` (NULL JOIN) | `complete` | 10-15 |

---

## TOP 10 CRITICAL METHODS

Ranked by risk severity (security, data integrity, availability impact):

### 1. `tacho_vehicle_data_repository.get_tacho_status_data()`
**Risk:** CRITICAL — **DATA LEAK**
- **Issue:** NO company filter applied to query
- **Impact:** Any authenticated user can query tacho status data for ALL companies
- **Severity:** GDPR violation, regulatory non-compliance
- **Fix:** Add `company_id` filter parameter and validate tenant isolation

### 2. `tacho_vehicle_data_repository.get_latest_per_truck()`
**Risk:** CRITICAL — **DATA LEAK**
- **Issue:** NO company filter applied to query
- **Impact:** Truck tacho data leak across tenants
- **Severity:** Same as above
- **Fix:** Add company filtering to JOIN query

### 3. `automail_repository.upsert_override()`
**Risk:** CRITICAL — **TOCTOU Race Condition**
- **Issue:** Time-of-check-time-of-use race between SELECT and INSERT/UPDATE
- **Impact:** Duplicate overrides or lost updates under concurrent access
- **Severity:** Data corruption in automail settings
- **Fix:** Use `INSERT ... ON CONFLICT UPDATE` with proper locking

### 4. `automail_repository.reorder_schedules()`
**Risk:** HIGH — **Batch Transaction Without Rollback**
- **Issue:** Updates multiple rows in loop without transaction wrapper
- **Impact:** Partial updates on failure — inconsistent sort_order sequence
- **Severity:** Broken automail scheduling
- **Fix:** Wrap in explicit transaction with rollback on any failure

### 5. `route_event_repository.delete_orphans()`
**Risk:** HIGH — **Tenant Isolation + Correlated Subquery**
- **Issue:** Correlated subquery may not respect company scoping when called from admin context
- **Impact:** Delete events from wrong company, or fail to delete orphans
- **Severity:** Data integrity, cross-tenant contamination
- **Fix:** Validate company_id propagation in all code paths

### 6. `pipeline_repository.append_related_document()`
**Risk:** HIGH — **Read-Modify-Write Race**
- **Issue:** Non-atomic read of current document_ids, modify, then write back
- **Impact:** Lost updates under concurrent document attachment
- **Severity:** Lost work in document pipelines
- **Fix:** Use atomic array append or row-level locking

### 7. `successive_carrier_repository.replace_for_trip()`
**Risk:** HIGH — **Transaction Without Rollback**
- **Issue:** DELETE + INSERT sequence without try/except rollback
- **Impact:** Orphaned records or duplicate carriers on failure mid-operation
- **Severity:** Broken successive carrier tracking
- **Fix:** Wrap in explicit transaction

### 8. `driver_truck_assignment_repository.swap()`
**Risk:** HIGH — **Transaction Without Rollback**
- **Issue:** Swap operation (two updates) without transaction safety
- **Impact:** Inconsistent state if second update fails
- **Severity:** Fleet assignment corruption
- **Fix:** Add transaction wrapper with rollback

### 9. `proforma_repository.get_next_number()`
**Risk:** HIGH — **Race Condition**
- **Issue:** `MAX(id) + 1` pattern without locking or sequence
- **Impact:** Duplicate numbers under concurrent proforma creation
- **Severity:** Invoice numbering conflicts
- **Fix:** Use database sequence or `SELECT FOR UPDATE NOWAIT`

### 10. `tacho_driver_activity_repository.create()`
**Risk:** HIGH — **Admin Company ID Injection**
- **Issue:** Company ID potentially injected from admin context without validation
- **Impact:** Activity logged under wrong company
- **Severity:** Regulatory compliance, audit trail integrity
- **Fix:** Validate company_id matches authenticated user's tenant

---

## RECOMMENDED IMPLEMENTATION ORDER

### Phase 1: Critical Security Fixes (Week 1-2)
**Focus:** Data leak fixes and regulatory compliance

| Priority | Repository | Method | Rationale |
|----------|------------|--------|-----------|
| P0 | `tacho_vehicle_data_repository` | `get_tacho_status_data()` | CRITICAL data leak — GDPR violation |
| P0 | `tacho_vehicle_data_repository` | `get_latest_per_truck()` | CRITICAL data leak |
| P0 | `tacho_driver_activity_repository` | `create()` | Company ID injection risk |
| P1 | `tacho_import_repository` | `create()` | Column validation for tacho imports |
| P1 | `route_event_repository` | `delete_orphans()` | Tenant isolation in admin context |

**Estimated:** 25-35 tests, 500-700 LOC

### Phase 2: Transaction Safety (Week 2-3)
**Focus:** Fix TOCTOU races and missing rollbacks

| Priority | Repository | Method | Rationale |
|----------|------------|--------|-----------|
| P0 | `automail_repository` | `upsert_override()` | TOCTOU race — critical |
| P1 | `automail_repository` | `reorder_schedules()` | Batch transaction |
| P1 | `pipeline_repository` | `append_related_document()` | Read-modify-write race |
| P1 | `successive_carrier_repository` | `replace_for_trip()` | Missing rollback |
| P1 | `driver_truck_assignment_repository` | `swap()` | Missing rollback |
| P2 | `proforma_repository` | `get_next_number()` | Numbering race |
| P2 | `contact_repository` | `set_primary()` | Missing rollback |

**Estimated:** 60-80 tests, 1200-1600 LOC

### Phase 3: Error Handling (Week 3-4)
**Focus:** Silent error swallowing, rowcount checks

| Priority | Repository | Method | Rationale |
|----------|------------|--------|-----------|
| P1 | `tag_repository` | `add()` | Silent IntegrityError swallow |
| P2 | `tag_repository` | `remove()` | Missing rowcount |
| P2 | `contact_repository` | `update()` | Missing rowcount |
| P2 | `successive_carrier_repository` | `update()` | Missing rowcount |
| P2 | `proforma_repository` | `create()` | Exception swallowing |

**Estimated:** 25-35 tests, 500-700 LOC

### Phase 4: Remaining Repository Coverage (Week 4-6)
**Focus:** Complete test coverage for all 12 repositories

| Repository | Methods | Focus Areas |
|-----------|---------|-------------|
| `automail_repository` | 32 | Templates, schedules, overrides, settings, email logs, reminders |
| `pipeline_repository` | 29 | Stuck run recovery, match signals, input cleaning, run management |
| `driver_truck_assignment_repository` | 10 | Assignment semantics, NULL handling, plate lookups |
| `proforma_repository` | 10 | Numbering, CRUD with allowlist filtering |
| `route_event_repository` | 2 | Orphan deletion, event creation |
| `successive_carrier_repository` | 6 | Trip-scoped CRUD with tenant isolation |
| `tacho_driver_activity_repository` | 4 | Activity creation, import-scoped deletion |
| `tacho_import_repository` | 4 | Hash-based dedup, column validation |
| `tacho_vehicle_data_repository` | 6 | Status queries, latest-per-truck, creation |
| `tag_repository` | 5 | Add/remove with integrity, client-scoped retrieval |
| `truck_route_assignment_repository` | 3 | Assignment completion, type coercion, NULL JOIN ordering |
| `contact_repository` | 7 | Primary contact management, datetime handling |

**Estimated:** 200-260 tests, 3500-4800 LOC

---

## TEST PATTERNS REFERENCE

### Transaction Safety Test Pattern
```python
def test_reorder_schedules_atomic():
    """Schedules must all update or none."""
    original_order = repo.get_schedule_order(group_id=1)
    try:
        repo.reorder_schedules(group_id=1, new_order=[3,1,2])
    except Exception:
        pass  # intentionally cause partial failure
    current_order = repo.get_schedule_order(group_id=1)
    assert current_order == original_order, "Partial update detected"
```

### TOCTOU Race Test Pattern
```python
@pytest.mark.parametrize("concurrent_writes", [2, 5, 10])
def test_upsert_override_no_duplicate(concurrent_writes):
    """Concurrent upserts must not create duplicates."""
    overrides = []
    def writer():
        overrides.append(repo.upsert_override(1, {"key": "value"}))
    
    threads = [threading.Thread(target=writer) for _ in range(concurrent_writes)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    # Exactly one override should exist
    assert len(repo.get_overrides(1)) == 1
```

### Company Isolation Test Pattern
```python
def test_get_tacho_status_data_requires_company_filter():
    """Query must not return data from other companies."""
    # Setup: Create data for company A
    repo.create({"company_id": 1, "truck_id": 100, "data": "SECRET"})
    
    # Query WITHOUT company filter should be rejected
    with pytest.raises(ValueError, match="company_id required"):
        repo.get_tacho_status_data()
    
    # Query WITH correct company returns data
    result = repo.get_tacho_status_data(company_id=1)
    assert result[0]["data"] == "SECRET"
    
    # Query with WRONG company returns empty
    result = repo.get_tacho_status_data(company_id=999)
    assert len(result) == 0
```

### Rowcount Verification Test Pattern
```python
def test_update_returns_affected_rows():
    """Update should return count or raise if no rows affected."""
    # Non-existent record
    result = repo.update(id=9999, data={"key": "value"})
    assert result == 0 or result is False
    
    # Existing record
    repo.create({"id": 100, "key": "original"})
    result = repo.update(id=100, data={"key": "updated"})
    assert result == 1
```

---

## APPENDIX: METHOD COUNTS BY REPOSITORY

| Repository | Total Methods | High Priority | Medium Priority | Low Priority |
|------------|---------------|---------------|-----------------|--------------|
| `automail_repository` | 32 | 3 | 5 | 24 |
| `pipeline_repository` | 29 | 1 | 3 | 25 |
| `driver_truck_assignment_repository` | 10 | 1 | 2 | 7 |
| `proforma_repository` | 10 | 1 | 2 | 7 |
| `contact_repository` | 7 | 1 | 2 | 4 |
| `successive_carrier_repository` | 6 | 1 | 2 | 3 |
| `tacho_vehicle_data_repository` | 6 | 3 | 1 | 2 |
| `route_event_repository` | 2 | 1 | 1 | 0 |
| `tacho_driver_activity_repository` | 4 | 1 | 1 | 2 |
| `tacho_import_repository` | 4 | 1 | 1 | 2 |
| `tag_repository` | 5 | 1 | 2 | 2 |
| `truck_route_assignment_repository` | 3 | 1 | 2 | 0 |
| **TOTAL** | **118** | **16** | **26** | **76** |

---

*Report generated from 12 repository audits. For individual repository detailed findings, refer to each repository's dedicated audit document.*
