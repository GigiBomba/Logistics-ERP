# Operion — Production Readiness Audit

Status: **2026-08-06** · Scope: frontend (`operion-website` @ `e7202f3`, 3 unpushed commits) + backend (`Calculator logistica` @ `ddabfe1`, 8 unpushed commits) + deployment/ops. Method: two read-only audit lanes + live endpoint probes + oracle synthesis gate.

## Verdict

**NO — not production ready.** No deployment of the site is reachable anywhere (`operionerp.xyz` does not serve; `operion-website.pages.dev` returns HTTP 522), and the deployment pipeline is not configured. Nothing below requires a redesign — it is configuration, wiring, and small bounded fixes.

> **Post-audit correction (2026-08-06):** the production domain is **https://operionerp.xyz**, not operion.com (which does not exist). The backend CORS allowlist already includes operionerp.xyz, so the original B1 blocker is **resolved for the main site** (only `*.pages.dev` previews remain blocked). Same-day repo fixes shipped: full site rebrand to operionerp.xyz (~100 files: canonicals, structured data, sitemap, robots, OG footer, search guard, breadcrumbs, mockups, emails) + Docker HEALTHCHECK fix. One BLOCKER remains: B3 (no successful deployment + unverified GitHub secrets).
>
> **Build/deploy discoveries (same day):** (1) the real deploy root is **`dist/client`** (vike's output) — deploy.yml said `dist`, which has no `index.html` (the old root files were pre-vike leftovers); fixed. (2) The app CSS was **never in vike's build graph** (imported only in the legacy `src/main.tsx` SPA entry) — a clean build shipped no stylesheet; fixed by importing `@/styles/globals.css` in `pages/+Page.tsx`; vike now emits and auto-links it in all prerendered pages (the earlier `inject-prerender-stylesheet.ts` fix rode on a stale artifact and was removed). (3) Self-hosted webfonts were never linked — `headHtmlBegin` in `pages/+config.ts` now injects `/fonts/fonts.css`. (4) The `tsc -b` build gate was broken by a wrong cast in `src/__tests__/unit/i18n/locale-properties.test.ts` (pre-existing; never caught because CI never ran) — fixed.

---

## 🔴 BLOCKERS (must fix before any launch)

| # | Issue | Evidence | Fix |
|---|---|---|---|
| B1 | **CORS for main site: RESOLVED** — operionerp.xyz is already in the backend allowlist (`backend/main.py:48-65`). Remaining: `*.operion-website.pages.dev` previews are blocked — add the wildcard when preview API testing is wanted (non-blocking) | | |
| B2 | ~~Docker HEALTHCHECK always fails~~ — **FIXED 2026-08-06**: `docker/Dockerfile` and `compose.prod.yaml` now probe the open `/api/v1/health/live` | | |
| B3 | **No successful Pages deployment exists** — pages.dev returns 522 (project exists, no working deployment); GitHub secrets/variable (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_PROJECT`) unverified/not configured | live probe; docs/DEPLOYMENT.md §2 vs deploy.yml header (stale) | Configure GitHub secrets/variables → push → deploy. **External action** |

## 🟡 REQUIRED (defensible launch requires these)

| # | Issue | Evidence | Fix |
|---|---|---|---|
| R1 | **Password reset never sends email** — token stored in-memory, no provider call; UI claims "reset link sent" | `backend/api/v1/auth.py:643-659` | Wire existing ResendProvider; move tokens to Redis/DB. **Repo change** |
| R2 | **Preview URLs CORS-blocked** — PR previews (`<hash>.operion-website.pages.dev`) fail API calls | same allowlist as B1 | Include `*.operion-website.pages.dev` (folded into B1) |
| R3 | **Two conflicting prod compose files** — `docker/docker-compose.yml` (gunicorn+nginx+backup+Celery) vs `compose.prod.yaml` (uvicorn, no nginx); env naming mismatch (`OPERION_ENV` vs `OPERION_ENVIRONMENT`); which one runs live unverified | both files | Pick one canonical (recommend `docker/docker-compose.yml`), deprecate the other, normalize env names. **Repo change** |
| R4 | **API base URL hardcoded fallback to prod** — preview/staging builds silently call prod API if `VITE_API_URL` unset | `src/config/site.ts:21` | Set `VITE_API_URL` per deployment env (Pages env var). **Config** |
| R5 | **Per-endpoint rate limiters in-memory only** — contact/register/waitlist limits not shared across gunicorn workers (4× bypass) | `backend/api/v1/contact.py:27`, `registration.py:25`, `waitlist.py:47` | Move to Redis (login lockout + global limiter already Redis-backed). **Repo change** |
| R6 | **Stripe unconfigured → billing nonfunctional** — checkout/portal return MOCK URLs, webhook 501 (fail-closed ✓), `addon_price_mappings` empty | `subscriptions.py:832-838,932-937,997-1003`; `webhooks_stripe.py:333-342` | Set `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`; seed real Price IDs. **External + SQL** |
| R7 | **`OPERION_API_KEY` startup crash risk** — compose uses `${OPERION_API_KEY:-}` (empty default) but production raises RuntimeError if unset | `backend/config.py:146-150`, `compose.prod.yaml:49` | Ensure key set in live env. **External** |
| R8 | **Turnstile pass-through by default** — no bot protection on public forms unless `REQUIRE_TURNSTILE=1` and keys set | `backend/utils/turnstile.py:52-60` | Set `TURNSTILE_SECRET_KEY` + `VITE_TURNSTILE_SITE_KEY`; enable require-mode post-launch. **External** |
| R9 | **No `/version` endpoint, no graceful shutdown** — ops can't verify deployed version; in-flight requests dropped on restart | `backend/main.py:42` | Add version endpoint + SIGTERM drain (post-launch acceptable). **Repo change** |

## 🔵 DEFERRABLE

| # | Issue | Note |
|---|---|---|
| D1 | ~~`SITE_BASE_URL` hardcoded `https://operion.com`~~ — **FIXED 2026-08-06**: site rebranded to `https://operionerp.xyz` across 100+ files (canonicals, structured data, sitemap, robots, OG footer, breadcrumbs, search guard, mockups, contact emails) | | |
| D2 | Blog sitemap/OG 18-slug seed fallback (`BLOG_API_TOKEN` unset) | Dynamic posts missing from sitemap/OG until token set at build |
| D3 | 1.4 MB `index-*.js` chunk (Vite chunk-size warning) | Code-split further; routes already lazy |
| D4 | R2 off-site backups commented out (`docker/docker-compose.yml`) | Only local volume backups exist |
| D5 | nginx TLS cert paths are placeholders | OK if Cloudflare edge terminates TLS |
| D6 | oxlint scans sibling `Calculator logistica/` locally (no include/exclude in `.oxlintrc.json`) | CI unaffected (fresh checkout); 1-line exclude fixes local DX |
| D7 | Stale docs: deploy.yml header + DEPLOYMENT.md §7 claim "no Pages project exists" (project exists per §2 + 522 probe) | Update comments/checklist |
| D8 | `/health` admin-gated; `/health/live` is the liveness probe (orchestration should use `/live`) | Docs/ops note |

## ℹ️ Confirmed healthy (no action)

- `public/_headers` security set complete (CSP/GTM/Turnstile/GA sources, HSTS preload, XFO DENY, nosniff, COOP/CORP, Permissions-Policy) — matches DEPLOYMENT.md §5
- API docs disabled in production (live probe ✓); secure cookies; MFA+CSRF active under `OPERION_ENV=production`; JWT 15 min + opaque refresh in Redis
- Uploads: magic-byte validation, filename sanitization, EXIF strip, nginx 50 MB cap
- Frontend: root ErrorBoundary, 404 noindex, error pages outside MaintenanceGuard, PageSuspense, consent-gated analytics (GCMv2), i18n audit PASS (all 6 locales), nav↔routes parity
- CI: quality + tests + visual soft-gate + nightly Stryker issue tracking; 7 k6 load scripts available
- All code-fixable residuals closed (docs/OPERION_KNOWN_ISSUES.md §8); e2e 198/198 green; vitest 1695/1695; axe suites green

## Adjudicated contradictions

1. "dist/ empty" (exp-1) → **false** — verified 10 root files + dist/assets + dist/client (37 prerendered pages)
2. "KNOWN_ISSUES doc missing" (exp-2) → **false** — exists at `docs/OPERION_KNOWN_ISSUES.md`
3. Pages project status → **exists** (DEPLOYMENT.md §2, 2026-08-01, matches 522 probe); deploy.yml header + DEPLOYMENT.md §7 are stale
4. "18 skipped tests" vs 10 `@pytest.mark.skip` markers → **no contradiction** — runtime skips include dynamic `pytest.skip()` calls
5. Lint BLOCKER → **downgraded to DEFERRABLE** — CI checkout has no sibling dir; `src/` itself lints clean

## Launch checklist

**Phase 0 — repo fixes (0.1–0.10 above), commit, push** (`git push origin main` both repos; frontend 3 + backend 8 unpushed commits today)
**Phase 1 — GitHub**: secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`; variable `CLOUDFLARE_PAGES_PROJECT=operion-website`; `VITE_API_URL=https://api.operionerp.xyz`
**Phase 2 — Cloudflare**: confirm Pages project (branch `main`, build `npm run build`, output `dist`); attach `operionerp.xyz` as custom domain (zone already in account — hosts api.operionerp.xyz); determine why pages.dev returns 522 before first deploy
**Phase 3 — DNS**: CNAME `operionerp.xyz` (+ `www.operionerp.xyz` if used) → `operion-website.pages.dev`
**Phase 4 — backend env**: `OPERION_CORS_ORIGINS` (+operion.com/pages.dev), `STRIPE_SECRET_KEY`/`WEBHOOK_SECRET`, seed `addon_price_mappings`, `TURNSTILE_SECRET_KEY`, `OPERION_API_KEY`, `RESEND_API_KEY`, `BLOG_API_TOKEN`; redeploy with fixed HEALTHCHECK
**Phase 5 — deploy & verify**: push → CI green → pages.dev 200 → operion.com 200 → DEPLOYMENT.md §8 checklist (headers, SPA fallback, preview URL) → smoke: login, dashboard, checkout, password reset, contact email
**Phase 6 — post-launch (week 1)**: k6 load tests, R2 backups, `/version`, chunk splitting, `REQUIRE_TURNSTILE=1`, Redis rate limiters

## Open verification items (need dashboard/GitHub access)

GitHub secrets & CI run history · Cloudflare account state (project, custom domain, why 522) · main-site DNS/CNAME state for operionerp.xyz · live server identity for api.operionerp.xyz (which compose file, Postgres vs SQLite) · `addon_price_mappings` population · payment-leniency legal sign-off status.
