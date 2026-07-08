# Operion ERP — Full Security Test Suite & Production-Readiness Prompt

**Context for the AI assistant:** You've now fixed and individually verified the findings from `SECURITY_AUDIT.md` and `SECURITY_AUDIT_VERIFICATION.md`. This prompt asks you to consolidate those one-off verification tests into a permanent, repeatable security test suite that runs in CI on every change — so a future code change can't silently reintroduce a fixed vulnerability. Do not treat this as writing new one-off scripts; treat it as building a permanent regression net.

Work through sections in order. Commit after each section. Show me actual test output (pass/fail counts), not a summary claim, at the end of each section.

---

## Section 1 — Test suite structure

1. Create a dedicated `tests/security/` directory, separate from general unit/functional tests, with these files:
   - `test_auth.py` — login, lockout, JWT lifecycle, refresh rotation, logout/revocation
   - `test_authorization.py` — RBAC (admin/dispatcher/user role gates), endpoint coverage (no endpoint left unprotected)
   - `test_tenant_isolation.py` — the company A/B isolation tests from the previous remediation pass, expanded to cover every tenant-owned table, not just the ones you tested first
   - `test_input_validation.py` — extra-field rejection, column allowlist injection attempts, file upload validation
   - `test_infrastructure.py` — CORS, security headers, docs exposure in prod mode, generic error handler / no stack trace leakage
   - `test_secrets.py` — confirms no secrets in repo (see Section 3), confirms constant-time comparison is used
   - `conftest.py` — shared fixtures: two test companies (A, B) each with a full set of test users (admin/dispatcher/regular) and sample data (trip, invoice, client, driver, truck), plus a helper to get an auth token for any of them
2. Use pytest. All tests must be independently runnable and not depend on execution order or leftover state from a previous test — each test should set up and tear down its own data (or run inside a transaction that's rolled back).
3. Confirm the test DB is never the real dev/prod database — a separate SQLite file or a dedicated test Postgres schema, created fresh per test run.

## Section 2 — Required test coverage (be exhaustive here, not illustrative)

### 2.1 Authentication
4. Correct credentials succeed; wrong password fails; wrong/unknown email fails (and both failure modes return the same generic error/timing profile — don't let "unknown email" vs "wrong password" be distinguishable by response).
5. Lockout triggers after N failed attempts, blocks even correct credentials during the window, and releases after the window.
6. JWT expires at the configured lifetime — a token used 1 second after expiry is rejected.
7. A tampered JWT (flip one character in the signature, or re-sign with a different/guessed secret) is rejected.
8. A JWT with `alg` changed to `none` is rejected (algorithm confusion check).
9. Refresh token rotation: reusing an already-exchanged refresh token fails.
10. Refresh token absolute lifetime: even with repeated valid refreshes, confirm there's an outer limit (or explicitly document that there isn't one yet, if that's still a known gap — don't let the test suite imply a protection that doesn't exist).
11. Logout actually invalidates the refresh token (a captured refresh token from before logout can't be used after).
12. Admin-via-env auth path gets the same lockout/logging treatment as normal users — or if it's intentionally exempt, the test documents that as a deliberate, reviewed decision rather than an oversight.

### 2.2 Authorization / RBAC
13. Parameterized test iterating every route in `app.routes`: each protected route rejects requests with no token, an expired token, and a token for a role that shouldn't have access (e.g. regular user hitting an admin-only route).
14. Role downgrade: if a user's role changes in the DB mid-session, confirm whether their existing token still grants old access, and assert the *actual* current behavior (don't assume) — flag to me if this is a gap so we can decide whether short token lifetimes are sufficient mitigation or whether token invalidation-on-role-change is needed.

### 2.3 Tenant isolation
15. For every tenant-owned table (trips, invoices, clients, drivers, trucks, route_history_v2, documents, receipts, and any others with company_id): a user in company A cannot read, update, or delete a record belonging to company B via direct ID reference, list endpoint filtering, search/filter parameters, or bulk export endpoints.
16. Confirm the read-only SQL sandbox endpoint (if still present) cannot be used to bypass company_id scoping — a dispatcher using it should not see cross-company data even via raw SQL, or the endpoint should be admin-only and explicitly out of scope for tenant scoping (tell me which).

### 2.4 Input validation & injection
17. Every write endpoint rejects unexpected extra fields (422).
18. Column-name allowlist rejects attempts to write to protected/internal columns (`id`, `company_id`, `created_at`) via the public API even if the field name matches a real column.
19. File upload endpoints reject: oversized files, disallowed MIME types, and a file with a mismatched extension-vs-content (e.g. a `.pdf` that's actually an executable) if that check exists — if it doesn't exist yet, add it and test it here rather than leaving it as a gap.
20. Confirm no repository method builds SQL via string concatenation/f-string of user-supplied values anywhere (a static grep-based test is acceptable here: fail the test if `execute(f"` or similar patterns appear in `repositories/`).

### 2.5 Infrastructure / transport
21. CORS: unapproved origins are rejected/not reflected in response headers.
22. Response headers include the basics: no `Server` header leaking framework/version detail, `X-Content-Type-Options: nosniff`, and confirm whether HSTS is set at the app level or intentionally deferred to the reverse proxy (document which).
23. `/docs`, `/redoc`, `/openapi.json` return 404 when `OPERION_ENV=production`.
24. Unhandled exceptions return a generic error body in all cases (test at least one deliberately broken code path), and the real trace still reaches server-side logs.
25. Rate limiting: confirm the 100 req/60s limit actually triggers a 429 in a test, and that hitting it doesn't leak whether the block is due to global limiting vs. login-specific lockout (these should look the same to an attacker probing which one they hit).

### 2.6 Secrets hygiene
26. A test (or pre-commit/CI script) that scans the repo for patterns resembling secrets (hex strings of JWT-secret length, `PASSWORD`, `SECRET_KEY`, `.env` files) and fails the build if any are staged for commit. This should run in CI on every push, not just once.
27. Confirm `.env`/`admin.env`/equivalent are in `.gitignore` and that `git status` shows them as untracked in a clean checkout.

## Section 3 — CI integration

28. Add (or update) a CI config (GitHub Actions, or whatever you're using) that runs the full `tests/security/` suite on every push and every pull request, separate from the general test suite so a security regression is impossible to miss in the diff/status check.
29. Make the security suite a required, blocking check — not advisory. A PR should not be mergeable if it fails.
30. Add the secret-scanning check (#26) as its own fast-running step that runs before the rest of the suite, so a committed secret is caught in seconds, not after a full test run.

## Section 4 — Dependency & supply chain scanning

31. Add `pip-audit` (or equivalent) as a CI step that fails the build on any known CVE in current dependencies. Run it now and report current findings, including the `python-jose` issue already flagged.
32. Set up (or document, if tooling isn't available in this environment) a recurring schedule for this scan — weekly is reasonable — not just a one-time run.

## Section 5 — Production security checklist

Produce a `PRODUCTION_SECURITY_CHECKLIST.md` that a human (you or me) can walk through before any production deploy, distinct from the automated test suite — things that are policy/config decisions, not code:

- [ ] All secrets rotated and stored outside git (confirm mechanism: env vars via deployment platform, secrets manager, etc.)
- [ ] `OPERION_ENV=production` set, confirmed docs/redoc disabled
- [ ] TLS/HTTPS enforced at the reverse proxy, HSTS header present
- [ ] Redis password-protected, not exposed on a public interface
- [ ] Celery workers use a restricted DB user, not superuser credentials
- [ ] Database backups configured AND a test restore has been performed (not just backups existing)
- [ ] Rate limiting and lockout thresholds reviewed for real-world traffic patterns (not just defaults)
- [ ] CORS origins list contains only real production client origins, no wildcards
- [ ] Full security test suite green in CI
- [ ] `pip-audit` clean or all findings explicitly accepted/documented
- [ ] Data retention / GDPR statement exists for driver PII (CNP, license numbers)
- [ ] Company_id migration fully complete with no legacy rows missing tenant assignment

## Section 6 — What to flag back to me rather than assume

- Any place where "add a test" surfaced a real gap that isn't actually fixed yet (e.g. role-downgrade token invalidation, HSTS at app level) — list these separately as **known gaps**, not folded into the test suite pass/fail count silently.
- Whether CI is GitHub Actions, something else, or not yet set up at all — tell me what exists today before assuming.

---

**Final step:** Run the entire `tests/security/` suite and paste the actual output (test names, pass/fail, count) — not a paraphrase. Then give me the one-paragraph plain-English status: what's now regression-proof, what's still a known gap, and what from the production checklist still needs a decision from me before you'd call this production-ready.
