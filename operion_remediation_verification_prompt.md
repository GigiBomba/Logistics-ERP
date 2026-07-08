# Operion ERP — Remediation Completion & Verification Prompt

**Context for the AI assistant:** You previously produced `SECURITY_AUDIT.md` claiming 14 findings "Fixed in This Commit." On review, at least one of those (#5, multi-tenant isolation) is NOT actually fixed — it is the same underlying vulnerability as #15 in your own "Not Fixed" table, which you acknowledged requires schema changes you did not make. This means the executive summary's claim that "All Critical and High findings have been fixed" is false. Do not repeat this pattern. From this point forward, a finding may only be marked "Fixed" if it is accompanied by a passing automated test that fails on the pre-fix code and passes on the post-fix code. If you cannot write such a test for a given finding, mark it "Unverified" and say so explicitly — do not upgrade its status based on code review alone.

Work through the sections below in order. Do not skip ahead. Commit after each numbered section with a message naming the finding number(s) it resolves.

---

## Section 1 — Finish the incomplete Critical fixes first

### 1.1 Multi-tenant isolation (findings #5 / #15)
This is the highest priority item in the whole audit. The plumbing (context var, `_company_filter()` helper) already exists but is not connected to real data.

1. Add a `company_id` column (foreign key to `companies.id`, `NOT NULL`) to every table that represents tenant-owned data: trips, invoices, clients, drivers, trucks, route_history_v2, documents, receipts, and any other table holding per-company records. List every table you add it to.
2. Write a migration script that backfills `company_id` on existing rows before adding the `NOT NULL` constraint (if there is existing data, ask me how to map it — do not guess or default it silently).
3. Update every repository method (not just reads — creates, updates, deletes too) to apply `_company_filter()` or an equivalent `WHERE company_id = ?` clause. Go file by file through `repositories/` and confirm each one. List every file you touched.
4. Write an isolation test: create two companies (A and B), create a trip/invoice/client/driver under each, authenticate as a user in company A, and assert that every list/get/update/delete endpoint returns 404 or an empty result — never company B's data — when given company B's IDs. This test must actually call the API, not just the repository function directly.
5. Show me the test output (pass) before and (fail) after temporarily reverting the `company_id` filter, to prove the test would have caught the original bug.

### 1.2 SQL injection via column names (finding #16)
1. Go through every repository's `create()` and `update()` method. For each, replace whatever builds the column list (`data.keys()`, `**kwargs`, etc.) with an explicit hardcoded allowlist of valid column names per table — defined as a constant at the top of each repository file, not derived from the incoming payload.
2. Confirm any column name not in the allowlist is rejected with a clear error, not silently dropped.
3. Write a test that attempts to pass a malicious/unexpected key (e.g. `"; DROP TABLE trips;--"` or a real column name that shouldn't be user-writable, like `company_id` or `id`) into a create/update call and asserts it's rejected.

### 1.3 Secret rotation & git history (from the "Committed Secrets" section)
1. Confirm explicitly: was this repository ever pushed to a remote (GitHub/GitLab/etc.), or has it only ever existed locally? Tell me which, and how you determined that.
2. If it was ever pushed: walk me through purging it from history with the BFG Repo-Cleaner (safer/simpler than `git filter-branch`) — give me the exact commands, and confirm afterward with `git log --all --oneline -- admin.env` that no trace remains in any branch or reflog.
3. Confirm the JWT secret and admin password hash have actually been rotated in the running production environment (not just generated) — show me the env var is different from the one that was committed.
4. Confirm all previously issued JWT tokens are now rejected (test: use an old token captured before rotation, confirm it now returns 401).

---

## Section 2 — Verification tests for everything else marked "Fixed"

For each of these, write a test that specifically targets the vulnerability, and show it failing against a checked-out pre-fix commit (or a manually reverted snippet) and passing on current code:

5. **#2 (eval → json.loads):** Test that a malformed/malicious string in the Redis refresh-token value cannot execute code — e.g. store a string containing Python syntax like `__import__('os').system(...)` and confirm it's treated as inert data, not executed.
6. **#3 (auth on all endpoints):** Write a test that hits every route registered in the app (introspect via FastAPI's `app.routes`) with no `Authorization` header and asserts every single one returns 401/403 except the explicitly public ones (`/health`, `/auth/token`, `/auth/refresh`, docs if enabled). This should be one parameterized test that lists all routes, not 80 manually written tests.
7. **#4 (extra="forbid"):** Test that POSTing an extra/unexpected field to a couple of representative endpoints (trip create, client create) returns a 422, not a silent success.
8. **#6 (CORS):** Test that a request with `Origin: https://evil.example.com` is rejected/not reflected back in `Access-Control-Allow-Origin`.
9. **#7 (refresh rotation):** Test that using the same refresh token twice — once to get a new pair, then again — fails the second time.
10. **#8 (upload validation):** Test that an oversized file and a disallowed MIME type are both rejected before reaching OCR/Celery processing.
11. **#9 (constant-time API key compare):** This one is hard to test for timing directly — instead, just confirm via code inspection that `hmac.compare_digest` is used, and note in the report that timing itself isn't practically testable in CI.
12. **#10 (generic error handler):** Test that triggering an unhandled exception (e.g. a deliberately broken endpoint in a test-only route, or mocking a repository to raise) returns a generic 500 body with no stack trace or file path, while confirming the full trace still lands in the server-side log.
13. **#11 (docs disabled in prod):** Test that with `OPERION_ENV=production` set, `/docs`, `/redoc`, and `/openapi.json` all return 404.
14. **#12 (lockout):** Test 6 consecutive failed logins for the same email and confirm the 6th is blocked even with the correct password, and that it unblocks after the window.
15. **#13 (bcrypt rounds configurable):** Test that changing `OPERION_BCRYPT_ROUNDS` actually changes the cost factor of newly hashed passwords.

---

## Section 3 — Report format

Rewrite `SECURITY_AUDIT.md` (or add `SECURITY_AUDIT_VERIFICATION.md`) with a table like this for every finding, Critical through Low:

| # | Finding | Status | Test file/function that proves it | Verified? |
|---|---|---|---|---|

Status must be one of: **Fixed & Verified**, **Fixed, Unverified** (explain why no test was possible), or **Not Fixed** (with the real blocker, like the schema change needed for company_id). No finding may say "Fixed" alone without one of these qualifiers.

---

## Section 4 — What I still need to decide (ask me, don't assume)

Flag these back to me rather than guessing:
- How to backfill `company_id` on any existing production data (I need to confirm the mapping).
- Whether to purge git history now or whether the repo was always local-only.
- Whether `python-jose` → `PyJWT` migration (finding #20) should happen now or be scheduled separately, since it touches every token-decoding code path and needs its own test pass.

---

**Final step:** Once all of Section 1 and 2 are done and verified, commit the updated audit report and give me a one-paragraph plain-English summary of what is now actually safe versus what still needs schema/infra decisions from me.
