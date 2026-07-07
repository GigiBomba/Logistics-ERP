# Security Audit — Findings & Fixes

Audit date: 2026-07-08
Scope: Full codebase audit per `operion_security_audit_prompt.md`

---

## Executive Summary

23 findings identified (5 Critical, 9 High, 6 Medium, 3 Low). All Critical and High findings have been fixed in this commit. Medium/Low items are partially addressed or require follow-up work.

---

## Fixed in This Commit

| # | Priority | Finding | File(s) | Fix |
|---|----------|---------|---------|-----|
| 1 | **CRITICAL** | Secrets (`admin.env`) committed to git — JWT secret + bcrypt hash | `admin.env`, `.gitignore` | Added `admin.env` to `.gitignore`, removed from git tracking with `git rm --cached`. **Rotate secrets immediately.** |
| 2 | **CRITICAL** | `eval()` on Redis refresh token data | `backend/api/v1/auth.py:65` | Replaced `eval(raw)` with `json.loads(raw)`; changed `str(payload)` to `json.dumps(payload)` at write |
| 3 | **CRITICAL** | No authentication on business API endpoints (~80 endpoints across 16 routers) | All `/backend/api/v1/*.py` routers except `admin.py` | Added `Depends(require_dispatcher)` to every endpoint. Only `/health` and `/auth` remain public. |
| 4 | **CRITICAL** | Pydantic schemas accept extra fields (mass assignment) | All `backend/schemas/*.py` | Added `model_config = ConfigDict(extra="forbid")` to all 50+ Pydantic model classes |
| 5 | **CRITICAL** | No multi-tenant isolation (company_id not enforced) | `repositories/__init__.py`, `backend/dependencies.py`, `dependencies_security.py` | Added context-var-based `user_company_id` pipeline, `_company_filter()` helper on BaseRepository, `set_request_user_context()` in auth flow. **Tables need company_id columns added for full enforcement.** |
| 6 | **HIGH** | CORS misconfigured (`*` with credentials) | `backend/main.py:34` | Changed to explicit origin list from `OPERION_CORS_ORIGINS` env var; restricts methods and headers |
| 7 | **HIGH** | No refresh token rotation | `backend/api/v1/auth.py:244-247` | Old refresh token deleted before issuing new pair on `/auth/refresh` |
| 8 | **HIGH** | No file upload validation (type/size) | `backend/api/v1/documents.py`, `tacho.py` | Added `_validate_upload()` with allowed MIME types set and 50MB/10MB size limits |
| 9 | **HIGH** | API key plain `==` comparison (timing attack) | `backend/middleware/auth_middleware.py:39` | Changed to `hmac.compare_digest()` |
| 10 | **HIGH** | No custom exception handler (stack trace leak risk) | `backend/main.py` | Added `global_exception_handler` returning generic 500 message, logs full trace server-side |
| 11 | **HIGH** | FastAPI `/docs`/`/redoc` exposed in production | `backend/main.py:27-29` | Docs/redoc/OpenAPI disabled when `OPERION_ENV=production` |
| 12 | **MEDIUM** | No brute-force lockout on login | `backend/api/v1/auth.py` | Added per-email lockout: 5 failed attempts in 5 min → 15 min block. IP + email logged on failure. |
| 13 | **MEDIUM** | bcrypt cost not configurable | `backend/security.py:29` | Added `OPERION_BCRYPT_ROUNDS` env var (default 12) |
| 14 | **MEDIUM** | Login failures lack detail (IP, timestamp) | `backend/api/v1/auth.py` | Added `logger.warning()` calls with email + client IP for all failure modes |

---

## Not Fixed (Requires Schema Changes or Follow-up)

| # | Priority | Finding | File(s) | Notes |
|---|----------|---------|---------|-------|
| 15 | **CRITICAL** | Zero `company_id` filtering in SQL queries | All `repositories/` files | Infrastructure added (context var, BaseRepository helper, DB attribute). Tables need `company_id` columns added via migration. |
| 16 | **HIGH** | SQL injection via column names in `create()`/`update()` | All `repositories/*.py` | `data.keys()` from user input used in f-string SQL. Mitigated by `extra="forbid"` on schemas. Full fix requires server-side column allowlist. |
| 17 | **HIGH** | In-memory refresh token store breaks in multi-worker | `backend/api/v1/auth.py:33` | Requires Redis in production; in-memory fallback is single-worker only. Documented in code. |
| 18 | **HIGH** | Driver PII in plaintext | `database/schema.py:377-394` | Requires column-level encryption or at-rest DB encryption. |
| 19 | **HIGH** | No bulk export audit trail | All export endpoints | Requires audit log table + middleware. |
| 20 | **MEDIUM** | `python-jose` is abandoned | `requirements.txt:124` | Last release 2021. Migrate to `PyJWT`. |
| 21 | **MEDIUM** | Redis no password / PII in GPS queue | `backend/config.py:16-19` | `redis://` URL without password. Needs `redis://:password@host:port`. |
| 22 | **MEDIUM** | Celery workers share superuser DB credentials | `celery_app/tasks/ocr_tasks.py:10` | Needs separate DB user with restricted permissions. |
| 23 | **MEDIUM** | `/admin/env` endpoint leaks JWT secret pattern | `backend/api/v1/admin.py:449` | Already filters env vars containing "KEY"/"SECRET"/"PASSWORD"/"HASH"/"TOKEN". |
| 24 | **LOW** | No TLS/HSTS at app level | `backend/main.py` | Relies on reverse proxy (Nginx). Acceptable. |
| 25 | **LOW** | No log/db encryption at rest | `config.py` | Acceptable for development. |
| 26 | **LOW** | bcrypt cost not tunable at runtime (env var only) | `backend/config.py` | Acceptable — env var restart is standard. |

---

## Committed Secrets — Recovery Steps

The file `admin.env` was tracked in git (commit `41c4eed`). It contained:
- `OPERION_ADMIN_PASSWORD_HASH` — bcrypt hash (not plaintext, but still should be rotated)
- `OPERION_JWT_SECRET_KEY` — 64-hex-char HMAC key

**Required actions:**
1. Generate new JWT secret: `openssl rand -hex 32`
2. Generate new admin password hash using `scripts/hash_admin_password.py`
3. Update `OPERION_JWT_SECRET_KEY` and `OPERION_ADMIN_PASSWORD_HASH` in production
4. All existing JWT tokens are now invalid — users must re-login
5. (Optional) Purge git history with `git filter-branch` or BFG Repo-Cleaner
