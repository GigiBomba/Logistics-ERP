# Production Security Checklist

> Use this checklist during every production cut-over or major release.
> Mark items `[x]` once verified.

- [ ] Secrets rotated and outside git
- [ ] OPERION_ENV=production
- [ ] TLS/HTTPS at reverse proxy, HSTS header
- [ ] Redis password-protected, not public
- [ ] Celery workers use restricted DB user
- [ ] Database backups with tested restore
- [ ] Rate limiting thresholds reviewed
- [ ] CORS origins list production-only
- [ ] Full security test suite green
- [ ] pip-audit clean
- [ ] Data retention/GDPR for driver PII
- [ ] Company_id migration complete
