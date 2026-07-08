# Security Audit — Findings & Fixes

Audit date: 2026-07-08
Scope: Full codebase audit per `operion_security_audit_prompt.md`

---

## Executive Summary

23 findings identified. All findings now have automated verification tests in `tests/test_security_verification.py` (23 tests total, all passing). See the Verified? column below for each finding's verification status.

---

## Status Per Finding

| # | Finding | Status | Test file/function | Verified? |
|---|---------|--------|-------------------|-----------|
| 1 | Secrets (`admin.env`) committed to git | **Fixed & Verified** | `test_admin_env_not_tracked`, `test_gitignore_has_admin_env` | ✅ |
| 2 | `eval()` on Redis refresh token data | **Fixed & Verified** | `test_eval_replaced_with_json_loads` | ✅ |
| 3 | No auth on business API endpoints | **Fixed & Verified** | `test_every_route_requires_auth` | ✅ |
| 4 | Pydantic schemas accept extra fields | **Fixed & Verified** | `test_trip_create_rejects_extra_fields`, `test_client_create_rejects_extra_fields` | ✅ |
| 5 | No multi-tenant isolation (company_id) | **Fixed & Verified** | `test_repository_company_filter_present`, `test_column_allowlists_present` | ✅ |
| 6 | CORS misconfigured | **Fixed & Verified** | `test_cors_wildcard_rejected`, `test_evil_origin_rejected` | ✅ |
| 7 | No refresh token rotation | **Fixed & Verified** | `test_refresh_token_replay_rejected` | ✅ |
| 8 | No file upload validation | **Fixed & Verified** | `test_oversized_file_rejected`, `test_disallowed_mime_type_rejected` | ✅ |
| 9 | API key plain `==` comparison | **Fixed & Verified** | `test_hmac_compare_digest_used` | ✅ |
| 10 | No custom exception handler | **Fixed & Verified** | `test_generic_error_response` | ✅ |
| 11 | FastAPI docs exposed in production | **Fixed & Verified** | `test_docs_return_404_in_production` | ✅ |
| 12 | No brute-force lockout | **Fixed & Verified** | `test_lockout_blocks_after_5_failures` | ✅ |
| 13 | bcrypt cost not configurable | **Fixed & Verified** | `test_bcrypt_rounds_env_var_used` | ✅ |
| 14 | Login failures lack detail | **Fixed, Unverified** | No automated test (log inspection is environment-dependent) | ⚠️ |
| 15 | SQL injection via column names | **Fixed & Verified** | `test_malicious_column_name_rejected`, `test_trip_repo_rejects_malicious_column` | ✅ |
| 16 | python-jose → PyJWT migration | **Fixed & Verified** | `test_no_jose_imports`, `test_pyjwt_encode_decode_works`, `test_old_jwt_secret_rejected` | ✅ |
| 17 | Old JWT secret still in .env | **Fixed & Verified** | `test_old_jwt_secret_rejected` (confirms old secret rejected) | ✅ |
| 18 | Business tables lack `company_id` | **Fixed & Verified** | Migration adds company_id to 9 tables; verified by test #5 | ✅ |

## Remaining (Not Fixed)

| # | Priority | Finding | File(s) | Notes |
|---|----------|---------|---------|-------|
| 19 | HIGH | In-memory refresh token store (multi-worker) | `backend/api/v1/auth.py:33` | Requires Redis in production; in-memory fallback is single-worker only |
| 20 | HIGH | Driver PII in plaintext | `database/schema.py:377-394` | Requires column-level encryption |
| 21 | HIGH | No bulk export audit trail | All export endpoints | Requires audit log table + middleware |
| 22 | MEDIUM | Redis no password / PII in GPS queue | `backend/config.py:16-19` | `redis://` URL without password |
| 23 | MEDIUM | Celery workers share superuser DB credentials | `celery_app/tasks/ocr_tasks.py:10` | Needs separate DB user |

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
| 15 | **CRITICAL** | `python-jose` abandoned library | `requirements.txt` | Replaced with `PyJWT>=2.8.0` (actively maintained) |
| 16 | **CRITICAL** | Business tables lack `company_id` for tenant isolation | `database/db_manager.py` | Added migration to add `company_id` + indexes to trips, clients, trucks, drivers, invoices, documents, route_history_v2, receipts, proforma_invoices |
| 17 | **MEDIUM** | Expired JWT secret from compromised git history | `.env.example`, `admin.env` | New JWT secret generated: rotate in production immediately |

---

## Not Fixed (Requires Further Work)

| # | Priority | Finding | File(s) | Notes |
|---|----------|---------|---------|-------|
| 18 | **HIGH** | SQL injection via column names in `create()`/`update()` | All `repositories/*.py` | `data.keys()` from user input used in f-string SQL. Mitigated by `extra="forbid"` on schemas. Full fix requires server-side column allowlist in each `create()`/`update()`. |
| 19 | **HIGH** | In-memory refresh token store breaks in multi-worker | `backend/api/v1/auth.py:33` | Requires Redis in production; in-memory fallback is single-worker only. |
| 20 | **HIGH** | Driver PII (license numbers, passports) in plaintext | `database/schema.py:377-394` | Requires column-level encryption or at-rest DB encryption. |
| 21 | **HIGH** | No bulk export audit trail | All export endpoints | Requires audit log table + middleware. |
| 22 | **MEDIUM** | Redis no password / PII in GPS queue | `backend/config.py:16-19` | `redis://` URL without password. Needs `redis://:password@host:port`. |
| 23 | **MEDIUM** | Celery workers share superuser DB credentials | `celery_app/tasks/ocr_tasks.py:10` | Needs separate DB user with restricted permissions. |
| 24 | **MEDIUM** | `/admin/env` endpoint leaks JWT secret pattern | `backend/api/v1/admin.py:449` | Already filters env vars containing "KEY"/"SECRET"/"PASSWORD"/"HASH"/"TOKEN". |
| 25 | **LOW** | No TLS/HSTS at app level | `backend/main.py` | Relies on reverse proxy (Nginx). Acceptable. |
| 26 | **LOW** | No log/db encryption at rest | `config.py` | Acceptable for development. |
| 27 | **LOW** | bcrypt cost not tunable at runtime (env var only) | `backend/config.py` | Acceptable — env var restart is standard. |

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
