# Operion ERP — Local Staging Harness Runbook

A local stand-in for a deployed staging environment: real backend process,
isolated SQLite DB, seeded test users, and an end-to-end smoke that exercises
the exact mobile-facing contract chain. No Docker required (default path is
plain uvicorn).

## 1. Start the staging backend

```bat
scripts\start_staging.bat
```

- Copies nothing automatically — the script sets the staging env inline and
  seeds `data/staging.db` (idempotent) on every start.
- Alternative config: copy `.env.staging.example` → `.env.staging` and edit;
  the launcher loads it (values below override anything unset). **If a stale
  `.env.staging` exists (e.g. from an older harness attempt), regenerate it
  from `.env.staging.example`** — a stale file may reference different test
  users/seed scripts and silently diverge from the smoke test's expectations.
- Docker alternative: `scripts\start_staging.bat -Docker` (uses
  `compose.local.yaml`). Note: the compose path does NOT run the seed step —
  seed first with the plain launcher once, or run
  `python scripts\seed_staging_users.py` manually.
- Server: http://127.0.0.1:8010 (staging port; default 8000 untouched).

## 2. Seeded test users

| User | Role | Password |
|---|---|---|
| `driver@staging.local` | driver | `staging-pass` |
| `dispatcher@staging.local` | dispatcher | `staging-pass` |

Seeding is idempotent (`scripts/seed_staging_users.py`); it creates
`data/staging.db` with the full schema via `DatabaseManager`.

## 3. Run the smoke

```bat
pytest tests\staging\test_staging_smoke.py -v
```

The smoke auto-detects the path: live server if reachable, otherwise an
in-process `create_app()` fallback (seeding first). It reports which path ran.

Chain covered (each asserting the contract shape):

1. `POST /api/v1/auth/token` (driver) → JWT
2. `GET /api/v1/mobile/driver/trip-overview` → 200, 8 contract keys (all-null when no trip)
3. `GET /api/v1/mobile/driver/route-share` → clean 404 (no transport) or RouteShareResponse shape
4. `POST /api/v1/auth/token` (dispatcher) → JWT
5. `POST /api/v1/mobile/company/export/manifest` → entry list with signed-URL fields
6. `POST /api/v1/ocr/process` (multipart + `Idempotency-Key`) → 201 queued/processing, key echoed
7. `POST /api/v1/copilot/chat` → timeline or clarification shape

The staging tests are marker-gated (`@pytest.mark.staging`) and never run in
the default suite.

## 4. Point the mobile app at staging

- Base URL: `http://127.0.0.1:8010` (Flutter web dev / Android emulator uses
  `10.0.2.2:8010` — adjust `OPERION_API_BASE_URL` + CORS accordingly).
- CORS for dev origins is preset (`localhost:5173`, `127.0.0.1:5173`,
  `localhost:3000`); extend `OPERION_CORS_ORIGINS` for anything else.
- Mobile dev build needs the staging JWT flow only — the app's normal login
  screen works against the seeded users.

## 5. What a real deployed staging environment additionally needs

Out of scope for this harness (documented, not built):

- Managed PostgreSQL (`OPERION_DB_ENGINE=postgresql` + DSN) instead of the
  local SQLite file.
- Redis (`OPERION_REDIS_URL`) + Celery workers for the async OCR/processing
  pipelines (the local harness accepts the degraded in-process paths).
- Real secrets: `OPERION_JWT_SECRET_KEY` (openssl rand -hex 32), transport
  `OPERION_API_KEY`, field-level `OPERION_ENCRYPTION_KEY`, admin gateway hash.
- A staging domain + TLS + the support-service proxy
  (`OPERION_SUPPORT_SERVICE_URL`) if integration with operon-ops is wanted.
- Real AI provider keys (`OPERION_GEMINI_API_KEY` / `OPERION_QWEN_API_KEY`)
  for LLM-backed copilot replies (the smoke only asserts the planner shape).
