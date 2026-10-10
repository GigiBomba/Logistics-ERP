# Full Operion Test Suite — Timings & Results

Run date: **2026-10-07** · Machine: Windows (32 GB RAM, Python 3.11.9 / pytest 9.1.1, Node v24.16.0,
Playwright 1.61.1, Flutter 3.44.x) · Test services: Postgres 16 + Redis 7 containers (healthy).

All suites were run **strictly sequentially** (one batch at a time), pytest capped at `-n 2`
(repo's local worker cap) and Playwright at 2 workers, per the resource constraint.

## Result summary

| Suite | Mode | Tests | Passed | Failed | Skipped | Duration |
|---|---|---|---|---|---|---|
| Python pytest (`tests/`) | 8 × 1/8 shards + tail re-split 4 × 1/32, `-n 2 --dist=loadscope`; 19 xdist-gated files re-run serial (`-n 0`) | 23,023 collected | **0 failures** across all batches | 0 | ~1,183 (gates + env skips) | **69 m 38 s** |
| ui/ vitest | `npm test` | 362 | 362 | 0 | 0 | 46.7 s |
| website/ vitest | `npx vitest run --reporter=dot` | 2,536 | 2,536 | 0 | 0 | 122.8 s |
| website Playwright — chromium | `--project=chromium --workers=2` (final) | 285 | 280 | 0 | 5 | 6 m 12 s |
| website Playwright — firefox | `--project=firefox --workers=2` (final) | 285 | 279 + 1 flaky (passed on retry) | 0 | 5 | 13 m 36 s |
| website Playwright — webkit | `--project=webkit --workers=2` (final) | 285 | 280 | 0 | 5 | 8 m 30 s |
| mobile_app Flutter | `flutter test --reporter=expanded` | 1,976 | 1,976 | 0 | 0 | 84.5 s |
| **TOTAL** | | | | **0 failures (all platforms, all browser projects)** | | **≈ 1 h 42 m** |

> The total is the sum of the successful staged runs above. The investigation phase (initial
> stalled/failed shard-8 attempts, crash reproduction probes, fix verification) is additional wall
> time and is not part of the suite duration.

## Python pytest — staged breakdown

| Stage | Tests | Fail | Skip | Duration |
|---|---|---|---|---|
| shard 1/8 | 2,878 | 0 | 92 | 289.4 s |
| shard 2/8 | 2,878 | 0 | 204 | 327.7 s |
| shard 3/8 | 2,878 | 0 | 19 | 673.8 s |
| shard 4/8 (post-fix re-run) | 2,878 | 0 | 60 | 602.9 s |
| shard 5/8 | 2,878 | 0 | 2 | 411.4 s |
| shard 6/8 | 2,878 | 0 | 0 | 508.0 s |
| shard 7/8 | 2,878 | 0 | 135 | 541.3 s |
| tail (groups 29–32 of 32) | 2,863 | 0 | 358 | 492.0 s |
| serial xdist-gated pass (19 files, one process each) | 655 | 0 | 1 | 331.5 s |

The monolithic 1/8 tail batch was re-split into four 1/32 batches after a Qt worker crash late in
the run left the xdist controller waiting on a lost completion event; the batched form completes
cleanly.

## Issues found and fixed

1. **API dashboard resume bug** — `ui/views/api_dashboard_view.py`
   `test_timer_restarts_after_shutdown_wakeup` failed deterministically (shard 4):
   `wakeup()` neither restarted the timer stopped by `shutdown()` nor refreshed when the
   in-flight guard was still set (a stale/suspended poll), leaving the dashboard stale after a
   power-resume. Fixed: `wakeup()` restarts the 30 s timer and forces a fresh poll
   (`_refresh_status(force=True)`). Verified: file 26/26 serial ×2 and under xdist.
2. **Copilot signals worker crash** — `tests/ui/signals/test_copilot_signals.py`
   Under xdist, gw0 died twice in the `GuidedOverlayWidget` overlay fixture at `QTest.qWait(50)`
   (native Qt access violation), and the worker loss wedged the controller at session end.
   The file passes 15/15 with `-n 0`. Added the repo's documented module-level xdist gate
   (honest reason; serial coverage preserved) and registered the file in
   `scripts/run_pytest_guarded.py` `GATED_FILES`; serial re-run green.
3. **Guarded runner console crash** — `sys.stdout.write` died on a cp1252-incompatible character
   at the end of shard 1 (UnicodeEncodeError), losing the summary. Mitigated by running with
   `PYTHONIOENCODING=utf-8` (no code change); all subsequent shard summaries captured.
4. **Cross-browser suites (firefox + webkit) brought to zero failures** — the 44 per-browser
   visual baselines per project were missing, so they were generated (44 firefox + 44 webkit
   `*-win32.png`); the 6 webkit waitlist baselines were regenerated once after the deterministic
   counter gate below changed the captured frame. All residual functional failures were fixed
   (items 5–9); firefox/webkit now run all 285 tests with 0 failures (firefox reports 1 flaky —
   passed on retry).
5. **Hydration gate hardened** — `website/e2e/helpers.ts`: `waitForFormReady` now polls the
   form's own React `onSubmit` (not just the button's props) plus a 100 ms settle. This removes
   the native-form-GET race (`/login?email=…`) behind the firefox MFA / password-reset flakes.
6. **Deterministic waitlist counter** — `visual-regression.spec.ts` waits for the mocked target
   text `500+` instead of a fixed 1800 ms sleep (webkit dark diffs were catching the counter
   mid-animation).
7. **Cold-route headroom** — `playwright.config.ts` expect timeout 10 s → 20 s: SPA link clicks
   trigger on-demand vike-dev route compiles that exceeded 10 s under loaded cross-browser runs
   (auth-flow / v3-navigation / download-flow URL flakes).
8. **CTA readiness gate** — `checkout-upgrade.spec.ts` polls for React props on the upgrade CTA
   before clicking (firefox flake: the checkout POST never fired).
9. **Robust checkbox toggle + strict locator** — `auth-flow.spec.ts`: the terms checkbox is
   toggled via keyboard (the sticky header intercepted the pointer click on firefox) and the
   verify-email assertion targets the heading (the `<title>` made `getByText` a strict-mode
   violation once client-side titles updated). Local `retries: 1` added (CI keeps 2); retried
   tests are reported as "flaky", never silently passed.

## Environment issues resolved in the follow-up (2026-10-10)

- **Tacho native crash — root-caused and fixed.** Bisection over the shard-8 serial prefix
  (49 files, ~870 tests) isolated it to `tests/test_sync_ui_integration.py::TestConflictDialog`:
  unparented `SyncConflictDialog` widgets left to the cyclic GC were finalized during a later
  test's event loop (the tacho `view_with_db` fixture's `qtbot.wait`) and crashed the process.
  The dialog tests now register every dialog with `qtbot.addWidget` (close + deleteLater in
  pytest-qt teardown). Reproducer: 3/3 crashes before → 3/3 green after; the full 1,004-test
  serial prefix is green; the file's xdist gate was removed and it passes 10/10 under `-n 2`
  and 2/2 serial.
- **xdist crash wedge — fixed via vendored upstream patch.** pytest-xdist 3.8.0's
  `LoadScopeScheduling.remove_node` re-queues a crashed worker's completed scopes as empty work
  units, wedging the controller at session end (upstream issues #1323/#1378; fix merged in
  PR #1324 but unreleased as of 3.8.0). `tests/conftest.py` now feature-detects the buggy line
  and applies an equivalent monkeypatch — disable with `OPERION_XDIST_WEDGE_FIX=0`; delete the
  shim once xdist > 3.8.0 ships. Red/green: with the shim disabled, a synthetic `os._exit(1)`
  repro stalls (guard kills it after 60s of silence, exit 2); with the shim enabled the same
  repro completes in ~4s with the crash reported. Tail batches g29–g32 and a mid shard remain
  green with the shim active.
- The remaining xdist-gated files (native Qt crashes with no reproduction outside long loaded
  shards) stay gated; a stray crash can no longer hang a session thanks to the wedge fix.

## Artifacts

- Raw machine log: `logs/full_suite_timing.log` (one `TIMING|...` line per run).
- Per-run logs/JUnit XML: `logs/pytest_shard*.xml`, `logs/tail32_g*.xml`, `logs/serial_*.xml`.
- Suite logs: `logs/ui_vitest.txt`, `logs/website_vitest.txt`, `logs/playwright_chromium3.txt`,
  `logs/flutter_test.txt`.
