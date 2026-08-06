# Operion ‚Äî Known Issues & Remaining Work

Status snapshot: **2026-08-04** ¬∑ Repos: `operion-website` (frontend @ `80112b6`), `Calculator logistica` (backend @ `fbd12d0` + work-in-progress uncommitted from this session).

This document consolidates every known non-blocking residual, pre-existing defect, and deferred item across both repos, with evidence and disposition. Blocking launch-readiness items are NOT listed here unless marked ‚Äî see `Operion_Website_Production_Readiness_Report.md`.

---

## 1. Deferred backend application bugs (surfaced by test-debt remediation)

Two of three were **fixed 2026-08-04** (see ¬ß2). One remains deferred:

| # | Bug | Evidence | Severity | Disposition |
|---|---|---|---|---|
| 1 | ~~`POST /api/v1/clients/` ‚Üí `ClientService.create(name=...)` TypeError 500~~ | **FIXED** ‚Äî router now calls `create(data.name, ...)` (positional); `_filter_repo_columns()` added so API-only fields (`company_code`/`city`) don't trip `_validate_columns`; 47 client tests green | High | ‚úÖ Fixed (residual sub-items: `PermissionService‚ÜíUserRepository.get_by_id` missing ‚Äî typed permission paths unusable; `add_contact` legacy field-name mismatch; persisting `company_code`/`city` needs a migration) |
| 2 | ~~Invoice generation crashes (nested tx, `document_links.company_id`, `doc_number` UNIQUE)~~ | **FIXED** ‚Äî `create_invoice_record` rolls back on IntegrityError (no dangling tx); `document_links.company_id` column + migration + index; collision-proof doc_number (transaction-guarded `BEGIN IMMEDIATE` + 5√ó retry); 62 invoice/doc tests green | Medium | ‚úÖ Fixed (residual: `/invoices/generate` endpoint-level company_id scoping is a separate multi-tenant task; stress test has a pre-existing wrong import path) |
| 3 | Pre-existing failures in untracked R3-era test files: `tests/test_api/test_trips_router.py`, `test_trips_endpoints.py`, `test_api_tacho.py`, `test_api_gps.py` | **FIXED** ‚Äî 14 baseline failures / 5 root-cause classes ‚Üí 36/36 green (tests aligned to real contract; no app changes: `created_at` mock shape, `page_size` vs `limit`, required `client_id`, tacho MIME `application/x-ddd`, GPS fixture env ordering) | Low | ‚úÖ Fixed |

**Remaining deferred (out of scope):** `/invoices/generate` endpoint-level multi-tenant company_id scoping ¬∑ `PermissionService` typed paths (missing `UserRepository.get_by_id`) ¬∑ `add_contact` legacy field mapping ¬∑ `company_code`/`city` persistence migration.

## 2. Fixed this session (backend test-debt remediation + deferred fixes, 2026-08-04)

- **`DatabaseManager.execute()` + `commit()` shims** ‚Äî mobile `db.execute`/`db.commit` sites unblocked; `ensure_mobile_tables()` wired into `init_db()`; `users.name`‚Üí`COALESCE(display_name, email)`; transport create sets `client_name` default.
- **Trip create‚Üíread chain** ‚Äî `TripRepository.create` sets `created_at`; trips table += `loading_city`/`delivery_city`/`reference`/`notes`/`updated_at` (migration + idempotent backfill); `_db_to_trip_result` NULL coercion; `_resolve_driver_id` `users.driver_id` fallback.
- **Clients** ‚Äî router‚Üíservice call fixed; `_filter_repo_columns()` guards create/update legacy paths.
- **Invoicing** ‚Äî rollback-on-IntegrityError; `document_links.company_id` + migration + index; collision-proof doc_number; best-effort document registration.
- **Test-support workarounds removed** ‚Äî conftest monkeypatches deleted; mobile write-path tests added (`TestMobileWriteEndpoints`, 6).
- **Result:** `tests/security/` + `test_auth_endpoints` ‚Üí **340 passed / 18 skipped / 0 failed**; mobile_security 18/0; combined critical 161 + clients/invoicing/trips/tacho/gps suites exit 0; upload Windows `0xc00000ff` crash eliminated.

## 3. Non-blocking residuals (documented, deliberately not closed)

| Item | Status | Evidence / Notes |
|---|---|---|
| Stryker mutation score | ‚úÖ **FIRST REAL SCORE: 67.32% / 67.41% covered-code** (482/716 mutants, 9m04s) ‚Äî `mutation-score.json` valid; ‚â• break 50 ‚Üí chain exit 0. `record-mutation-score.ts` was broken (wrote null) and is fixed. Survivor hot spots: queries.ts 60% (pagination/array-default assertions), auth-provider 79% | nightly workflow will track drift |
| Coverage gates | ‚úÖ **ALL FOUR MET: stmts 88.35% ¬∑ funcs 86.65% ¬∑ branch 76.27% ¬∑ lines 90%** (thresholds kept strict) ‚Äî 6 new integration test files (subscription 29, settings 22, profile 16, support 16, app-shell 15, blog-editor 14); 151 files / 1689 tests | minor flake: 3 settings-interactions tests under parallel vitest only (pass single-worker) |
| 3 e2e skips (backend-dependent) | returnUrl full cycle, password-reset full cycle, org-invite ‚Äî need a live backend + email capture | `e2e/critical/*.spec.ts` skip markers |
| Stripe live configuration | F4 addon‚Üíprice mapping + F5 reconciliation need real `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET` + populated `addon_price_mappings` rows | env-gated; mock `"mock": true` fallback when unset |
| Payment-leniency (¬ß4.6) | Correctly held pending legal/accounting sign-off | blueprint ¬ß4.6 |
| OG/sitemap seed fallback | sitemap + OG images use 18-slug seed when `BLOG_API_TOKEN`/`OPERION_BLOG_API_TOKEN` unset (blog API 401s at build) | `scripts/generate-{sitemap,og-images}.ts` graceful fallback |
| `reports/mutation/` untracked + not gitignored; `tsx` not a declared dependency | housekeeping | add `.gitignore` entry if desired |

## 4. Environment / ops notes

- **`.env` is NOT committed** (gitignored in both repos ‚Äî verified). Local `.env` ships `OPERION_ENV=production`, which makes any test/CI process importing `backend.main` boot in production mode (secure cookies, docs disabled). Mitigation exists in `tests/security/conftest.py` (pins `OPERION_ENV=test` before imports). **Recommended:** set `OPERION_ENV=test` explicitly in CI, and/or remove `OPERION_ENV=production` from the committed `.env.example` so devs set it per-context.
- **Scheduled task `OperionTestServices`** on this machine spawns a background test harness from a second repo copy (`C:\Users\Bonjo\source\repos\Calculator logistica`), stealing CPU and interleaving output. Dev-machine artifact only ‚Äî not a CI/repo concern. Disabled during remediation, re-enabled after.
- **Backend requires Python 3.10+** (PEP 604 in use); `run.bat`/scripts now reference `py -3.11`; Docker images `python:3.11-slim`.
- Nothing is pushed to any remote ‚Äî all commits are local.

## 5. Status legend

- ‚úÖ Done & verified ¬∑ üü° Documented residual (not blocking) ¬∑ ‚ùå Defect ‚Äî needs app-code fix ¬∑ ‚ö™ Process/environment note

## 6. Update (2026-08-04) ó all code-fixable residuals closed

**Fixed this session (gate-approved, see ß2 for mechanics):**
- `/invoices/generate` + `/{id}/send`: **tenant scoping** ó company_id derived from auth (never request body; body-smuggled `company_id:999` proven ignored), threaded through `generate_and_record`/`send_invoice_email` via `db.user_company_id`; repo `_company_filter()` gates all reads, `_set_company_from_context()` stamps writes; `create_record` delegates to `InvoiceRepository.create`; runtime isolation test proves company2 sees 0 of company1's invoices. `test_company_id_propagation.py` rewritten to the real context-based contract.
- **`PermissionService` typed paths unblocked** ó `UserRepository.get_by_id` added (all typed create/update/add_contact/delete previously raised AttributeError).
- **`add_contact` field mapping** ó API `name`/`position` ? repo `full_name`/`title` (no-op for callers already using column names).
- **`company_code`/`city` persist** ó real `clients` columns (schema + schema_pg parity + migration) round-trip API?service?repo?DB; `_filter_repo_columns` kept as defense.
- **Stress tests collect** ó import path `services.invoice_service` ? `services.invoicing.service`.
- **Frontend** ó 3 parallel-flaky settings tests hardened (state cleanup + waitFor 5000ms); `record-mutation-score.ts` `totalUndetected` = Survived-only (233) + `totalNoCoverage` (1), scores unchanged; `tsx ^4.23.7` declared.

**Verified:** backend invoicing 56 / critical 161 / clients 75 / safety net 602 ó all exit 0; frontend vitest 151 files / 1689 tests ◊2 + tsc clean; mutation-score.json regenerated valid.

**Remaining (documented caveats from final gate ó non-blocking):**
1. `POST /invoices/generate` accepts arbitrary `trip_data` in the body ó PDF *content* could show another tenant's visuals (DB row is correctly scoped to the caller). Pre-existing design; follow-up: validate `trip_data.trip_id` belongs to the caller's company.
2. Cross-tree pytest fixture quirk: mixing `tests/test_api/` with `tests/integration/` (or stress/loadtest trees without bridged conftests) in ONE invocation can report `fixture 'client_with_mocks' not found` ó pre-existing conftest directory-scoping behavior; no integration test uses that fixture. **CI hygiene: invoke test trees as separate pytest commands.**
3. Pre-existing, stash-proven, outside lane-owned suites: 4 contact/client_repository FK-fixture + month-grouping failures.
4. Not fixable from code (unchanged): 3 e2e skips (live backend), Stripe live keys (credentials), payment-leniency (legal), OG/sitemap seed fallback (needs `BLOG_API_TOKEN` at build).

## 7. Update (2026-08-04, second pass) ó remaining code-fixable issues closed

**Fixed this session (gate-approved):**
- **`trip_data` cross-tenant validation on invoice generation** ó `InvoiceService._validate_trip_ownership` (services/invoicing/service.py) runs at the top of `generate_and_record`, protecting `/invoices/generate`, `/{id}/send`, and desktop callers. A trip that exists but belongs to another company returns None via the company-scoped lookup ? 404 `resource/trip-not-found` (IDOR-safe, indistinguishable from missing). Admin + unscoped (desktop) callers skip. Ad-hoc trip_data without a trip_id is documented as bypassing the check (DB rows still scoped). +3 runtime tests in test_company_id_propagation.
- **`ClientRepository.get_revenue_history` GROUP BY bug** ó `GROUP BY month` bound to the generated `trips.month` column (created_at-based) instead of the `SUBSTR(start_date, 1, 7)` alias ? revenue buckets computed from created_at but labeled with start_date. Fixed to `GROUP BY SUBSTR(start_date, 1, 7)` + regression test proving same-start_date-month / different-created_at-month trips land in one correct bucket (repositories/client_repository.py:228, tests/test_client_repository.py).
- **4 pre-existing client/contact repository test failures** ó FK fixture bugs (contact/trip inserted with a client_id that had no clients row) fixed with proper seeded clients; `test_monthly_breakdown` aligned to the real contract with the grouping bug documented.
- **Cross-tree pytest fixture quirk** ó `tests/integration/conftest.py` now bridges the test_api fixtures (app/client/mocks/client_with_mocks, mirroring stress/loadtest conftests) AND the integration tree's global `ClientRepository` monkeypatches were moved into the `test_db` fixture with `monkeypatch` scoping so they no longer leak into `tests/test_api/`. Mixed-tree invocations now pass in one command.
- **2 of 3 e2e skips converted to mock-based full cycles** ó returnUrl full cycle (login ? land on original protected page, not /dashboard) and password-reset full cycle (forgot ? reset with test-controlled token ? login) now run as real UI-state tests. Critical tier: **52 passed / 1 skipped / 0 failed** (was 50/3/0).

**Verified:** backend ó invoicing 71, clients+integration combined 78, client/contact repos 44, critical 161, safety net 620 ó all exit 0 (mixed-tree invocation now green). Frontend ó e2e critical 52/1/0.

**Remaining (documented, not code-fixable or properly scoped feature work):**
1. **Missing invite-accept page/route (P1 feature gap, code-ready)** ó `src/routes.tsx` has no accept-invite route; `useAcceptInvitation` (queries.ts:541) + `organizationsApi.acceptInvitation` (endpoints.ts:426) are complete but unconsumed; backend `POST /api/v1/organizations/invitations/{token}/accept` works. Needs a new route (`/accept-invitation?token=`) + page wiring the existing hook. The org-invite e2e accept leg stays skipped with this precise reason until the page exists.
2. Not fixable from code (unchanged): Stripe live keys (credentials), payment-leniency (legal), OG/sitemap seed fallback (needs `BLOG_API_TOKEN` at build).

## 8. Update (2026-08-04, third pass) ó invite-accept page shipped; all code-fixable issues closed

**Fixed (gate-approved, two lanes + one remediation pass):**
- **Invite-accept page shipped** (`src/pages/public/accept-invitation.tsx`, route `path="accept-invitation"` public/CSR-not-prerendered): reads `?token=`, StrictMode-safe single-fire `useAcceptInvitation()`, five states (loading/success/already-accepted/error-with-code-distinction/invalid-link), Helmet titles, auth-page card/motion patterns. Wired the previously dead `useAcceptInvitation` hook (queries.ts:541) + `organizationsApi.acceptInvitation` (endpoints.ts:426). MSW accept handler added. 6 integration tests. **org-invite e2e accept leg un-skipped** (second context, mock-based, auth mocks added for determinism). Critical tier: **53 passed / 0 skipped / 0 failed** ó the last skip is gone.
- **Invite error-contract aligned** (gate follow-up #1): backend now emits distinct codes ó `invitation/invalid` (404), `invitation/expired` (400), `invitation/already-accepted` (409), email mismatch 403 unchanged (backend/errors.py + organizations.py accept restructure, +4 backend tests). MSW + frontend code-checks aligned to the real contract (already-accepted info state now reachable in production; was unreachable). MaintenanceGuard whitelist includes accept-invitation (gate follow-up #2). E2E second-context auth mocks added (gate follow-up #3). Contract tests on both sides added (gate follow-up #4).
- **Verified:** backend ó organizations 14, critical 161, exit 0; frontend ó vitest 152 files / 1695 passed / 0 failed, tsc clean, critical e2e 53/0/0, i18n:audit PASS.

**ALL code-fixable residuals are now closed.** Remaining (documented, not code-fixable): Stripe live keys (credentials), payment-leniency (legal), OG/sitemap seed fallback (needs `BLOG_API_TOKEN` at build).
