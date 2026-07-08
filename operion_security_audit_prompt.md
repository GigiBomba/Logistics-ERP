# Operion ERP — Security Audit Prompt for AI Coding Assistant

**Instructions for the AI assistant:** Answer every question below by inspecting the actual codebase (not from memory or assumption). For each item, state: (1) current behavior with file/line references, (2) whether it is a vulnerability, (3) a concrete fix if needed, (4) a verification step to prove the fix works (test, curl command, or script). Do not mark anything "fixed" without showing the verification output. Commit after each section with a message describing exactly what changed and why.

---

## 1. Authentication (login, password, tokens)

1. Show me the exact bcrypt configuration (cost factor / rounds). Is it tunable via env var, and what's the current value in production config?
2. Is there a timing-safe comparison anywhere passwords or tokens are checked, or could an attacker learn info from response-time differences?
3. Is there any rate limiting or lockout specifically on `POST /api/v1/auth/token` separate from the general 100/60s limiter? What stops a brute-force script from trying thousands of email/password combos?
4. Are login failures logged with enough detail to detect a brute-force attempt (IP, email attempted, timestamp), without logging the password itself?
5. What is the JWT signing secret — where is it stored, how long is it, and is it the same secret across dev/staging/prod?
6. Is the JWT algorithm hardcoded server-side (`HS256`), or does the code trust an `alg` field from the token header itself? (This is the classic "alg: none" / algorithm confusion vulnerability — verify the decode call pins the algorithm explicitly.)
7. Where is the refresh token stored server-side (Redis or in-memory dict per your notes)? If in-memory dict — what happens to sessions on a multi-worker Gunicorn deployment where each worker has its own memory? Could this let a revoked token still work on a different worker?
8. When a refresh token is used to get a new access token, is the old refresh token invalidated (rotation), or can the same refresh token be replayed indefinitely until it expires?
9. Is there an absolute expiration on refresh tokens, or can a user stay logged in forever by refreshing repeatedly?
10. On logout, is the refresh token actually deleted from the store, or just the client-side token discarded? Can a stolen refresh token still be used after the legitimate user "logs out"?
11. Does the admin-via-env-variable auth path bypass any of the same protections (rate limiting, logging, lockout) that normal users get? Is the admin password ever logged or exposed in error messages, tracebacks, or Celery task args?

## 2. Authorization / RBAC

12. Walk through `require_admin` and `require_dispatcher` — do they check the role from the decoded JWT claims, or do they re-query the database each time? If from the JWT, what happens if a user's role is downgraded — does their existing token still grant old permissions until it expires?
13. List every endpoint that does NOT have a `Depends(get_current_user)` (or similar) attached. Which of these are intentionally public, and which are accidentally unprotected?
14. Is there object-level authorization, or just role-level? Example: can a dispatcher at Company A fetch trip/invoice/client records belonging to Company B just by guessing an ID (IDOR)? Show me the check that ties `company_id` from the JWT to the `company_id` filter in every repository query.
15. Pick 5 endpoints that accept a resource ID (trip_id, client_id, invoice_id, driver_id, truck_id) — for each, confirm the service/repository layer filters by the requesting user's company_id, not just the raw ID.

## 3. Multi-tenancy isolation

16. Is there a single shared database with a `company_id` column enforced everywhere, or could a bug in one query leak cross-company data? Search for any raw SQL query in `repositories/` missing a `company_id =` clause.
17. Are file uploads (documents, CMR scans, OCR inputs) stored in a path scoped by company_id, or in a flat shared directory where a predictable filename could let one company access another's files?

## 4. Input validation & injection

18. Are all SQL queries using parameterized queries / bound parameters everywhere, or is there any string concatenation or f-string building of SQL anywhere in `repositories/`? (Search explicitly for f-strings or `.format()` near `execute(`.)
19. Do Pydantic v2 schemas reject unexpected/extra fields (`model_config = ConfigDict(extra="forbid")`), or do they silently ignore extra fields a client sends (which can mask attempted mass-assignment attacks)?
20. For the read-only SQL sandbox endpoint (SQLite `mode=ro`) — is it actually reachable only by admins? What happens if someone runs a query with `ATTACH DATABASE` or PRAGMA statements — are those blocked?
21. Are file uploads (documents, tachograph `.DDD` files) validated for file type/size/content before processing, or does the OCR/Celery pipeline blindly process whatever is uploaded? Could a malicious file cause a zip-bomb, decompression bomb, or trigger code execution in a parsing library?

## 5. Secrets & configuration

22. Where do `OPERION_API_KEY`, JWT secret, database credentials, and Redis credentials live — `.env` file, hardcoded, environment variable, or a secrets manager? Is `.env` in `.gitignore`? Run a check for any committed secrets in git history.
23. Is the API key (`X-API-Key`) compared with a constant-time comparison, or a plain `==` (timing attack surface, minor but easy to fix)?
24. Does the FastAPI `/docs` and `/redoc` exposure in production leak internal schema details (table names, field names) that aid an attacker? Should these be disabled or gated behind auth in production?

## 6. Redis & Celery

25. Is Redis password-protected and not exposed on a public network interface? Since Redis is broker + cache + telemetry aggregator per your architecture, does anything sensitive (tokens, PII, password hashes) get written into Redis keys or Celery task payloads in plaintext?
26. Are Celery tasks validated so an attacker with API access can't queue arbitrary task names/payloads? Is there a task allowlist?
27. If OCR/PDF Celery workers run as a separate process, do they have their own least-privilege database credentials, or the same superuser credentials as the API?

## 7. Transport & network

28. Is TLS enforced (HTTPS-only) in production, or can the API be hit over plain HTTP? Is there an HSTS header?
29. What does CORS config look like — is `allow_origins` a wildcard `*`, or scoped to the actual desktop client / known origins? Combined with cookies or Authorization headers, a wildcard here is a real risk.
30. Is the rate limiter (100 req/60s per IP) applied per-IP only? For users behind NAT/corporate proxy sharing one IP, does this cause false lockouts — and conversely, can an attacker rotate IPs/proxies to bypass it entirely?

## 8. Logging, error handling, PII

31. Do error responses returned to the client ever include stack traces, SQL, or internal file paths (common with default FastAPI/Starlette exception handlers in debug mode)? Confirm `debug=False` in production and a custom exception handler that returns generic messages.
32. Does `logging_middleware.py` ever log full request bodies? If so, could that capture passwords, tokens, or driver personal data (CNP, license numbers) in log files?
33. Are logs, and database backups, encrypted at rest? Who has access to them?

## 9. Dependency & supply chain

34. Run a dependency audit (`pip-audit` or equivalent) against the current `requirements.txt`/`uv.lock` — list any known CVEs, especially in FastAPI, Pydantic, python-jose/PyJWT, bcrypt, and any PDF/OCR libraries.
35. Since you're on Python 3.9 by mandate — confirm the JWT library in use is still receiving security patches and isn't an abandoned package pinned for 3.9 compatibility.

## 10. Data protection specifics (Romanian/EU context)

36. Driver personal data (CNP — Romanian personal numeric code, license numbers) and client data are processed — is there a documented data retention policy, and is this data encrypted at rest given GDPR obligations?
37. Who can export/download the full client or driver list, and is that action logged (audit trail) given it's the kind of bulk-export that matters most in a data breach?

---

**Final step:** After going through all sections, produce a short prioritized list (Critical / High / Medium / Low) of every actual finding — not restating the questions — with the specific file and line number for each, and commit that list as `SECURITY_AUDIT.md` in the repo root.
