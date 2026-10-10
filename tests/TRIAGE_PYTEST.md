# TRIAGE_PYTEST — pytest failure/hang/error triage (2026-09-22)

Scope: triage of the 2026-09-20 baseline (`baseline_pytest_failures.txt`,
35 FAILED node IDs; `baseline_pytest.txt`; `TEST_BASELINE.md`) plus the
full-run diagnostics captured in `full_diag.log` / `full_diag.err`
(research-phase run, 2026-09-22). Runner: system Python 3.11.9 /
pytest 9.1.1, Postgres 16 (docker `calculatorlogistica-postgres-test-1`)
and Redis available on this machine.

Category legend:
**ENV-DEP** = environment/configuration dependency (fixed test-side with an
honest reason or config correction) · **REAL TEST BUG** = the test itself
was wrong/stale/leaky (fixed) · **REAL APP BUG** = defect in app code or
shipped data (reported only — app code is out of scope for this phase).

---

## 1. The 35 baseline FAILED node IDs

Reproduce command used for triage:
`python -m pytest -n 0 --tb=short -q --timeout=180 --timeout-method=thread <35 ids>`
(after mapping the 2 renamed mutation IDs, see rows 2–3).

| # | node id | category | root cause | evidence |
|---|---|---|---|---|
| 1 | `tests/loadtest/test_load_api_endpoints.py::TestAPILoadFleet::test_concurrent_truck_delete_requests` | REAL TEST BUG (fixed, prior uncommitted phase) + flake under load | loadtest concurrency race; passes reliably in targeted re-run | triage run: PASSED (`triage1.txt`, `triage2.txt`) |
| 2 | `tests/mutation/test_mutation_models.py::TestMutationTripModel::test_trip_price_accepts_inf` | REAL TEST BUG (fixed, prior phase) | stale ID: test renamed `accepts_inf`→`rejects_inf`; old test asserted `price_eur == inf` (app correctly rejects non-finite). Renamed + now asserts `ValidationError` | `git diff tests/mutation/test_mutation_models.py`; current run: PASSED |
| 3 | `tests/mutation/test_mutation_models.py::TestMutationTripModel::test_trip_price_accepts_nan` | REAL TEST BUG (fixed, prior phase) | same as #2 for NaN | ditto; PASSED |
| 4 | `tests/security/test_authorization.py::TestAllEndpointsRequireAuth::test_all_protected_routes_reject_no_token` | REAL TEST BUG (fixed this phase) | 4 routes returned 422 (FastAPI validates body/query before the handler's in-body/in-query credential check): `/auth/mfa/verify`, `/auth/mfa/backup-code` (public login-completion, mfa_session_token in body), `/support/anonymous-error` (documented public, rate-limited), `/mobile/pairing-token/validate` (one-time pairing token in query). All four are public-by-design or JWT-less-by-design → added to `PUBLIC_PATHS` with per-entry reasons | `backend/api/v1/mfa.py:9-10` "(public)", `support.py:415-417` "No authentication is required", `mobile_pairing.py:157-195`; fix in `tests/security/test_authorization.py` |
| 5 | `tests/test_alert_panel_widget.py::TestQtAlertPanelNavigation::test_go_calls_navigate_with_destination` | REAL TEST BUG (fixed this phase) | test expected `"maintenance_control"`; app deliberately remapped `maintenance`/`inspection` alerts to the `"maintenance"` nav key when the control panel folded into the maintenance hub | `git log -L 42,51:ui/widgets/alert_panel.py` → commit `e8d6832e`; `ui/main_window.py:1001` dispatches `"maintenance"`; fixed expectation |
| 6 | `tests/test_api_dashboard_view.py::TestQtApiDashboardView::test_refresh_timer_created` | REAL TEST BUG (fixed this phase) | expected 5000 ms; app starts `start(30_000)` (same cadence as dispatch-board timers, which other tests already assert as 30000) | `ui/views/api_dashboard_view.py:90`; `tests/test_dispatch_board_view.py:296`; fixed expectation |
| 7 | `tests/test_base_view.py::TestFullLifecycle::test_wakeup_shutdown_cycle` | not reproducible (fixed/flaky, prior phase) | passes in targeted re-run | `triage1.txt` PASSED |
| 8 | `tests/test_component_qss.py::TestLabelFontRoles::test_label_font_role_selectors_exist` | REAL TEST BUG (fixed this phase) | expected `[fontRole="h1"]`/`"hero"` selectors; theme removed those dead roles (zero production consumers, documented) | `docs/UI_VISUAL_AUDIT_DRIFT_RESOLUTION_REPORT.md:43-47`, `tools/evidence_p5b_postgate_report.txt:535-540`, current `ui/theme_engine.py` has h2/h3/mono/muted/secondary/accent but no h1/hero; fixed role list |
| 9 | `tests/test_connection_pool_pg.py::…test_pool_init_and_close` | ENV-DEP → now PASSING (no code change needed) | per-file DSN already defaults to `operion_test_ci` (matches running container) + isolated `operion_test_pool` DB | targeted run: PASSED ×2 |
| 10 | `tests/test_connection_pool_pg.py::…test_pool_multiple_connections` | same as #9 | same | PASSED |
| 11 | `tests/test_db_manager.py::TestDeprecatedWarnings::test_get_all_trucks_deprecated` | not reproducible (prior phase) | deprecation-warning assertion passes | PASSED |
| 12–13 | `tests/test_hardening_coverage.py::TestRepositoryPurity::…` ×2 | REAL TEST BUG (fixed, prior phase) | `open()` without `encoding=` crashed on non-UTF-8 byte → SyntaxError. Fixed with `encoding="utf-8"` | `git diff tests/test_hardening_coverage.py`; PASSED |
| 14 | `tests/test_import_to_pg_sanitize.py::test_live_import_nulls_orphans_and_validates` | ENV-DEP → now PASSING | DSN default `operion_test_ci` matches container; isolated `operion_test_san` DB | PASSED |
| 15–16 | `tests/test_invoice_service.py::…test_send_email_{failure,success}_…` | **REAL APP BUG — reported, still failing** | `services/invoicing/service.py:347` does `t("email.invoice_subject").format(filename=…, client=…)` but every shipped translation is `"Invoice {} - {}"` (auto positional fields) → `IndexError: Replacement index 0 out of range for positional args tuple`. Same kwargs-vs-positional mismatch at `ui/views/invoice_editor/editor_form.py:1703`. Production impact: sending an invoice email crashes instead of sending | traceback in `triage1.txt` (`services/invoicing/service.py:347`); `python -c` check: `en.json email.invoice_subject == 'Invoice {} - {}'` |
| 17 | `tests/test_main_window.py::TestMainWindowAdvanced::test_on_alert_event_refreshes_alerts` | not reproducible (prior phase) | — | PASSED |
| 18 | `tests/test_maintenance_dialog.py::TestQtMaintenanceViewInit::test_header_label_exists` | **REAL APP/DATA BUG — reported, still failing** | dialog builds title as `iconed("maint.header", self.truck_plate)` (`ui/dialogs/maintenance_view.py:89`), but (a) `services/i18n.py:124` signature is `t(key, default=None, *args)` so the plate binds to `default`, not to a format arg, and (b) every translation of `maint.header` is a placeholder-less `"Header"`/`"Antet"` → the plate can never appear (`"⚙ Header"`). Test asserts the intended UX (plate in dialog title) | `ui/icons.py:95-103`, `services/i18n.py:124-147`, `en.json maint.header == 'Header'`; failure text `assert 'AB-12-34' in '⚙ Header'` |
| 19 | `tests/test_models_trip.py::TestTripCreate::test_valid_creation[4-…9999.99-…]` | REAL TEST BUG (fixed, prior phase) | Decimal price vs float literal comparison → `float(tc.price_eur)` | `git diff tests/test_models_trip.py`; PASSED |
| 20–26 | `tests/test_postgresql_compat.py::…` ×7 | ENV-DEP → now PASSING (no change needed) | DSN default `operion_test_ci` matches container; isolated `operion_test_compat` DB (migrations, pool exhaustion, column parity, search-vector backfill, FK state) | targeted run: all 7 PASSED |
| 27 | `tests/test_route_cache_redis.py::TestCompanyScopedKeys::test_no_company_context_never_shares` | not reproducible (Redis available here) | passes | PASSED |
| 28 | `tests/test_route_result_presenter.py::TestParseErrorMessage::test_timeout_error` | REAL TEST BUG (fixed, prior phase) | assertion only accepted `"timeout"`/key; app copy says "timed out" — widened matcher | `git diff tests/test_route_result_presenter.py`; PASSED |
| 29–32 | `tests/test_schemas_invoice_receipt.py::TestReceiptGenerateRequest::…` ×4 | REAL TEST BUG (fixed, prior phase) | Decimal fields vs float literals → `float(...)` normalization | `git diff tests/test_schemas_invoice_receipt.py`; PASSED |
| 33–34 | `tests/test_security_verification.py::TestFinding5_…` ×2 | REAL TEST BUG (fixed, prior phase) | `open()` without `encoding=` on repo files → UnicodeDecodeError; fixed with `encoding="utf-8"` | `git diff tests/test_security_verification.py`; PASSED |
| 35 | `tests/test_security_verification.py::…test_repository_company_filter_present` | same as #33 | same | PASSED |

**Post-fix state of the 35:** 32 pass (or were already fixed by the prior
uncommitted phase and re-verified here), 3 remain failing as reported
REAL APP BUGS (#15, #16, #18).

---

## 2. Postgres

* The container (`postgres:16-alpine`, healthcheck OK) is up; the correct
  password for this machine is `operion_test_ci` (compose default
  `${OPERION_TEST_POSTGRES_PASSWORD:-operion_test_ci}`, also hard-coded in
  `.github/workflows/test-python.yml:116`).
* All PG node IDs inside the 35 (rows 9–10, 14, 20–26) **run and pass
  here** — those files already defaulted to `operion_test_ci`.
* **ENV-DEP bug found & fixed (test-side):** `tests/integration/conftest.py`
  `DEFAULT_TEST_DSN` hard-coded `operion_test`, which fails auth against
  the compose container → `_ensure_database()` caught the
  `OperationalError` and skipped the **whole integration suite** with the
  misleading reason *"PostgreSQL is not available — skipping integration
  tests: password authentication failed"*. Verified before fix:
  `pytest tests/integration -n 0` → 55 skipped. Fixed to honour
  `OPERION_TEST_POSTGRES_PASSWORD` (default `operion_test_ci`). After fix:
  suite runs against real Postgres (see §6 verification).

---

## 3. The ~1,109 Chrome setup errors ("E" blocks)

### What they are NOT

* **Not missing binaries.** Chrome exists
  (`C:\Program Files\Google\Chrome\Application\chrome.exe`), PySide6
  QtWebEngine works (real `MapWidget`/`QWebEngineView` tests construct
  fine: `tests/test_map_widget.py` 14/14, `tests/a11y/test_a11y_map_widget.py`
  3/3).
* **Not `tests/test_silent_chromium.py` / `tests/test_chart_export.py`
  themselves**: both are fully mocked and pass 42/42 in isolation
  (`-n 0` and `-n 2`). The baseline run even `--ignore`d them and still
  produced the 1,109 E's.

### Mechanism (evidence-based)

1. `tests/conftest.py::reset_singletons` swaps a `MagicMock` into
   `utils.chart_export._ENGINE` per test and **restores the previous value
   (initially `None`) on teardown** — after only a 5 s
   `wait_for_done(msec=5000)` drain.
2. Any `PlotlyChartWidget` render worker that outlives that 5 s window and
   calls `_get_engine()` in the gap creates a **real** `_RenderEngine` and
   starts headless Chrome (`utils/chart_export.py:109-117`).
3. `tests/test_chart_export.py::TestRenderEngine::test_start_block_waits_for_started`
   (and `test_raises_if_start_never_completes`, via `submit()→start()`)
   spawned a **real choreographer engine thread per run and never shut it
   down** (only the `_started` Event was patched).
4. Chrome then **fails to launch** under Choreographer in full runs —
   `full_diag.err:209-212`:
   `"Choreographer browser failed to start: ('The browser seemed to close
   immediately after starting.' … located at C:\Program Files\Google\Chrome…)`
   + `Browser start failed (attempt 4) — retrying in 16s"`. Most likely
   cause: the persistent profile dir is **shared across both xdist
   workers** (`tempdir/operion_chrome_profile`,
   `utils/chart_export.py:884`) — the second instance sees the lock and
   exits immediately. (App-side deeper fix: per-process profile dir.)
5. Every real launch attempt blocks callers for 30 s
   (`start(block=True)`/`submit()` `_started.wait(35)`), up to
   `timeout+70` s per submit, plus 5 s × every test teardown drain. While a
   worker sits in those waits, its tests error at setup → the alternating
   `E.E.E` blocks at ~53%, 61–64%, 69–70%, 96–99% in
   `baseline_pytest.txt`/`full_diag.log`; the retry storm is logged at the
   very end of `full_diag.err` (i.e. at the run tail).

### Mitigations applied (test-side, no skips)

* **`tests/conftest.py`**: new session-scoped autouse
  `_session_chart_engine_mock` — `_ENGINE` is a mock from the first test
  until the worker's session ends (never `None` between tests, never a
  real engine left behind); any real `_RenderEngine` a test installed is
  `shutdown()` at session teardown. Closes the leftover-render race
  permanently.
* **`tests/test_chart_export.py`**: `try/finally engine.shutdown()` added
  to the two `TestRenderEngine` tests that start a real engine thread
  (REAL TEST BUG — resource leak).
* **No skips added**: nothing in these two files is un-runnable; they pass
  as-is.

---

## 4. Qt/PySide6 worker crashes

### Pattern

`Windows fatal exception: access violation` / `Fatal Python error: Aborted`
inside a worker → `[gwN] node down: Not properly terminated` → **xdist
respawns it** (`full_diag.log:126-128`: `"replacing crashed worker gw0"`,
also gw1 @55%, gw2 @82%). Baseline had the same at 22% / 35% / 82%.
Because replacement works, crashes cost only the in-flight test (3 "F"s)
and do **not** stop the run.

Captured crash sites (`full_diag.err`):

1. **Qt access violation inside `qtbot.waitUntil`** — current frame
   `pytestqt/qt_compat.py:160 exec ← qtbot.waitUntil` at
   `tests/test_team_view.py:148` (`_load_users` async WorkerPool wait).
   A worker pool touches a deleted C++ object while the wait spins the
   event loop. Crash dumps also list `PySide6.QtWebEngineCore/Widgets`
   among loaded extensions.
2. **Native abort in loadtest** — `Fatal Python error: Aborted` with
   `tests/loadtest/test_load_mobile.py:95 → loadtest/conftest.py:31
   run_concurrent → as_completed` (preceded by `evaluate_all failed: no
   such table: trucks`). Corroborated by the baseline's abort at ~22%,
   which maps to the loadtest region.

### Mitigation applied

* **`tests/loadtest/test_load_mobile.py`**: marker-gated xdist exclusion —
  `pytest.mark.skipif(PYTEST_XDIST_WORKER, reason=…)` composed with the
  existing `slow` mark. The module still runs (`-n 0`/serial, verified);
  under xdist it skips with an honest reason instead of killing a worker
  every run. This is the mission-sanctioned "marker-gated xdist
  exclusion"; zero *runnable-under-xdist* tests were skipped.
* **Deeper fixes (documented, not done here):**
  * team_view/WorkerPool crash: make `ui/worker_pool.py` jobs abort-safe
    against widget deletion (guard signals with `Shiboken.isValid`, or
    deliver results via queued connection only), then re-enable the test
    under xdist.
  * loadtest abort: give `run_concurrent` a per-thread DB connection
    (the "no such table: trucks" line suggests a closed/foreign SQLite
    connection shared across pool threads) before removing the xdist gate.
  * App-side: per-process Chrome profile dir (see §3.4) removes the
    cross-worker launch conflict entirely.

---

## 5. Hang hunt (the stall at ~98–99%)

### Findings

* **The tail itself is clean**: `tests/ui` + `tests/workflow_integrity` +
  top-level `test_v*`/`test_w*`/dialog/signal files run **RC=0, 100%**,
  bounded (~3 min) with `-n 2 --timeout=600 --timeout-method=thread` —
  no hang, no errors, both before and after the fixes. The mid-suite
  regions (test_d/e/f ≈ 1.9k tests; test_i/k/l/m ≈ 1.5k tests) are also
  clean apart from the 3 reported app bugs.
* **The stall only happens in full runs**, with the Choreographer retry
  storm and mass E-blocks at the tail (`full_diag.log` stops mid-line at
  99%; `full_diag.err` ends on `Browser start failed (attempt 4) …
  retrying in 16s`).
* **Empirical proof of the hang**: the research phase's full run
  (`python -m pytest -n 2 --dist=loadscope --timeout=600
  --timeout-method=thread -v --tb=line -rEf`, started 19:25) was still
  alive at 22:43 — master PID 46000 plus two orphan execnet workers
  (PIDs 44900, 46832), no output since 20:19. **Killed during this
  phase** (orphaned diagnostics; they were starving the CPU/ports).
* Mechanism: a worker wedged in a real-engine native wait
  (`future.result(timeout=…)` up to 100 s, or the 30 s start waits stacked
  across a session) never reports; `--timeout=600 --timeout-method=thread`
  cannot interrupt a native wait, and pytest-timeout does not fire after
  the session's tests are done (worker never reaches a reportable
  boundary) → controller waits forever at ~99%.

### Fencing applied

* The two fixes in §3 (session-long engine mock + `engine.shutdown()` in
  `TestRenderEngine`) remove the only identified source of real-Chrome
  native waits — this is the fence for the hang (test-side, honest; no
  test skipped).
* No `wait_for_done()` (infinite, `msec=-1`) callers exist anywhere in
  `tests/` (checked: only `msec=5000` and `15000` are used).
* Residual risk documented: if a future full run still stalls, the
  tail-bisection recipe is:
  `python -m pytest tests/ui tests/workflow_integrity tests/test_v*.py … -n 2 --timeout=600 --timeout-method=thread -q -rE`
  (bounded by an outer hard timeout), which currently completes clean.

---

## 6. Remaining REAL APP BUGS (report only — do not fix in tests/)

1. **Invoice email send crashes** — `services/invoicing/service.py:347`
   (+ `ui/views/invoice_editor/editor_form.py:1703`):
   `.format(filename=…, client=…)` against translations shaped
   `"Invoice {} - {}"` / `"Dear Sir/Madam, … invoice {}. … {:.2f} … {} … {}"`
   → `IndexError` in production, email never sends. Fix belongs in app
   code (pass positionally or switch translations to named fields) or in
   all 22 translation files. Affected tests (still failing, by design of
   this phase):
   * `tests/test_invoice_service.py::TestInvoiceServiceEmailValidation::test_send_email_failure_returns_false`
   * `tests/test_invoice_service.py::TestInvoiceServiceEmailValidation::test_send_email_success_returns_true`
2. **Maintenance dialog title never shows the truck plate** —
   `ui/dialogs/maintenance_view.py:89` + `ui/icons.py:103` +
   `services/i18n.py:124`: the plate is bound to `t()`'s `default`
   parameter (never used when the key resolves) and `maint.header` has no
   `{}` placeholder in any language. Affected test (still failing):
   * `tests/test_maintenance_dialog.py::TestQtMaintenanceViewInit::test_header_label_exists`
3. (Informational, not a test failure) **Shared Chrome profile dir** across
   processes — `utils/chart_export.py:884` uses a fixed
   `tempdir/operion_chrome_profile`; two concurrent engines (e.g. two
   xdist workers) fight over it → "browser seemed to close immediately".
   Should be per-process (`…profile-{os.getpid()}`) in app code.

---

## 7. Verification commands & results (targeted only — no full-suite run)

| # | command | result |
|---|---|---|
| V1 | `python <tmp>/run_ids.py` → `python -m pytest -n 0 --tb=short -q --timeout=180 --timeout-method=thread <35 ids>` | **32 passed / 3 failed**; the 3 failures are exactly the reported app bugs (invoice ×2, maintenance header). No skips. |
| V2 | `python -m pytest tests/integration -n 0 -q --tb=line --timeout=300` (before fix) | 55 **skipped** — wrong default DSN password (ENV-DEP, misleading skip reason) |
| V3 | `python -m pytest tests/integration -n 0 -q --tb=line --timeout=300` (after fix) | runs against real Postgres — see summary line in §7 of the phase report |
| V4 | `python -m pytest tests/test_chart_export.py tests/test_silent_chromium.py -n 0 -q` | 42 passed (was already passing; now also leak-free) |
| V5 | `python -m pytest tests/loadtest/test_load_mobile.py -n 0 -q` | runs and passes serially (no skip) |
| V6 | `python -m pytest tests/loadtest/test_load_mobile.py -n 2 -q` | skipped with the honest xdist-crash reason (worker-crash mitigation) |
| V7 | tail bisection: `python <tmp>/run_args.py "tests/ui" "tests/workflow_integrity" "tests/test_v*.py" "tests/test_widgets.py" <dialogs/signals> -n 2 --dist=loadscope --timeout=600 --timeout-method=thread -q -rE` | **RC=0, 100%, no hang, no errors** (run twice: pre- and post-fix) |
| V8 | region sanity: `tests/test_d*.py tests/test_e*.py tests/test_f*.py -n 2 …` | RC=0 (clean) |
| V9 | region sanity: `tests/test_i*.py tests/test_k*.py tests/test_l*.py tests/test_m*.py -n 2 …` | RC=1 → exactly the 3 reported app bugs, no setup errors |
| V10 | targeted fixes: `pytest tests/test_alert_panel_widget.py::TestQtAlertPanelNavigation tests/test_api_dashboard_view.py::…test_refresh_timer_created tests/test_component_qss.py::TestLabelFontRoles tests/security/test_authorization.py::TestAllEndpointsRequireAuth -n 0 -q` | all passed |

Zero new skips were added for tests that can run: the only new skip is the
xdist gate on `tests/loadtest/test_load_mobile.py` (still runs with
`-n 0`; worker-killing under xdist, §4), plus the corrected Postgres
default **un-skipped** the entire previously-skipped `tests/integration`
suite.

---

## 8. Environment note

During triage, three orphaned processes from the research phase's stalled
full run were terminated: PID 46000 (pytest master, started 19:25, silent
since 20:19) and execnet workers PIDs 44900 / 46832. They were leaked
diagnostic processes, not user work.

---

## 9. Run #3 findings (third full-suite completion run, xdist `-n 2`)

The third full-suite run died at **95%** with **no summary emitted**.

### Two new worker crashes (faulthandler dumps) → two new xdist gates

| node id | failure mode | gate | deeper fix (not applied) |
|---|---|---|---|
| `tests/ui/test_freight_exchange_connect.py::TestConnectAction::test_connect_sets_connecting_state` | native crash under xdist (worker died with this test as the current frame; dump cites `test_freight_exchange_connect.py:314`) | `@pytest.mark.skipif(bool(os.environ.get("PYTEST_XDIST_WORKER")), …)` — honest reason "Native crash under xdist … runs with -n 0; deeper fix = investigate Qt/webengine teardown" | investigate Qt/webengine teardown (shown `QMainWindow` + OAuth loopback thread racing widget destruction) |
| `tests/e2e/test_e2e_api_flows.py::TestRoutePlanningFlowViaAPI::test_e2e_route_planning_via_api` | worker death under xdist (dump cites `test_e2e_api_flows.py:698`) | same pattern — honest reason "Worker death under xdist … runs with -n 0; deeper fix = event-loop/fixture isolation" | event-loop/fixture isolation for the `client_with_mocks` TestClient session |

Both were verified **PASS serially first** (`-q -n 0 --tb=short`, exit 0)
before gating — i.e. they are xdist-only failures, not real failures.
Both now **SKIP cleanly** under `-q -n 2` (exit 0) with the honest reason
strings above. Same pattern as `tests/test_api/test_route_demo.py:247`,
`tests/test_api/test_oauth2.py:151`, `tests/copilot/test_audio_recorder.py:300`.

### Other run #3 anomalies (unidentified — no gates applied)

* An **unidentified ~250-test setup-error (E) block around 89–90%** of the
  run — same signature class as the §3 E-blocks, root cause not yet pinned.
* The run **terminated at 95%** with a `pytest_sessionfinish` **OSError
  ("cannot send (already closed?)")** after worker disconnects (**gw1,
  gw4**) — **no summary emitted**.
