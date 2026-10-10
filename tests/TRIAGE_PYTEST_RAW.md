# TRIAGE — RAW: 35 baseline pytest failures (re-run 2026-09-22)

- Command (batch): `python -m pytest <35 baseline IDs> -q --tb=short -n 0` → `debug_pytest_35.txt` (repo root)
- System python 3.11.9, pytest 9.1.1. Postgres available. No code/test changes made.
- Wall time: batch attempt #1 = **3.5 s** (aborted by usage error — see note), batch attempt #2 (33 valid IDs) = **21.7 s**, Chrome probe = ~10–15 s (not separately stopwatchped). Total pytest wall ≈ **~40 s**.
- Note: `debug_pytest_35.txt` was captured via `Tee-Object`; pytest's final `30 passed, 3 failed …` counts line is absent from the captured file (last line is the 3rd `FAILED` entry), but the progress line `............FF.F.................` = 33 chars / 3 `F` confirms **30 passed, 3 failed**.
- Note: attempt #1 with all 35 IDs exited with pytest usage error (exit 4, nothing executed, 3.5 s) because 2 node IDs no longer exist (`ERROR: not found … no match in any of [<Class TestMutationTripModel>]`). Re-ran remaining 33 without them.

## Summary table

| # | node id | outcome | error class | evidence snippet |
|---|---------|---------|-------------|------------------|
| 1 | tests/loadtest/test_load_api_endpoints.py::TestAPILoadFleet::test_concurrent_truck_delete_requests | passed | n/a | no `F` in progress line; no FAILED entry |
| 2 | tests/mutation/test_mutation_models.py::TestMutationTripModel::test_trip_price_accepts_inf | **not found (collection)** | other — ID gone (renamed) | `ERROR: not found: …test_trip_price_accepts_inf (no match in any of [<Class TestMutationTripModel>])`; current file has `test_trip_price_rejects_inf` at tests/mutation/test_mutation_models.py:175 |
| 3 | tests/mutation/test_mutation_models.py::TestMutationTripModel::test_trip_price_accepts_nan | **not found (collection)** | other — ID gone (renamed) | `ERROR: not found: …test_trip_price_accepts_nan`; current file has `test_trip_price_rejects_nan` at tests/mutation/test_mutation_models.py:180 |
| 4 | tests/security/test_authorization.py::TestAllEndpointsRequireAuth::test_all_protected_routes_reject_no_token | passed | n/a | no FAILED entry (deprecation warnings only) |
| 5 | tests/test_alert_panel_widget.py::TestQtAlertPanelNavigation::test_go_calls_navigate_with_destination | passed | n/a | no FAILED entry |
| 6 | tests/test_api_dashboard_view.py::TestQtApiDashboardView::test_refresh_timer_created | passed | n/a | no FAILED entry |
| 7 | tests/test_base_view.py::TestFullLifecycle::test_wakeup_shutdown_cycle | passed | n/a | no FAILED entry |
| 8 | tests/test_component_qss.py::TestLabelFontRoles::test_label_font_role_selectors_exist | passed | n/a | no FAILED entry |
| 9 | tests/test_connection_pool_pg.py::TestPostgresConnectionPool::test_pool_init_and_close | passed | n/a | no FAILED entry (Postgres available this run) |
| 10 | tests/test_connection_pool_pg.py::TestPostgresConnectionPool::test_pool_multiple_connections | passed | n/a | no FAILED entry |
| 11 | tests/test_db_manager.py::TestDeprecatedWarnings::test_get_all_trucks_deprecated | passed | n/a | no FAILED entry |
| 12 | tests/test_hardening_coverage.py::TestRepositoryPurity::test_all_repo_files_have_explicit_commit | passed | n/a | no FAILED entry |
| 13 | tests/test_hardening_coverage.py::TestRepositoryPurity::test_all_repos_import_cleanly | passed | n/a | no FAILED entry |
| 14 | tests/test_import_to_pg_sanitize.py::test_live_import_nulls_orphans_and_validates | passed | n/a | no FAILED entry (alembic DeprecationWarning only) |
| 15 | tests/test_invoice_service.py::TestInvoiceServiceEmailValidation::test_send_email_failure_returns_false | **failed** | real assertion (app code bug) | `services/invoicing/service.py:347: subject = t("email.invoice_subject").format(filename=…, client=…)` → `E IndexError: Replacement index 0 out of range for positional args tuple` |
| 16 | tests/test_invoice_service.py::TestInvoiceServiceEmailValidation::test_send_email_success_returns_true | **failed** | real assertion (app code bug) | same: `services/invoicing/service.py:347` → `E IndexError: Replacement index 0 out of range for positional args tuple` (i18n template has positional `{}`, called with kwargs) |
| 17 | tests/test_main_window.py::TestMainWindowAdvanced::test_on_alert_event_refreshes_alerts | passed | n/a | no FAILED entry |
| 18 | tests/test_maintenance_dialog.py::TestQtMaintenanceViewInit::test_header_label_exists | **failed** | real assertion | `tests/test_maintenance_dialog.py:154: assert "AB-12-34" in maint_view._title_lbl.text()` → `E AssertionError: assert 'AB-12-34' in '⚙ Header'` |
| 19 | tests/test_models_trip.py::TestTripCreate::test_valid_creation[4-start_date3-9999.99-9999.0] | passed | n/a | no FAILED entry |
| 20 | tests/test_postgresql_compat.py::TestConcurrentPgConnections::test_concurrent_reads_succeed | passed | n/a | no FAILED entry (ran against live Postgres) |
| 21 | tests/test_postgresql_compat.py::TestConcurrentPgConnections::test_concurrent_sequential_ids | passed | n/a | no FAILED entry |
| 22 | tests/test_postgresql_compat.py::TestConcurrentPgConnections::test_concurrent_writes_isolation | passed | n/a | no FAILED entry |
| 23 | tests/test_postgresql_compat.py::TestMigrationIntegrity::test_alembic_migrations_apply_on_pg | passed | n/a | no FAILED entry (alembic path_separator DeprecationWarning only) |
| 24 | tests/test_postgresql_compat.py::TestPoolResilience::test_pool_exhaustion_blocks | passed | n/a | no FAILED entry |
| 25 | tests/test_postgresql_compat.py::TestSchemaColumnCoverage::test_critical_tables_column_parity | passed | n/a | no FAILED entry |
| 26 | tests/test_postgresql_compat.py::TestSearchVectorBootBackfill::test_boot_backfills_null_search_vector | passed | n/a | no FAILED entry |
| 27 | tests/test_postgresql_compat.py::TestTripsFkValidatedStatePersists::test_validated_state_survives_reboot | passed | n/a | no FAILED entry |
| 28 | tests/test_route_cache_redis.py::TestCompanyScopedKeys::test_no_company_context_never_shares | passed | n/a | no FAILED entry |
| 29 | tests/test_route_result_presenter.py::TestParseErrorMessage::test_timeout_error | passed | n/a | no FAILED entry |
| 30 | tests/test_schemas_invoice_receipt.py::TestReceiptGenerateRequest::test_all_fields | passed | n/a | no FAILED entry |
| 31 | tests/test_schemas_invoice_receipt.py::TestReceiptGenerateRequest::test_amount_positive | passed | n/a | no FAILED entry |
| 32 | tests/test_schemas_invoice_receipt.py::TestReceiptGenerateRequest::test_vat_rate_negative | passed | n/a | no FAILED entry |
| 33 | tests/test_schemas_invoice_receipt.py::TestReceiptGenerateRequest::test_vat_rate_positive | passed | n/a | no FAILED entry |
| 34 | tests/test_security_verification.py::TestFinding5_MultiTenantIsolation::test_column_allowlists_present | passed | n/a | no FAILED entry |
| 35 | tests/test_security_verification.py::TestFinding5_MultiTenantIsolation::test_repository_company_filter_present | passed | n/a | no FAILED entry |

**Tallies:** 30 passed · 3 failed (all real assertion/app-code, no env/timeout flakes) · 2 not-found IDs (renamed) · 0 skipped · 0 env errors (postgres/qt/chrome) in this bounded run.

## 4. Chrome setup-error probe (ONE command)

Command: `python -m pytest tests/test_chart_export.py -x -q --tb=short -n 0` → last 40 lines.

**Result: probe PASSED — `20 passed`, exit code 0. No error reproduced in isolation.** Dependency check in the same session:

- `choreographer` **is installed** (imports OK from site-packages).
- `chrome.exe` **exists** at `C:\Program Files\Google\Chrome\Application\chrome.exe`.
- Profile dir exists: `%TEMP%\operion_chrome_profile`.

So there is **no missing Python package or missing Chrome binary**. The unavailability documented in the baseline is **runtime contention on the shared Chrome user-data-dir**: with `-n 2`, both xdist workers share the single persistent profile dir `%TEMP%\operion_chrome_profile` (defined at **utils/chart_export.py:884**), so the second headless Chrome exits immediately → `"Choreographer browser failed to start: ('The browser seemed to close immediately after starting.')"` + 30–100 s blocking retries → the ~1,109 E-at-setup blocks (TEST_BASELINE.md:29-30; tests/conftest.py:245-250).

Where the engine actually tries to use it (file:line):

- **utils/chart_export.py:362** — `import choreographer as choreo` inside `_RenderEngine._ensure_browser()` (def at utils/chart_export.py:352)
- **utils/chart_export.py:366** — `choreo.Browser(**_browser_kwargs())` — the actual headless Chrome launch (failure logged at utils/chart_export.py:372)
- Engine singleton created lazily at **utils/chart_export.py:109-116** (`_get_engine()`)

Where the fixtures intercept it (file:line):

- **tests/conftest.py:198-206** — per-test fixture replaces `utils.chart_export._ENGINE` with `MagicMock(spec=_ce._RenderEngine)` "so … any test never try to boot real Chrome"
- **tests/conftest.py:234-267** — session autouse `_session_chart_engine_mock` keeps the mock in place for the whole session (added specifically because the gap caused real Chrome boots)

## 5. Stall area (baseline_pytest.txt, UTF-16)

Command used: `Get-Content -Encoding Unicode -Tail 60` (+ full-file line scan for context).

- The run was in **quiet mode (`-q`)**: only progress characters, **no node IDs** for the final tests. File ends at **[99%]** with the last visible progress clusters: `.....F.FFs..FF` then `.......................s..sssss.s` then plain dots — i.e. a **cluster of ~5 failures + skips immediately before the stall at 99%**, no test names captured.
- The last identifiable *areas* before the stall (from named output embedded in the log):
  - **96–98%**: massive `E` blocks (the headless-Chrome/Qt setup-error storm described in §4) with interspersed `F`s.
  - **line 829 (~82%)**: `[gw2] node down: Not properly terminated` after `ssssssssssss` (skipped cluster) — the **last worker-death line** before the tail; after it an `F` at 82%.
  - **line 674 (~74%)**: `[gw1] node down` — preceded by `Windows fatal exception: access violation` with current thread in **tests/test_team_view.py:148 `test_load_users_populates_table`** (`qtbot.waitUntil` → `pytestqt/qt_compat.py:160 exec`).
  - **line 531 (~63%)**: `[gw0] node down` — preceded by `Fatal Python error: Aborted` with current thread in **tests/test_api/test_route_demo.py:236 `test_missing_destination_returns_400`** (blocked in `starlette.testclient` POST via httpx).
  - **lines 739-741 (~55%)**: stray stderr `Auto-CMR generation failed for trip 1: no such table: trips` / `evaluate_all failed: no such table: trucks` / `evaluate_truck 1 failed: no such table: trucks`.
- Conclusion: no specific test name is visible at the 99% stall point (quiet mode); the last *named* tests in the log are the three xdist-crash sites above (`test_route_demo.py::test_missing_destination_returns_400`, `test_team_view.py::test_load_users_populates_table`, plus the gw2 death at 82%), and the stall itself follows the 96–99% Chrome/Qt `E`-storm plus the final `F.FFs..FF` cluster. Harness stopped the run at ~99% after ~100 min (baseline_pytest_failures.txt header).
