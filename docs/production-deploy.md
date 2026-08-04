# Operion ERP — Production Deployment Runbook

> Grounded in the repo's actual production artifacts: `docker/docker-compose.yml`,
> `docker/init-db.sh`, `docker/Dockerfile`, `docker/Dockerfile.worker`,
> `docker/.env.production`, `.env.example`, `requirements.lock.txt`,
> `PRODUCTION_SECURITY_CHECKLIST.md`, and `backend/config.py` startup guards.
>
> Note: the audit referenced `docker/compose.prod.yaml`; the production compose
> file in this repo is `docker/docker-compose.yml` (Postgres + Redis + api +
> worker + celery-beat + backup + nginx). Follow that file.

---

## 1. Prerequisites

| Component | Version | Why |
|---|---|---|
| PostgreSQL | 15+ | `postgres:15-alpine` image; `schema_pg.sql` + Alembic |
| Redis | 7+ | `redis:7-alpine`; Celery broker/result, rate limiting, refresh tokens |
| Docker Compose | v2 | `docker compose up -d` |
| Python | 3.11 | `requirements.lock.txt` is pinned with Python 3.11 (`pip-compile`) |
| `uv` / `pip` | any | to install the lockfile contract |

Recommended host: a single Linux VM (2–4 vCPU, 4–8 GB RAM). No GUI/desktop
components are needed for the server-side deployment.

---

## 2. Environment setup

1. Copy the template and edit secrets:

   ```bash
   cp .env.example .env
   # or start from the richer template:
   cp docker/.env.production .env
   ```

   > **WARNING:** `docker/.env.production` ships with **placeholder values**
   > (`CHANGE_ME_*`) and empty fields (e.g. `OPERION_ADMIN_PASSWORD_HASH`,
   > `OPERION_SUPPORT_INTERNAL_AUTH`). It is a template only — deploying with
   > these values means the app boots with known/predictable secrets (and
   > `OPERION_SUPPORT_INTERNAL_AUTH` with an empty value is rejected by the
   > prod startup guard). Replace **every** `CHANGE_ME_*` placeholder and set
   > all required variables (see step 3) before starting the stack.

2. Generate every secret with `openssl rand -hex 32` (do **not** reuse dev
   secrets — see `PRODUCTION_SECURITY_CHECKLIST.md`):

   ```bash
   OPERION_JWT_SECRET_KEY=$(openssl rand -hex 32)
   OPERION_API_KEY=$(openssl rand -hex 32)
   OPERION_ENCRYPTION_KEY=$(openssl rand -hex 32)
   OPERION_SUPPORT_INTERNAL_AUTH=$(openssl rand -hex 32)
   OPERION_REDIS_PASSWORD=$(openssl rand -hex 32)
   OPERION_POSTGRES_PASSWORD=$(openssl rand -hex 32)
   OPERION_CELERY_PASSWORD=$(openssl rand -hex 32)
   ```

3. Required production variables and what they gate
   (each is enforced by `backend/config.py` `_check_admin_config`):

   | Variable | Purpose | Startup guard |
   |---|---|---|
   | `OPERION_ENV=production` | Disables `/docs`/`/redoc`, enables prod CORS + startup guards | `config.py` |
   | `OPERION_JWT_SECRET_KEY` | Signs/verifies JWTs; **refuses to boot in prod without it** | `config.py` raises `RuntimeError` |
   | `OPERION_API_KEY` | Transport-layer API key (`X-API-Key` header); **refuses to boot in prod without it** | `config.py` raises `RuntimeError` |
   | `OPERION_ENCRYPTION_KEY` | Fernet field-level encryption (SMTP passwords etc.); unset → plaintext fallback with a warning | `config.py` warns |
   | `OPERION_SUPPORT_INTERNAL_AUTH` | Internal auth for the operion-ops support-service proxy; the default `dev-insecure-replace-in-production` is rejected in prod | `config.py` raises `RuntimeError` |
   | `OPERION_REDIS_URL` + `OPERION_REDIS_PASSWORD` | Rate limiting, refresh-token store, caching across gunicorn workers | `config.py` pings Redis in prod |
   | `OPERION_POSTGRES_DSN` | Backend DB connection (`OPERION_DB_ENGINE=postgresql`) | — |
   | `OPERION_CELERY_PASSWORD` | Password for the restricted `operion_celery` Postgres role created by `docker/init-db.sh`; **must be set** — the init script defaults to `CHANGE_ME_CELERY_PASSWORD` if unset | `docker/init-db.sh` |

4. Never commit the resulting `.env` (currently `.env` is git-tracked — run
   `git rm --cached .env` before onboarding, per the audit blocker #1).

---

## 3. Database

The schema is fully declarative and idempotent:

1. **Initialise the schema** — `DatabaseManager` with `OPERION_DB_ENGINE=postgresql`
   executes `database/schema_pg.sql` on first boot (each statement is wrapped in
   a SAVEPOINT so a failing statement never aborts the transaction), then runs
   Alembic migrations to head. You can run the same step manually:

   ```bash
   psql "$OPERION_POSTGRES_DSN" -f database/schema_pg.sql
   alembic upgrade head   # also run automatically on first boot
   ```

2. **Restricted Celery user** — `docker/init-db.sh` (mounted as the Postgres
   container's first-time init script) creates `operion_celery` with **only**
   `SELECT / INSERT / UPDATE` on all tables + `USAGE` on sequences, and
   explicitly `REVOKE CREATE ON SCHEMA public`. The `worker` and `celery-beat`
   services connect with this restricted user — no DDL in production workers.

3. **Lockfile as the install contract** — installs are pinned by
   `requirements.lock.txt`, generated with Python 3.11:

   ```bash
   pip-compile --output-file=requirements.lock.txt requirements.api.txt
   pip install -r requirements.lock.txt
   ```

   The Docker images install `requirements.txt`; regenerate both when
   dependencies change and keep them in sync with the lockfile.

---

## 4. Build & run

Compose is production-oriented and binds DB/Redis/API to `127.0.0.1` only;
nginx terminates TLS on `80/443`. Run the commands from the **repo root** —
the compose file's build context is the repo root (`context: ..`), so a
plain `cd docker` would break the builds.

```bash
# populate docker/.env.production with the real secrets first
docker compose -f docker/docker-compose.yml up -d --build
docker compose -f docker/docker-compose.yml ps   # wait for postgres + redis to be healthy
```

**Healthcheck order** (declared in `docker-compose.yml`):
`db` and `redis` must be `service_healthy` before `api`/`worker` start
(`depends_on: condition: service_healthy`). Do not scale workers before the
DB schema is up.

**Gunicorn** (`docker/Dockerfile` CMD):
`gunicorn backend.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
--bind 0.0.0.0:8000 --access-logfile - --error-logfile -`.
Tune `--workers` to `(2 × CPU cores) + 1`. The image healthcheck curls
`/api/v1/health` (30s interval, 3 retries).

**Celery** (`docker/Dockerfile.worker`):
- Worker: `celery -A backend.celery_app.celery worker --loglevel=info --concurrency=2`
- Beat: `celery -A backend.celery_app.celery beat --loglevel=info`

Global task time limits already exist in `backend/celery_app/celery.py`
(`task_time_limit=30*60`, `task_soft_time_limit=25*60`). For graceful shutdown
add **at least** `--time-limit=1800` on the worker and give Docker/K8s time to
drain before SIGKILL:

```bash
celery -A backend.celery_app.celery worker \
  --loglevel=info --concurrency=2 \
  --time-limit=1800 --soft-time-limit=1500 \
  --max-tasks-per-child=200
```

Recommended stop policy: `--stop-wait-sec 120` (Docker Compose `stop_grace_period:
120s`) or `TERM_TIMEOUT=120` in orchestration, so in-flight document/email/OCR
tasks finish and Celery acks complete before the process is killed.

---

## 5. Migration workflow

- **Additive migrations only.** Every migration in this repo is idempotent
  (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `ON CONFLICT
  DO NOTHING` version seeds). Follow the same rule for new schema changes.
- **Backup before** applying migrations (`pg_dump` or the `backup` service —
  see §7).
- Run migrations in a maintenance window:
  `alembic upgrade head`, then verify `/api/v1/health/ready`.
- **Rollback:** `alembic downgrade -1` where the migration defines a
  `downgrade()`; Alembic migrations in `alembic/versions/` are tested for
  upgrade/downgrade/idempotency. Note the audit's finding: **only `IF EXISTS`
  drops exist**, so destructive rollbacks (table drops) are not recoverable —
  restore from backup instead.
- The schema-migration version seed table (`schema_migrations`, versions 1–8)
  is the SQLite-side record; PostgreSQL seeds the same table via
  `schema_pg.sql` and Alembic tracks its own `alembic_version`.

---

## 6. Smoke test checklist

Run after every deploy/rollback:

| # | Check | Command |
|---|---|---|
| 1 | Liveness | `curl -f http://127.0.0.1:8000/api/v1/health/live` |
| 2 | Readiness (DB+Redis+Celery) | `curl -f http://127.0.0.1:8000/api/v1/health/ready` |
| 3 | Combined health | `curl -f http://127.0.0.1:8000/api/v1/health` |
| 4 | One login (transport key + JWT) | `curl -X POST http://127.0.0.1:8000/api/v1/auth/token -d 'username=...&password=...'` with `X-API-Key` |
| 5 | One invoice PDF | `GET /api/v1/invoices/generate` (or `/api/v1/trips/{id}/export/pdf`) returns `application/pdf` |
| 6 | One tacho import | upload a `.ddd`/`.tgd` via the tacho import endpoint or UI |

Anything 5xx on 1–3 means the container is not ready; re-check `docker compose
logs` for the failing component. Item 5 also exercises the export/PDF path from
roadmap item 11.

---

## 7. Backup / restore, logs, monitoring

**Backup** — the `backup` compose service runs `scripts/backup.sh` daily at
03:00 via cron inside the container: `pg_dump` to `/backups`
(`OPERION_BACKUP_DIR`), retaining 30 days (`OPERION_BACKUP_RETENTION_DAYS`),
volume-mounted to `db_backups`. Uncomment the R2/S3 variables in
`docker-compose.yml` to ship dumps off-host. **Test a restore monthly**
(`PRODUCTION_SECURITY_CHECKLIST.md`).

```bash
# Manual restore
pg_restore --clean --if-exists -d "$OPERION_POSTGRES_DSN" /backups/<dump-file>
```

**Log rotation** — Docker json-file driver is configured globally in
`docker-compose.yml` (`max-size: 10m`, `max-file: 3`). Application logs are
written to the `app_logs` volume; the desktop logger (`utils/logger.py`) uses
`RotatingFileHandler` (10 MB × 5 backups).

**Monitoring** — `/api/v1/health/live` + `/api/v1/health/ready` for probes;
`/api/v1/health` for DB pool details. Prometheus metrics are exported via
`prometheus-client` (`backend/metrics.py`, in `requirements.lock.txt`) — scrape
the API port and alert on error/5xx rates.

---

## 8. Known operational notes (from the production-readiness audit)

1. **Celery task retries** — `build_email_package` and `generate_document_pdf`
   use `max_retries=2, default_retry_delay=30`. Emails are now double-send
   protected by the `sent_emails` dedup table
   (`UNIQUE(document_id, recipient)`); a retried task claims a `pending` row
   first and skips if a send is already in flight. Monitor `email_deduplicated`
   result keys and the Celery failure queue.
2. **GPS flush is per-company** — `flush_gps_batch_to_postgres` drains the
   tenant-scoped `gps:batch:{company_id}` queues; `GpsTelemetryRepository
   .create_many` uses `INSERT OR IGNORE` against the unique
   `(truck_id, recorded_at)` index, so replayed batches are idempotent. Do not
   switch it back to a global queue.
3. **Secret-leak procedure** — if any secret is suspected of leaking:
   - Find history with: `git log -S OPERION_JWT_SECRET_KEY --oneline --all` (and
     the same for `OPERION_API_KEY`, `OPERION_ENCRYPTION_KEY`, prefs tokens).
   - Rotate **all** secrets with `openssl rand -hex 32`, redeploy, and rotate
     any downstream tokens (freight-exchange provider credentials, SMTP
     passwords) stored encrypted in the DB.
   - Remove leaked files from git tracking (`git rm --cached .env
     data/prefs.json`) and scrub history before onboarding (audit blocker #1).
4. **Startup guards are fail-closed in prod** — the API will refuse to boot
   without `OPERION_JWT_SECRET_KEY`, `OPERION_API_KEY`, or a real
   `OPERION_SUPPORT_INTERNAL_AUTH`. Do not bypass; set them first.

---

## Reference

- `PRODUCTION_SECURITY_CHECKLIST.md` — pre-cut-over checklist
- `docs/staging-runbook.md` — local staging harness (SQLite, no Docker)
- `.env.example` / `docker/.env.production` — env templates
- `backend/config.py` — startup guards and their exact messages
