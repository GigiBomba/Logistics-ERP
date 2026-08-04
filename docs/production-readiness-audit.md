# Operion Desktop ERP — Production Readiness Audit

**Date:** 2026-08-01
**Scope:** PySide6 desktop client + FastAPI/PostgreSQL/Redis/Celery backend
**Method:** 13 parallel evidence lanes (source-verified, file:line references), plus a real bounded coverage measurement (coverage.py 7.15.2).
**Status:** Initial audit. Blockers tracked in `.slim/deepwork/production-readiness-fixes.md`; remediation in progress.

---

## 1. Executive verdict

**NOT production-ready for a real paying customer — conditionally fixable, but not today.**

The single biggest reason: **live production secrets are committed to the repository** (JWT signing key, API key, Fernet encryption key in `.env`; working Gemini/Qwen API keys in `data/prefs.json`), and alongside them sit a **constructible cross-tenant disclosure** (any authenticated user can read any other company's live truck GPS) and **partner API credentials stored in plaintext**. Any one of these is a release blocker on its own; together they mean the system cannot be trusted with a paying customer's fleet data until a concrete remediation pass is done.

The good news: the core data layer, auth primitives, and test infrastructure are genuinely strong — the blockers are concentrated in specific, well-bounded files.

## 2. Critical blockers

1. **Committed live secrets** — `.env:22,32,38` contain `OPERION_JWT_SECRET_KEY`, `OPERION_API_KEY`, `OPERION_ENCRYPTION_KEY` (real 64-char hex/base64 values); `data/prefs.json:27,34` contains working `gemini_api_key`/`qwen_api_key`. Anyone with repo access can forge JWTs (full API access as any user), decrypt Fernet-protected data, and burn/exfiltrate through paid AI APIs. *Failure:* total account compromise from a repo leak.

2. **GPS endpoints without truck-ownership verification** — `backend/api/v1/fleet.py:102,114,134,147` (`POST /fleet/gps/ingest`, `GET /fleet/gps/live/{truck_id}`, `POST /fleet/gps/batch`, `GET /fleet/gps/history/{truck_id}`): `get_live_position` does `cache.get(f"gps:live:{truck_id}")` with no company check. Truck IDs are sequential ints. *Failure:* Company A reads Company B's real-time vehicle coordinates (privacy/competitive breach) and injects fake pings (corrupts B's tracking).

3. **Tracking provider credentials plaintext at rest** — `services/preferences.py:80`: `_SENSITIVE_KEYS = {"smtp_password"}` only; Wialon/Frotcom/Traccar/Navixy tokens+passwords read raw from the settings table (`fleet_tracking_service.py:508-521`). *Failure:* DB leak = usable partner API credentials; contrasts with freight-exchange tokens which are encrypted.

4. **GPS flush task: silent permanent data loss + untenant-scoped queue** — `ocr_tasks.py:99-133`: `flush_gps_batch_to_postgres` has **no `max_retries`**, does `lpop` from a **global** `gps:batch_queue` (`fleet.py:110`) before inserting; a crash between lpop and commit loses pings forever, and concurrent companies race the same list. `GpsTelemetryRepository.create_many` (`gps_telemetry_repository.py:48-58`) never injects `company_id` → orphan/NULL-scope records.

5. **Background maintenance deletes ALL companies' data** — `maintenance_tasks.py:25`: `cleanup_expired_data` calls `delete_older_than(cutoff)` with no company scoping; same pattern in `copilot_repository.py:61-65,114-118,149-153,180-183` and `trans_eu_repository.py:123-126,166-169`. *Failure:* one scheduled task wipes every tenant's GPS/copilot history.

6. **Insight jobs: silent failure + duplicate writes + cross-tenant reads** — `insight_tasks.py:70-71,128-129,154-155,219-220`: `except Exception: continue` swallows all per-row failures; `copilot_insights` has no uniqueness constraint (`copilot_repository.py:136-138`), so retry after partial progress duplicates insights. `overdue_invoice_job` (`:87-90`) and `return_load_matcher_job` (`:171-175`) run raw SQL reading **all companies'** invoices/trips.

7. **Production ships a known insecure internal-auth default** — `backend/config.py:56` and `docker/.env.production`: `support_internal_auth = "dev-insecure-replace-in-production"`. *Failure:* any deployment that skips env setup has a well-known auth bypass string.

8. **Known-CVE dependency exposure + no reproducible builds** — `fastapi>=0.109.0,<0.200.0` pulls starlette <0.40 → **CVE-2024-47874** (multipart/form-data OOM DoS, CVSS 8.7) on every upload-capable endpoint; httpx transitive h11/httpcore need explicit pins (`CVE-2025-43859`). No lockfile exists for Python at all (`>=` pins everywhere) — deployments are not reproducible.

## 3. Findings table

| Category | Severity | Description | Evidence | One-line fix |
|---|---|---|---|---|
| Security | **Critical** | Committed secrets (.env, prefs.json) | `.env:22,32,38`; `data/prefs.json:27,34` | Rotate all secrets; `git rm --cached` + scrub history; env-only config |
| Tenant isolation | **Critical** | GPS live/history/ingest lack truck-ownership check | `fleet.py:102,114,134,147` | Verify `truck` belongs to JWT `company_id` before read/write |
| Security | **Critical** | Tracking credentials plaintext | `preferences.py:80`; `fleet_tracking_service.py:508-521` | Add to `_SENSITIVE_KEYS`, encrypt at rest via `encryption_service` |
| Celery | **Critical** | GPS flush: no retry, lpop-before-commit, global queue | `ocr_tasks.py:99-133`; `fleet.py:110` | `max_retries=3` + per-company queue key + unique `(truck_id, recorded_at)` |
| Tenant isolation | **Critical** | Cleanup/retention tasks delete all tenants | `maintenance_tasks.py:25`; `copilot_repository.py:61-65` et al. | Loop per-company or add `_company_filter` |
| Celery | **High** | Insight jobs: silent `continue`, duplicate inserts, cross-tenant reads | `insight_tasks.py:70-71,87-90,171-175`; `copilot_repository.py:136-138` | `UNIQUE(company_id, insight_type, payload)` + `INSERT OR IGNORE`; log per-row failures |
| Security | **High** | Refresh-token rotation not atomic (concurrent refresh race) | `auth.py:118-126` (self-documented gap) | Atomic check-and-delete via Lua/transaction |
| Security | **High** | `body: dict` endpoints without schema validation | `api_keys.py:36`; `mobile.py:216,1222` | Typed Pydantic schemas with `extra="forbid"` |
| Celery | **High** | `build_email_package` can double-send on retry | `document_tasks.py:115-119` | `sent_emails` dedup table `UNIQUE(document_id, recipient)` |
| Reliability | **High** | Idempotency middleware cross-process race (documented) | `idempotency_middleware.py:200-207` | Atomic `SET NX GET` / Lua script |
| PDF | **High** | Invoice generators crash on `None` numeric fields | `generator.py:120-126,408,413-416` | `float(x or 0)` guards |
| PDF | **Medium** | Fixed filenames → concurrent overwrite; client_name in contract filename → path traversal | `generator.py:45,217`; `template_service.py:72` | `tempfile.mkstemp`+`os.replace`; sanitize filename |
| PDF | **Low** | Document cache key is company-blind | `document_service.py:566-574` | Key = `doc:{company_id}:{doc_id}` |
| Analytics | **Medium** | Fleet "Avg Cost/km" uses fuel cost only (formula gap) | `fleet_tab.py:78` | Include tolls+salary+extras in total |
| Analytics | **Low** | Utilization = raw trip count, no km weighting; OTD not implemented | `analytics_repository.py:440-450`; schema lacks `promised_date` | Weight by km; add `promised_date` column |
| Analytics | Info (corrected) | "Inverted profit colors" — **false positive**; `route_profit_km` is `SUCCESS if avg>=0` (verified `overview_view.py:620`); `client_delay` at :599 correct | `overview_view.py:599,620` | None |
| i18n | **High** | ~33 hardcoded user-facing strings bypassing `t()` (worst: connect_view.py ×9) | `connect_view.py:59-215`; `freight_provider_settings.py:463`; `maintenance_view.py:496` | Wrap in `t()`; expand `test_no_hardcoded_strings` beyond QLabel |
| i18n | Info | Key parity perfect (2,857=2,857); 234 keys untranslated (RO==EN); graceful fallback | `services/i18n.py:113-147` | Batch-translate 234 keys |
| Tachograph | Info | No command injection (list args, no shell); 30s timeout; graceful missing-binary message; UI non-blocking | `tacho_service.py:620-631,662-668`; `tacho_import_view.py:513-523` | Solid; add version probe |
| Tachograph | **Medium** | Partial records on corrupt file (per-row commits; orphan import row) | `tacho_service.py:877-941,1069-1078` | Wrap import in one transaction |
| Error handling | **High** | No desktop global excepthook — runtime exceptions crash silently | `main.py:307` (startup-only); 0 `sys.excepthook` hits | Install `sys.excepthook` + `qInstallMessageHandler` |
| Error handling | **High** | ~100+ silent `except Exception` in services/; dispatch events swallowed at `logger.debug` | `dispatch_service.py:135,194,260,429,634-666`; `app_state.py:46,67` | Log at warning + retry/alert |
| Observability | **Medium** | No correlation ID to Celery tasks; non-JSON logs | `logging_middleware.py:19-26`; tasks lack request_id | Pass `request_id` into task kwargs; JSON formatter |
| Performance | **Critical** | Dashboard sync-loads all trips on main thread every 30s | `dashboard.py:149,237-251` | `WorkerPool.run` like `overview_view.py:430` |
| Performance | **High** | Dispatch board N+1 (1 + N×2 per card, unbounded trip load); conflict scan on main thread | `board_state.py:158,166,343,477` | LIMIT + batch resolve; move scan to worker |
| Performance | **Medium** | Driver manager N+1 (`get_truck_plate_for_driver` per row) | `driver_manager.py:676` | Single batch query |
| Performance | **Medium** | `LENGTH(start_date) >= 10` non-sargable anti-pattern ×4 | `trip_repository.py:243,268,432,457` | Enforce date format at INSERT; drop LENGTH guard |
| Performance | Info | `company_id` indexed on all business tables; composite `(company_id, status)` exists | `schema_pg.sql:88-92,1202-1203` | Solid |
| Testing | **High** | `fail_under=60` too low; export_service TypeError masked by skips | `pyproject.toml:122`; `test_workflow_integration.py:301-315` | Fix export bug, re-enable, raise to 80 |
| Testing | **Medium** | Zero tests for fleet-tracking adapters; PDF tested mock-only; "18 bugs" not enumerated in test_audit_fixes.py | gap; `test_celery_tasks.py:295-307`; `test_audit_fixes.py` | Adapter integration tests; functional PDF test; bug registry |
| Testing | Info | **Real measurement (bounded): 13%** aggregate over services/repositories/client/backend from 9 representative test files (tacho/trans_eu 0% in this set); full suite ≈3,000+ tests across 850 files | coverage 7.15.2 run | Full-suite measurement before onboarding |
| Deployment | **Critical** | `docker/.env.*` git-tracked; prod file carries dev values | `git ls-files docker/.env.*`; `.env.production:68` | `git rm --cached`; real secrets via vault |
| Deployment | **High** | Hardcoded personal OneDrive logo path; prod API URL not UI-configurable; localhost Redis defaults ship if env unset | `company_config.json:8`; `client/config.py:22`; `backend/config.py:19-23` | Env-resolve paths; settings field; fail-closed in prod |
| Deployment | **High** | No production deploy runbook (no migrations step, no Celery graceful shutdown) | README (dev only); `compose.prod.yaml:65` | Write `docs/production-deploy.md`; `--stop-wait-sec` |
| Deployment | **Medium** | Desktop log file never rotates | `utils/logger.py:30-31` | `RotatingFileHandler` |
| Security | Info | JWT pinned HS256; bcrypt(12); login lockout; HttpOnly SameSite=Strict cookie; `extra="forbid"` on core schemas; HMAC API keys | `security.py:13-60,115`; `auth.py:75-156,250-260` | Solid |
| Dependencies | **High** | CVE-2024-47874 (starlette multipart DoS); h11/httpcore transitive | `requirements*.txt`; `pyproject.toml` | Pin `fastapi>=0.115` / `starlette>=0.40` / `httpcore>=1.0.9` / `h11>=0.16`; add lockfile |
| Dependencies | Info | reportlab ≥4.4.10 (patched for RCE CVE-2023-33733); celery, PyJWT, pydantic, Jinja2 all above fixed versions | manifests | Monitor passlib (unmaintained, bcrypt-5 incompatible) |

## 4. What's actually solid (don't re-audit)

- **Repository-layer tenant isolation** — all ~25 tenant-scoped repositories apply `_company_filter`/`_company_filter_for`/`_set_company_from_context` on every method; company_id is JWT-derived server-side, never client-supplied; admin/debug endpoints all gated by `require_admin`.
- **Auth primitives** — pinned HS256 (no alg confusion), bcrypt rounds 12, Redis-backed login lockout (5 fails/300s window/900s lock), HttpOnly+SameSite=Strict refresh cookie, constant-time API-key comparison.
- **Data integrity** — `PRAGMA foreign_keys=ON` per SQLite connection; declarative PG FKs; alembic migrations tested for upgrade/downgrade/idempotency; only DROP is `IF EXISTS`; **invoice numbering is race-free** (`BEGIN IMMEDIATE` + `UNIQUE invoice_number`).
- **PDF partially** — CMR + Receipt generators use atomic `mkstemp`+`os.replace`; CMR null guards; invoice `validate_complete()` pre-checks.
- **i18n structure** — exact en/ro key parity (2,857/2,857), graceful 4-level fallback, live locale reload.
- **Tachograph** — subprocess is injection-safe (list args, no shell, 30s timeout), hash-based dedup, graceful missing-binary UX, daemon-thread UI.
- **Performance base** — `company_id` indexed on every business table; `overview_view`/`history_view` are the reference WorkerPool pattern; client-side freeze detector exists.
- **Operations** — health triad (live/ready/full) with DB+Redis+Celery checks; production startup guards (refuse to boot without JWT secret/API key in prod); prod CORS + Swagger disabled; least-privilege Celery DB role; Docker log rotation.
- **Test infra** — 850 test files / ~3,000+ tests; real SQLite InMemoryDB with FK seeding; real FastAPI TestClient; file-based concurrency suite; 19 chaos files; comprehensive invoice/dispatch/trip/remote-service coverage; HMAC webhook verification; trans.eu tokens encrypted at rest.

## 5. Prioritized remediation roadmap

**Before onboarding the first real customer (blockers):**
1. Rotate and remove all committed secrets (`.env`, `data/prefs.json` keys); `git rm --cached` + history scrub; move to env/vault
2. Add truck-ownership verification to all four GPS endpoints (`fleet.py`)
3. Encrypt tracking credentials (`_SENSITIVE_KEYS` + `encryption_service`); re-encrypt existing values
4. GPS flush task: `max_retries`, per-company queue key, unique constraint, `company_id` injection in `create_many`
5. Scope all cleanup/retention tasks per company (maintenance, copilot, trans_eu)
6. Insight jobs: uniqueness constraint + `INSERT OR IGNORE`, per-row failure logging, company-scope the two raw-SQL jobs
7. Replace `support_internal_auth` dev default with required env + fail-closed in prod
8. Pin `fastapi>=0.115`/`starlette>=0.40` + `httpcore`/`h11`; introduce a lockfile; run full-suite coverage to a verified baseline
9. Move dashboard + dispatch-board conflict scan off the main thread (WorkerPool); fix invoice PDF `None` crashes + atomic writes

**Before/early after onboarding (high):**
10. Desktop global excepthook + user-visible error dialog; upgrade ~10 silent dispatch-service swallows to warnings
11. Fix `export_service.py` NoneType bug, re-enable skipped tests, raise `fail_under` to 80
12. Email-send dedup table; idempotency Lua fix; OCR status/error field in API
13. Wire the existing (currently dead) `FreightRateLimiter` + `FreightCircuitBreaker`; add backoff/jitter to tracking polls; log non-200 statuses
14. i18n: wrap ~33 hardcoded strings; expand the no-hardcoded-strings test; translate 234 keys
15. Batch driver-manager plate lookup; LIMIT the board trip load; drop `LENGTH(start_date)` guards
16. Write `docs/production-deploy.md` (env, migrations, Celery shutdown, smoke test); rotate desktop log file

**Can wait (post-onboarding):**
17. Correlation IDs into Celery + JSON logging; OTD metric (schema change); per-tenant Chrome profile dirs; composite `(company_id, start_date)` indexes; version probe for tachograph binary; contract-PATCH `exclude_unset` (already partially done)

**Coverage note (measured, bounded):** a real run of 9 representative test files over `services/repositories/client/backend` yields **13% aggregate** (tacho/trans_eu at 0% in that set); the configured `fail_under=60` applies to the full ~3,000-test suite and was not verified end-to-end — that full measurement should be the first step of roadmap item 8.
