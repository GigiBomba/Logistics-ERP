# TEST_BASELINE

Pre-change baselines captured **2026-09-20**. No test files or test configs were modified.

| suite | command (workdir) | collected | passed | failed | skipped | xfailed | wall time | date |
|---|---|---|---|---|---|---|---|---|
| ui vitest | `npm test` (ui/) | 362 | 362 | 0 | 0 | 0 | 9.2s | 2026-09-20 |
| website vitest | `npx vitest run --reporter=dot` (website/) | 2,537 | 2,537 | 0 | 0 | 0 | 57.0s | 2026-09-20 |
| website e2e (chromium) | `npx playwright test --project=chromium --reporter=line -c e2e/playwright.config.ts` (website/) | 857 listed (3 projects) / 285 run (chromium) | 186 | 99 | 0 | 0 | 235.3s | 2026-09-20 |
| pytest | `python -m pytest -n 2 --timeout=600 --timeout-method=thread --durations=20 --ignore=tests/test_silent_chromium.py --ignore=tests/test_chart_export.py` (repo root) | 23,162 | 21,593 | 35 | 225 | 3 | ~100 min (INCOMPLETE, see notes) | 2026-09-20 |
| flutter | `flutter test --reporter=expanded` (mobile_app/) | 1,942 | 1,942 | 0 | 0 | 0 | 39.2s | 2026-09-20 |

## Artifacts

- `baseline_pytest.txt` - full pytest run output (run stopped by harness at ~99%; file is UTF-16 LE).
- `baseline_pytest_failures.txt` - verbatim FAILED test node IDs (35).

## Notes / blockers

- **ui vitest**: `ui\node_modules` was broken (react missing; `vitest/config` unresolvable -> `ERR_MODULE_NOT_FOUND`).
  Fixed by `npm install` in `ui/` (lockfile applied cleanly, no drift). `npx vitest list` now lists 362 tests.
- **website vitest**: exact `npx vitest list 2>$null` count = 2,537 lines (matches run count). 0 failures.
- **website e2e**: `webServer.command` (`npx vite --port 3000`) fails to boot with vike's `CACError: Unknown option '--port'`.
  Workaround without touching configs: booted `npx vite` manually (vite.config.ts pins `server.port: 3000`) and Playwright
  reused it (`reuseExistingServer: true`). Chromium run: 186 passed / 99 failed (visual-regression pixel diffs +
  waitlist-flow & several auth/nav specs). Only chromium project executed; firefox/webkit not run.
- **pytest**: run could not complete in this environment - stopped by harness at ~99% after ~100 min, then repeated twice
  more with same stall. Blockers: (a) PySide6/Qt tests raise `access violation` / `libshiboken ... already deleted`,
  crashing xdist workers (`[gwN] node down`); (b) headless Chrome cannot start for choreographer/chart-export tests
  (1,109 setup errors; `test_silent_chromium.py` + `test_chart_export.py` excluded from the baseline run - 42 tests);
  (c) a tail test hangs indefinitely (thread-based `--timeout=600` cannot interrupt native waits). Counts above cover
  the 22,968 tests that reported; the 35 failures match the expected ~30 pre-existing. Postgres-dependent failures
  (`test_connection_pool_pg`, `test_postgresql_compat`, `test_import_to_pg_sanitize`) require a running PostgreSQL.
  `.venv` has no pytest module - used system Python 3.11.9 / pytest 9.1.1.
- **flutter**: `flutter 3.44.6` available; all 1,942 tests passed.