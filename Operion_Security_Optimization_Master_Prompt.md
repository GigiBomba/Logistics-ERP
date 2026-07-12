# Operion ERP — Security Optimization Master Prompt
### For use with OpenCode-connected models (DeepSeek V4 Pro, Kimi, etc.)

**How to use this document:** Paste the relevant section(s) below as a standalone prompt to your coding AI. Each section is self-contained, prescriptive, and verification-gated — the AI must produce evidence (test output, scan output, diff) before the task is considered complete. Do not accept a summary claiming a fix is done; require the proof artifact specified in each "Verification" block. This mirrors your existing audit workflow (e.g. the company_id isolation fix) — AI-written executive summaries claiming completion are not sufficient evidence.

Run these roughly in the order below. Items 1–4 are the highest-severity, highest-frequency AI-coding failure modes and should be treated as blocking for any release.

---

## 1. Secrets Audit — Backend & Frontend

**Prompt:**
> Scan the entire Operion codebase (FastAPI backend, PySide6 client, and the new Vite/React website) for hardcoded secrets: API keys, database credentials, JWT signing keys, SMTP passwords, TIMOCOM/Trans.eu/Wialon/Frotcom/Traccar provider credentials, and any third-party tokens. Specifically check:
> - Any `.env` values that leaked into committed files
> - Any `VITE_`-prefixed environment variable in the website that contains a secret rather than a public-safe value (anything prefixed `VITE_` is bundled into client-side JS and is publicly readable)
> - Any secret embedded directly in PySide6 client source (the desktop client ships to end users' machines and can be reverse-engineered — it must never hold a backend secret, only a scoped user session token)
> - Hardcoded credentials in adapter modules (Wialon, Frotcom, Traccar, and the new TIMOCOM/freight-exchange adapters)
>
> Move every secret found to server-side environment variables, never exposed to a client. Produce a report listing: file, line, secret type, and the fix applied.

**Verification required:** `grep`/regex sweep output showing zero matches for common key patterns (`sk-`, `AKIA`, `-----BEGIN`, etc.) post-fix, plus a diff of each file changed.

---

## 2. Multi-Tenant Isolation (your RLS-equivalent)

Operion doesn't use Supabase, but the underlying risk is identical: PostgreSQL tables without enforced `company_id` scoping are the ERP's version of "RLS disabled." Given the prior audit already caught one incomplete fix here, treat this as recurring, not one-time.

**Prompt:**
> Audit every SQLAlchemy model and every FastAPI query in the backend. For each table containing `company_id`, confirm:
> 1. Every SELECT, UPDATE, and DELETE is filtered by the authenticated user's `company_id` at the query level — not filtered in Python after fetch, not trusted from a request parameter.
> 2. No endpoint accepts a `company_id` from the client and uses it directly; it must always be derived server-side from the authenticated session.
> 3. Write a failing-then-passing test for each table: authenticate as Company A, attempt to read/write a Company B record by ID, assert 403/404. The test must fail against the current code before the fix and pass after.
>
> Do not summarize this as "resolved" — output the actual failing test result, the code change, and the passing test result.

**Verification required:** Failing test output → diff → passing test output, per table. No exceptions for "internal" or "admin" endpoints — audit those too.

---

## 3. Server-Side Input Validation

**Prompt:**
> For every FastAPI endpoint, confirm request validation happens via Pydantic models on the server — not only via PySide6 form validation or React form validation on the website. Client-side validation is UX only and must never be the last line of defense.
> - Check invoice, CMR, tachograph, and dispatcher board endpoints specifically, since these accept the most complex nested input.
> - Check that string fields feeding into raw SQL (if any exist outside the ORM) are parameterized, never string-concatenated.
> - Check that file upload endpoints (tachograph `.DDD` files, PDF attachments) validate file type and size server-side, not just via the file picker.
> - For the website, verify the same Pydantic validation applies when the React frontend calls the shared FastAPI backend — the API must reject malformed input regardless of which client sent it.

**Verification required:** For each flagged endpoint, a curl/httpx request that bypasses the UI and sends invalid input, showing the server correctly rejects it (400/422), not a 500 or silent acceptance.

---

## 4. Authorization vs. Authentication (resource-level checks)

This is distinct from #2 — #2 is tenant isolation, this is *within-tenant* role/permission enforcement (e.g. a dispatcher shouldn't be able to hit an admin-only endpoint just because they're logged in).

**Prompt:**
> For every endpoint, confirm the check is "is this authenticated user permitted to perform this specific action on this specific resource" — not just "is there a valid token." Specifically:
> - Role-gated actions (bulk operations on the dispatcher board, financial report access, user management) must check role server-side.
> - Test: authenticate as a lower-privilege role, attempt each higher-privilege action directly via API call (not through the UI), confirm rejection.
> - Confirm the PySide6 client hiding a button/menu item is never the only protection — the backend must independently reject the action.

**Verification required:** Per-role test matrix showing attempted actions and pass/fail results.

---

## 5. Security Headers (website + API)

**Prompt:**
> Add the following headers to the FastAPI backend responses and the Cloudflare Pages-hosted website: `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Referrer-Policy`. For the CSP specifically, scope it to only the domains Operion actually needs (backend API origin, any map tile provider used for the route planner's Leaflet map, any font/CDN origins) — do not ship a wide-open CSP.

**Verification required:** Output of a headers scan (e.g. `curl -I` against staging, or securityheaders.com if the site is publicly reachable) showing each header present, before/after.

---

## 6. Static Analysis Sweep

**Prompt:**
> Run static analysis across the codebase: `bandit` for the Python/FastAPI backend, and an ESLint security plugin for the Vite/React/TypeScript website. Report every finding above low severity, triage each as true positive or false positive with justification, and fix all true positives. Add both scans to the CI/CD GitHub Actions pipeline so they run on every PR, not just this one-time pass.

**Verification required:** Scan output before fixes, diff of fixes, scan output after (should show the fixed findings cleared), and the CI workflow YAML showing the scan is now wired into the pipeline.

---

## 7. Dependency Audit

**Prompt:**
> Run `pip-audit` (or `safety`) against the backend's Python dependencies and `npm audit` against the website's Node dependencies. List every vulnerability found with severity, upgrade path, and whether the upgrade is a breaking change. Apply all non-breaking fixes immediately; for breaking-change fixes, propose a plan rather than applying blindly. Set this to run on a schedule (weekly GitHub Action) going forward, not just once.

**Verification required:** Audit output before/after, and the scheduled workflow file.

---

## 8. Security Monitoring / Logging

**Prompt:**
> Confirm the backend logs, at minimum: authentication attempts (success and failure), authorization failures (403s), and unusual query patterns (e.g. repeated cross-tenant access attempts caught by #2's checks). Logs must not contain secrets or full credentials. Propose where these logs should be shipped for retention/alerting given the current infra (self-hosted vs. managed — state the assumption), since without this a breach is discovered by a customer or a regulator instead of by Operion.

**Verification required:** Sample log output for each event type, confirmed to be secret-free (spot-check by grepping for common secret patterns in the log output itself).

---

## Notes on applying this to your workflow

- Consider folding items 6 and 7 (SAST + dependency audit) directly into your GitHub Actions CI so they're enforced automatically rather than repeated manually each release.
