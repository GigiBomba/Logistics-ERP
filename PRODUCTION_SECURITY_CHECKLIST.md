# Production Security Checklist

> Use this checklist during every production cut-over or major release.
> Mark items `[x]` once verified.

## Environment & Secrets

- [ ] **Secrets rotated and outside git** — Generate fresh `OPERION_JWT_SECRET_KEY`, `OPERION_API_KEY`, and `OPERION_REDIS_PASSWORD` for production using `openssl rand -hex 32`. Never reuse dev secrets.
- [ ] **OPERION_ENV=production** — Enables all startup guards, production CORS, disables Swagger docs.
- [ ] **OPERION_JWT_SECRET_KEY set** — Application refuses to start in production without it.
- [ ] **OPERION_API_KEY set** — Application refuses to start in production without it. Every client must send `X-API-Key` header.
- [ ] **OPERION_REDIS_URL configured** — Required for distributed rate limiting + refresh token store across gunicorn workers.
- [ ] **OPERION_REDIS_PASSWORD set** — Redis must be password-protected, not publicly accessible.
- [ ] **OPERION_AUDIT_LOG_DIR configured** — For financial export audit trails (payment CSV exports).
- [ ] **VITE_API_KEY set in frontend** — Must match `OPERION_API_KEY`. The web frontend sends it as `X-API-Key` on all requests.

## Infrastructure

- [ ] **TLS/HTTPS at reverse proxy** — Nginx config already includes TLS 1.2/1.3, HSTS, and security headers.
- [ ] **CORS origins production-only** — Defaults to `https://operionerp.xyz,https://app.operionerp.xyz,https://api.operionerp.xyz`. Override via `OPERION_CORS_ORIGINS` if needed.
- [ ] **Redis not public** — Bind to `127.0.0.1` or use a private VPC network. Password must be set.
- [ ] **Celery workers use restricted DB user** — Create a PostgreSQL user with only the permissions Celery needs (read/write on specific tables, no DDL).
- [ ] **Database backups with tested restore** — Automated daily backups, tested restore at least monthly.

## Code & Dependencies

- [ ] **Full security test suite green** — Run `pytest tests/` before deploying.
- [ ] **pip-audit clean** — Run `pip-audit` to check for dependency CVEs.
- [ ] **Rate limiting thresholds reviewed** — Currently 100 req/60s per IP (app-level) + nginx 30r/s burst 50. Adjust based on expected traffic.

## Data Protection

- [ ] **DB volume/filesystem encryption** — Enable LUKS (Linux), BitLocker (Windows), or cloud KMS for the database volume. Protects driver PII (bank accounts, IBANs) at rest.
- [ ] **Data retention/GDPR for driver PII** — Document retention periods and implement cleanup jobs for old driver data.
- [ ] **Company_id migration complete** — All business tables must include `company_id` for multi-tenant isolation. Verified by the existing audit.
