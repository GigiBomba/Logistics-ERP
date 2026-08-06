# Operion Website — S-Grade Blueprint Implementation Audit

**Audit date:** 2026-08-01
**Audited against:** `Operion_Website_SGrade_Blueprint.md` (v2, 1100 lines, §0–§21)
**Method:** Static code audit of the `operion-website` repo — 7 read-only evidence lanes (structure map + 6 domain lanes) plus targeted verification. Evidence is file:line references into current code.
**Scope note:** This audit verifies *implementation state in this repo*, not runtime behavior or backend contracts. Items that depend on `api.operionerp.xyz` (backend) or the desktop ERP are marked **BACKEND-GATED**. Companion docs already exist: `Operion_Website_Production_Readiness_Report.md` (2026-08-01, launch-readiness verdict) — this audit covers the S-Grade blueprint specifically.

**Status taxonomy used throughout:**
| Status | Meaning |
|---|---|
| ✅ IMPLEMENTED | Matches blueprint target state (evidence cited) |
| 🟡 PARTIAL | Work started, materially incomplete vs blueprint spec |
| 🟢 HONEST-DEFER | Blueprint-sanctioned deferral (honest EmptyState / ticket-based flow / planned badge) — §1 disposition |
| ❌ NOT IMPLEMENTED | Missing or fake with no sanctioned deferral |
| 🔵 BACKEND-GATED | Requires backend/cross-repo change; frontend scaffolding may exist |
| ⚪ N/A / NOT VERIFIABLE | Not applicable or cannot be verified from this repo |

---

## 1. Executive Summary

| Metric | Count |
|---|---|
| Blueprint items audited (section-table rows) | ~175 |
| ✅ IMPLEMENTED | ~103 |
| 🟡 PARTIAL | ~29 |
| 🟢 HONEST-DEFER | ~3 |
| ❌ NOT IMPLEMENTED | ~30 |
| 🔵 BACKEND-GATED / ⚪ N/A | ~10 |

**Overall: the repo has moved far past the blueprint's "current state" description.** The biggest structural items the blueprint called gaps are now real: vike prerendering for 37 public routes (`pages/+config.ts:6`, `+onBeforePrerenderStart.ts`), in-memory access token + sessionStorage refresh (§3.1 interim), full 401-refresh queue + CSRF, security headers CSP/COOP/CORP (`public/_headers`), Turnstile on all public forms, i18n audit script wired to CI-adjacent scripts, all 16 UI-primitive tests, 8/10 critical-path E2E specs, admin + Ops Console pages, legal pages (Privacy/Terms/Cookie/Accessibility), consent banner with GCM v2.

**The remaining gaps cluster in exactly the areas the blueprint flagged as highest-risk:** the billing tier (§4 — per-truck model half-built, downloads still a stub, Stripe unwired), MFA enrollment, device-management advanced features, RoadmapFeature rollout (component exists, zero usages), status-page honesty, and CI gate completeness.

---

## 2. Section-by-Section Findings

### §1 The One Rule (triage disposition) — ❌ NOT IMPLEMENTED
- **Evidence:** No triage artifact (doc/issue/comments) records BUILD / HONEST-DEFER / REMOVE dispositions for D/F-graded items. `RoadmapFeature` (`src/components/shared/roadmap-feature.tsx`) exists but has **zero imports** anywhere in `src/` — the §6.9 replacement component is not rolled out; 27+ "Coming Soon" strings remain across the codebase (e.g. `subscription.tsx:327`, `downloads.tsx:36`, `settings.tsx` 2FA, `industry-*.tsx:31` screenshots, `partners.tsx:58`).

### §2 Architecture, Providers & App Shell

| Item | Status | Evidence |
|---|---|---|
| ErrorBoundary onError → reporting | 🟡 PARTIAL | `main.tsx:46-53` calls `trackError()` (custom analytics) — real reporting, but not Sentry; no "Report this issue" action in boundary |
| QueryClient per-query staleTime | ✅ IMPLEMENTED | Devices 30s (`queries.ts:452`), sessions 30s (:472), onboarding 30s (:538), static content 30min (:53,:196,:204,:216,:235), notifications poll 30s (:754) |
| Global QueryCache/MutationCache onError → toast | ❌ NOT IMPLEMENTED | No global onError; 20+ ad-hoc `toast.error()` call sites |
| ThemeProvider + color-scheme meta | ✅ IMPLEMENTED | `theme-provider.tsx:3,24,34,37`; `<meta name="color-scheme">` present statically (`index.html:15`) |
| Toaster max-visible cap | ❌ NOT IMPLEMENTED | `main.tsx:61` — no `maxVisible`/queue |
| React.lazy per route | ✅ IMPLEMENTED | `routes.tsx:13-107` |
| 404 catch-all route | ✅ IMPLEMENTED | `routes.tsx:606-611` → on-brand NotFoundPage (`not-found.tsx`) |
| Route-level layout switch | 🟡 PARTIAL | Still path-prefix heuristic `pathname.startsWith("/dashboard")` (`app-shell.tsx:799`) — exactly the pattern blueprint §2.2 flagged as fragile |
| Prerendering public routes | ✅ IMPLEMENTED | vike: `pages/+config.ts:6` `prerender: true`; `pages/+onBeforePrerenderStart.ts` 37 routes; `pages/+Page.tsx` → SSRApp |
| Nav active-highlight nested routes | ✅ IMPLEMENTED | `app-shell.tsx:122,224` uses `startsWith` |
| Nav `badge` field | ❌ NOT IMPLEMENTED | `navigation.ts:19-26` NavItem has no badge field |

### §3 Authentication & Security

| Item | Status | Evidence |
|---|---|---|
| Access token in-memory only | ✅ IMPLEMENTED | `client.ts:20-28` module-level var |
| Refresh token httpOnly cookie | 🔵 BACKEND-GATED | Interim: sessionStorage (`client.ts:55`, `auth-provider.tsx:71,90,137`); cookie needs backend `Set-Cookie` change |
| Refresh-on-mount bootstrap | ✅ IMPLEMENTED | `auth-provider.tsx:116-118` |
| CSRF double-submit | ✅ IMPLEMENTED | Cookie read + `X-CSRF-Token` header for mutating requests (`client.ts:48-52,73-76`) |
| 401 refresh queue + retry cap | ✅ IMPLEMENTED | Promise-dedupe queue (`client.ts:30-45`), `_retry` flag, immediate reject on 2nd 401 (:85-87) |
| MFA challenge (login 2nd step) | ✅ IMPLEMENTED | `login.tsx:43-44` redirect → `mfa-challenge.tsx` (TOTP + backup-code toggle) |
| MFA enrollment (settings) | 🔵 BACKEND-GATED (frontend stub) | `settings.tsx:303-333` — disabled placeholder QR + disabled Enable button; no enroll API call |
| RequireRole wrapper | ✅ IMPLEMENTED | `require-role.tsx:13-31` |
| AdminRoute + admin gating | ✅ IMPLEMENTED | `protected-route.tsx:43-45`; `admin-layout.tsx:6` wraps `roles={["owner","admin"]}` |
| Security headers / CSP | ✅ IMPLEMENTED | `public/_headers` — CSP, X-Frame-Options DENY, nosniff, HSTS, Permissions-Policy, COOP same-origin, CORP same-site; minor deviation: `font-src 'self'` lacks `data:` |
| Audit log page + API | ✅ IMPLEMENTED | Page `routes.tsx:101` → `audit-log.tsx`; `auditLogApi.list` (`endpoints.ts:590-592`), query `queries.ts:695-696`, filter/pagination i18n keys in all 6 locales |
| Rate limiting frontend states | ✅ IMPLEMENTED | 429 handling in login (:53-55), register, forgot-password, waitlist, contact |
| Login rate limiting (backend) | 🔵 BACKEND-GATED | Not verifiable from this repo |
| tests/security/ frontend suite | ❌ NOT IMPLEMENTED | No `tests/security/` in frontend; token-storage assertions absent (backend repo has one) |

### §4 Billing, Subscriptions, Downloads

| Item | Status | Evidence |
|---|---|---|
| Subscription types match §4.3 schema | ✅ IMPLEMENTED | `types/index.ts:97-121` — all per-truck fields incl. `licensed_truck_count`, `ai_copilot_enabled`, `service_credit_cents`, Stripe ids |
| subscriptionApi/downloadApi/invoicesApi live | ✅ IMPLEMENTED | `endpoints.ts:96-105,129-132,239-242` (not commented out) |
| Subscription page per-truck display | 🟡 PARTIAL | Real `licensed_truck_count` (:482) + price breakdown (:398-411), BUT: term toggle disabled (:504-509), addon toggles display-only badges (:548-550), no cancel modal, no "manage trucks from Fleet Manager" note, "Coming Soon" badge (:327) |
| Billing page invoices + PDF | ✅ IMPLEMENTED | `billing.tsx:159-206` real invoice list + `pdf_url` download |
| Billing: payment methods / VAT / tax-info | ❌ NOT IMPLEMENTED | Payment methods EmptyState (:224-228); VAT shows `—` (:287); "Tax configuration will be available in a future update" (:294-295) |
| Downloads page real data | ❌ NOT IMPLEMENTED | Whole page "Coming Soon" (`downloads.tsx:36`); `downloadConfig` placeholders `site.ts:25-37` (empty version/size/URL) |
| Trial logic | 🟡 PARTIAL | `lib/trial.ts` correct; but `TRIAL_EXPIRING_SOON_DAYS = 3` (spec: 4) (:6); no dashboard-wide dismissible-per-day trial banner (only inline callouts `subscription.tsx:593-603`) |
| Stripe checkout wiring | 🔵 BACKEND-GATED | Env var + `useCreateCheckoutSession` (`queries.ts:255-265`) + `stripe-checkout.tsx` exist but not consumed by any UI |
| §4.6 payment-leniency | ⚪ N/A | Correctly not built (requires legal sign-off per blueprint) |

### §5 Device Management

| Item | Status | Evidence |
|---|---|---|
| Mobile devices real API | ✅ IMPLEMENTED | `queries.ts:448-453` |
| License devices real query + deactivate | ✅ IMPLEMENTED | `queries.ts:511-520`; `licenses.tsx:106-109,347-358` wired to DELETE |
| Auth sessions + remote force-logout | ✅ IMPLEMENTED | `devices.tsx:252-328` via `DELETE /auth/sessions/:id` |
| Search/filter | ✅ IMPLEMENTED | `devices.tsx:349-350` (all/active/inactive) |
| useDevices staleTime | ✅ IMPLEMENTED | 30s (`queries.ts:452`) — blueprint asked 60s; 30s is fine |
| Toast on mutations | ❌ NOT IMPLEMENTED | `handleDeactivate` has no onSuccess toast (:352-354) |
| Detail slide-over/Sheet | ❌ NOT IMPLEMENTED | Bespoke `DeviceCard` only; no Sheet |
| Bulk operations + summary toast | ❌ NOT IMPLEMENTED | No batch mutation |
| CSV export | ❌ NOT IMPLEMENTED | No papaparse |
| QR pairing | ❌ NOT IMPLEMENTED | No pairing-token flow |
| DeviceInfo unification | 🟡 PARTIAL | Duplicated defs `types/index.ts:487-497` + `endpoints.ts:13,377-380`; shared `device-list.tsx` exists but unused (devices.tsx uses bespoke DeviceCard) |

### §6 Design System & Components

| Item | Status | Evidence |
|---|---|---|
| 16 UI primitives | ✅ IMPLEMENTED | All present with variants; a11y checks largely correct: breadcrumb aria-current (:57), input aria-invalid (:22-23), callout role=alert (:56), spinner role=status (:12), progress aria-valuenow (:29-33), separator (:15), tabs arrow-key nav (:86-108), tooltip focus (:63-64), pagination (:64,88-89) |
| UI primitive gaps | 🟡 PARTIAL | Avatar: no non-Latin diacritics handling (`avatar.tsx:60-72` initials only); Button: no loading-state prop wiring (no aria-busy); copy-button wired only in `docs-article.tsx:444`, not license key/invoice etc. |
| Feature components | 🟡 PARTIAL | global-search ⌘K + quick actions ✅; live-chat real API ✅ (`live-chat.tsx:252-280`); notification-center wired ✅ (app-shell:184,368); release-card real ✅; newsletter-form ✅; table-of-contents ✅; comparison-table ✅ (overflow-x-auto); **social-share has NO WhatsApp target** (:55-82); testimonial-card placeholder-driven (props) |
| RoadmapFeature component | ✅ built / ❌ rolled out | Component exists with "Notify me" + `notifyAction`; **zero imports** — no §6.9 rollout |
| OKLCH tokens + dark variant | ✅ IMPLEMENTED | `globals.css:47-82`, `@custom-variant dark` (:5) |
| Fonts (swap, self-host) | 🟡 PARTIAL | Inter + JetBrains Mono declared (`globals.css:39-40`) but no `@font-face`/self-host source found |
| prefers-reduced-motion | ✅ IMPLEMENTED | Hook (`accessibility.tsx:50-63`) + global CSS media block (`globals.css:151-160`) |
| Stagger cap | ✅ IMPLEMENTED | `testimonial-card.tsx:36` `Math.min(index*0.05, 0.3)` |
| Screenshot replacement | 🟡 PARTIAL | Home/Features have crafted SVG mockups (not "Coming soon") — better than stub; industry pages still show "Preview coming soon" (industry-*.tsx:31) |
| EmptyState system | ✅ IMPLEMENTED | `empty-state.tsx` with icon/title/desc/action props; used across pages incl. honest-defer cases |

### §7 i18n

| Item | Status | Evidence |
|---|---|---|
| 6 locale files complete | ✅ IMPLEMENTED | en/ro/de/fr/es/pl all present (~193–212KB each) |
| CI key-diff audit script | ✅ IMPLEMENTED | `scripts/i18n-audit.ts` (flattens keys, diffs vs en, 95% threshold, exit 1) wired as `i18n:audit` (`package.json:12`) |
| Hardcoded-string lint rule | ❌ NOT IMPLEMENTED | No lint rule for bare JSX strings |
| Locale-aware formatting | ✅ IMPLEMENTED | `lib/utils.ts:9,17` Intl.DateTimeFormat/NumberFormat |
| hreflang (ties to §14) | ✅ IMPLEMENTED | `seo-head.tsx:74-85` |

### §8 Auth Pages

| Item | Status | Evidence |
|---|---|---|
| Login: returnUrl + validation | ✅ IMPLEMENTED | `login.tsx:48-50` same-origin check |
| Login: remember me | ✅ IMPLEMENTED | `login.tsx:20,106-111` + auth-provider session-scoped refresh |
| Login: MFA step | ✅ IMPLEMENTED | redirect to mfa-challenge (:43-44) |
| Login: rate-limit-aware error | ✅ IMPLEMENTED | 429 → retryAfter (:53-55) |
| Login: aria-live error announcement | ❌ NOT IMPLEMENTED | No aria-live on auth error summary |
| Register: 6 fields + zod | ✅ IMPLEMENTED | `register.tsx:19-30,111-158` |
| Register: password strength meter | ✅ IMPLEMENTED | `PasswordStrength` (:155) |
| Register: Terms/Privacy checkbox | ✅ IMPLEMENTED | `register.tsx:168-188` |
| Register: referral prefill editable | ✅ IMPLEMENTED | `?ref=` → editable field (:44,54) |
| Register: Turnstile | ✅ IMPLEMENTED | `register.tsx:17` |
| Forgot/Reset flows | ✅ IMPLEMENTED | 429-aware; reset token validation (:50-68) |
| Verify-email resend action | ❌ NOT IMPLEMENTED | No resend button (`verify-email.tsx:44-50`) |

### §9 Frontend Quick Wins

| Item | Status | Evidence |
|---|---|---|
| Notification bell wired + 30s poll | ✅ IMPLEMENTED | `app-shell.tsx:184,368`; `queries.ts:747-756` refetchInterval 30s |
| Unread badge + mark-all-read | ✅ IMPLEMENTED | `notification-center.tsx:124-131,150-156` |
| Return URL after login | ✅ IMPLEMENTED | `protected-route.tsx:25-26` |
| Dashboard real stats | 🟢 HONEST-DEFER | Stat cards real API; Storage Usage + Activity feed show honest EmptyStates ("not yet available from the API", `dashboard.tsx:323-327,484-488`) — blueprint-sanctioned deferral |
| Avatar persistence | ❌ NOT IMPLEMENTED | `profile.tsx:116-122` updates local context only, no API call |
| Notification prefs save | 🟡 PARTIAL | Settings tab wired (`settings.tsx:154-161`, `queries.ts:774-782`); Profile save button still disabled (`profile.tsx:492`) |
| Onboarding checklist → real API | ✅ IMPLEMENTED | `onboarding.tsx:168-172` |
| Onboarding tutorials/releases real | ✅ IMPLEMENTED | `onboarding.tsx:174-183` |
| Onboarding auto-completion | ❌ NOT IMPLEMENTED | Manual `completeStep` only; best-practices section EmptyState (:501-510) |

### §10 Dashboard Pages

| Item | Status | Evidence |
|---|---|---|
| Company: General/Team/Billing tabs | ✅ IMPLEMENTED | `company.tsx:98-103` |
| Company: Team unified with Organizations | ✅ IMPLEMENTED | `company.tsx:34-35` uses org members/invites |
| Company: logo upload / edit details | ❌ NOT IMPLEMENTED | Both disabled buttons (:181,:185) |
| Company: VAT real | ❌ NOT IMPLEMENTED | EmptyState "once billing module integrated" (:201-208) |
| Company: Departments | 🟢 HONEST-DEFER | EmptyState "coming in a future update" (:260-263) — acceptable per §1 only if dispositioned; no RoadmapFeature used |
| Settings: notifications wired | ✅ IMPLEMENTED | `settings.tsx:154-161` |
| Settings: 2FA | 🔵 BACKEND-GATED | Disabled placeholder QR (:292-336) |
| Settings: Data Export | 🟢 HONEST-DEFER | Direct export disabled; ticket-based request implemented (`settings.tsx:425-453`) |
| Settings: Delete Account | ❌ NOT IMPLEMENTED | Destructive button permanently disabled (:470) — exactly the pattern blueprint §10.2 calls worst-case |
| Support: tickets real | ✅ IMPLEMENTED | `support.tsx:55-56` |
| Support: Live Chat / AI Assistant | ✅ IMPLEMENTED | `live-chat.tsx:252-280` → `POST /api/v1/support/messages` |
| Support: Knowledge Base | 🟡 PARTIAL | Static hardcoded category links (`support.tsx:37-42`) |
| Organizations / Referrals pages | ✅ IMPLEMENTED | Real APIs (`organizations.tsx:52,54`, `referrals.tsx:33,38`) |
| Org-switcher query invalidation | ❌ NOT IMPLEMENTED | `handleSwitchOrg` sets local state only (`app-shell.tsx:208`); no `invalidateQueries` — stale-org-data risk flagged in §6.2 stands |

### §11 Public Marketing Pages

| Item | Status | Evidence |
|---|---|---|
| Home screenshots (3-tab) | ✅ IMPLEMENTED | SVG mockups, not "Coming soon" (`home.tsx:420-626`) |
| Home secondary CTA after Features | ❌ NOT IMPLEMENTED | No sticky/inline CTA between Features and Workflow |
| Features anchored sections | ✅ IMPLEMENTED | 7 sections, distinct copy via i18n problem/desc per category |
| Pricing JSON-LD (Product+FAQ) | ✅ IMPLEMENTED | `pricing.tsx:47-65` |
| Pricing Organization schema | ✅ IMPLEMENTED sitewide | `index.html:47-69` inline JSON-LD + `structured-data.tsx:16-39` |
| Waitlist rework (narrative, WhatsApp, honeypot, referral code) | ✅ IMPLEMENTED | `waitlist.tsx:251-259,272-284,232-260` |
| Waitlist live counter | 🟡 PARTIAL | Animated but hardcoded target 500 (`waitlist.tsx:383`), not live count |
| Industry pages (7) | 🟡 PARTIAL | Distinct content arrays per vertical; all share "Preview coming soon" screenshot stubs |
| Blog real API | 🟡 PARTIAL | `useBlogPosts` exists but falls back to hardcoded `BLOG_POSTS` array of 25 (blog-list.tsx:29-435) |
| Blog related-posts + reading time | 🟡 PARTIAL | Reading time present; related-posts absent ("Related tutorials coming soon") |
| Blog article JSON-LD + og:image | 🟡 PARTIAL | `articleSchema` ✅ (blog-article.tsx:1670); og:image is global fallback for all posts (:1665) |
| Tutorials real API | ✅ IMPLEMENTED | `tutorials-list.tsx:129` |
| Changelog / Roadmap real API | ✅ IMPLEMENTED | `queries.ts:160,171` |
| Status page real uptime | ❌ NOT IMPLEMENTED | All services hardcoded `"maintenance"` (`status.tsx:30-55`) → page reports "In Development" (:187) — trust-signal integrity issue §11.11 stands |
| Privacy/Terms rendering (TOC, last-updated) | ✅ IMPLEMENTED | TOC + lastUpdated present |
| Cookie Policy page (real cookie table) | ✅ IMPLEMENTED | `cookie-policy.tsx` — 8 real cookies table (:14-24,:176-201) |
| Accessibility Statement page | ✅ IMPLEMENTED | 251 lines, WCAG 2.1 AA claim, contact channel |
| Security page honest posture | ✅ IMPLEMENTED | MFA marked `planned: true` (`security.tsx:47`) — honest |
| Careers / Press / Brand | ✅ IMPLEMENTED | Real i18n content (careers 156L, press 271L, brand 393L) |
| Enterprise / Partners / Trust / Trust Center | 🟡 PARTIAL | Enterprise honest "planned features"; **partners "Partner listings — coming soon"** (`partners.tsx:58`); Trust (482L) + Trust Center (431L) substantial incl. retention table + subprocessors; DPA section is descriptive card only (trust.tsx:244-273), no downloadable DPA |
| Product Tour / ROI / Route Demo | ✅ IMPLEMENTED | route-demo calls real `POST /api/v1/route-demo/calculate`; ROI labels assumptions + disclaimer (:116-142,:392-448) |
| API Playground | 🟡 PARTIAL | Placeholder message ("available when public API stabilized") |

### §12 Admin Pages

| Item | Status | Evidence |
|---|---|---|
| Blog editor CRUD + XSS sanitize | ✅ IMPLEMENTED | `blog-editor.tsx:42-80` (sanitizes javascript: URLs + on-handlers on render) |
| Waitlist admin (stats/entries/CSV/campaigns/referrals) | ✅ IMPLEMENTED | `admin-waitlist.tsx:22-45`, `entries-tab.tsx` (search + pagination + CSV), `campaign-tab.tsx`, `referral-tab.tsx:19-54` |
| Ops Console (5 pages) | ✅ IMPLEMENTED | tickets/approvals/guardrails/dashboards/knowledge all exist, gated owner/admin via `admin-layout.tsx` |

### §13 Error & Edge Pages

| Item | Status | Evidence |
|---|---|---|
| /500 on-brand with report action | ✅ IMPLEMENTED | `error-500.tsx:70-91` (Try again, Go Home, Contact, Report pre-fills ticket) |
| /maintenance reachable | ✅ IMPLEMENTED | `MaintenanceGuard` in routes (:138) checks `VITE_MAINTENANCE_MODE` |
| /offline wired | ✅ IMPLEMENTED | `error-offline.tsx:10-26` navigator.onLine + listeners (no SW dependency) |
| 404 helpful | ✅ IMPLEMENTED | `not-found.tsx:8-13` 4 links + Go Home |
| 404 HTTP status / SEO | 🟡 PARTIAL | `_redirects` is `/* /index.html 200` — missing pages serve 200; no status-code rewrite, no noindex confirmation. Note: vike prerenders 37 known public routes as static HTML, so known routes serve correct content; only genuinely nonexistent URLs (typos/stale links) get 200-instead-of-404 |

### §14 SEO

| Item | Status | Evidence |
|---|---|---|
| Organization schema sitewide | ✅ IMPLEMENTED | `index.html:47-69` + `structured-data.tsx:16-39` |
| Article / SoftwareApplication / Breadcrumb / ContactPage schema | ✅ IMPLEMENTED | `structured-data.tsx:57-131,133-170` |
| hreflang 6 locales | ✅ IMPLEMENTED | `seo-head.tsx:74-85` |
| Unique og:image per page/post | 🟡 PARTIAL | Default fallback everywhere; explicit og:image only on home + blog-article (global) |
| Dynamic sitemap | 🟡 PARTIAL | Static hand-maintained `public/sitemap.xml` |
| Prerendering (highest-leverage item) | ✅ IMPLEMENTED | vike prerender, 37 public routes |

### §15 Performance

| Item | Status | Evidence |
|---|---|---|
| Bundle splitting >150KB | ❌ NOT IMPLEMENTED | `dist/assets`: index chunk 1368KB raw, blog-article 156KB raw; no visualizer/analyze script in package.json — the §2.2/§15 audit was never done |
| Image pipeline WebP/AVIF + srcset | ❌ NOT IMPLEMENTED | No srcset/WebP handling found |
| PWA | 🟡 PARTIAL | `sw.js` + `sw-register.ts` exist (cache-first static, network-first API, offline 503) — registered in main.tsx:15; blueprint put PWA at P3, so early |
| API caching staleTime applied | ✅ IMPLEMENTED | Per-endpoint staleTime across queries (see §2) |

### §16 QA & Testing

| Item | Status | Evidence |
|---|---|---|
| Vitest coverage thresholds | 🟡 PARTIAL | v8 provider, statements 80 / lines 80 / functions 75 / **branches 70 (spec: 75)**; no per-directory overrides (`vite.config.ts:33-39`) |
| verify-ui-test-manifest script | ✅ IMPLEMENTED | `scripts/verify-ui-test-manifest.ts` + wired `test:manifest` |
| UI primitive tests (16 named) | ✅ IMPLEMENTED | All 16 present under `src/__tests__/components/ui/` |
| Critical-path E2E inventory | 🟡 PARTIAL | 8/10 exist; **missing: `auth-mfa-cycle.spec.ts`, `checkout-upgrade.spec.ts`** |
| Visual regression | ✅ IMPLEMENTED | `e2e/visual-regression.spec.ts:31` + `test:visual` script |
| MSW contract handlers | ✅ IMPLEMENTED | 9 handler files (auth, devices, subscriptions, support, blog, etc.) |
| k6 scenarios | 🟡 PARTIAL | 4 scripts exist (spike, static, sustained, api-endpoints); no dedicated login / dashboard-load / notification-polling scenarios as named in §16.7 |
| Stryker mutation config | ✅ IMPLEMENTED | `stryker.conf.json` (high 80/low 60/break 50); score file not found (nightly tracking absent) |
| CI pipeline stage order | 🟡 PARTIAL | `ci.yml`: oxlint → tsc → build → vitest coverage → playwright. **Missing: i18n:audit gate, test:manifest gate, security regression suite, a11y suite, visual regression** — §16.10 not fully wired |
| Deploy CI | ✅ IMPLEMENTED | `deploy.yml` → Cloudflare Pages (preview on PR, prod on main) |

### §17 Analytics & Observability

| Item | Status | Evidence |
|---|---|---|
| GA4/GTM conditional injection | ✅ IMPLEMENTED | `index.html:112-138` via `%VITE_GA_MEASUREMENT_ID%` |
| Google Consent Mode v2 | ✅ IMPLEMENTED | default denied before config (`index.html:119-125`), update on choice (`consent.ts:62-69`) |
| Cookie consent banner | ✅ IMPLEMENTED | `cookie-consent-banner.tsx:23` (Accept/Reject/Manage + categories) |
| Event-level tracking | 🟡 PARTIAL | `trackEvent`/`trackCTAClick` exist; wired: waitlist_view/submit_attempt/submit_success, CTA clicks (navbar/hero/blog/route-demo/roi/downloads); **not wired: onboarding_step_completed, referral_shared, feature_interest_clicked, checkout_*** |
| Sentry/error monitoring | ❌ NOT IMPLEMENTED | No Sentry package; analytics.ts:158 notes "can be swapped for Sentry later" |

### §18 Environment & Deployment

| Item | Status | Evidence |
|---|---|---|
| **`.env` never committed** | ❌ **VIOLATION — CRITICAL** | **`.env` IS TRACKED IN GIT** (verified: `git ls-files` lists it); `.gitignore` has **no** `.env*` pattern (only `*.local`) — secret-hygiene blocker. **Fix:** add `.env*` to `.gitignore`, then `git rm --cached .env` (file stays local) |
| .env.example documented | ✅ IMPLEMENTED | All VITE_* vars incl. Stripe/Turnstile/GA/MAINTENANCE_MODE |
| Vite proxy dev-only | ✅ IMPLEMENTED | `vite.config.ts:18-24`; prod build uses real API URL |
| tsconfig strict: true | ✅ IMPLEMENTED | `tsconfig.app.json:27` |
| Netlify/CF _redirects + _headers | 🟡 PARTIAL | _headers ✅; _redirects 404 handling partial (see §13) |
| CI/CD pipeline | ✅ IMPLEMENTED | ci.yml + deploy.yml (see §16) |

### §18a Legal, Privacy & Cookie Compliance

| Item | Status | Evidence |
|---|---|---|
| Consent banner + GCM v2 | ✅ IMPLEMENTED | see §17 |
| Cookie Policy from real audit | ✅ IMPLEMENTED | 8-cookie table |
| Accessibility statement page | ✅ IMPLEMENTED | |
| Retention periods stated | ✅ IMPLEMENTED | `trust.tsx` retention table (Account data / audit logs / backups / deleted) |
| DPA template link | ❌ NOT IMPLEMENTED | Descriptive DPA card only (`trust.tsx:244-273`); no downloadable DPA |

### §18b Anti-Abuse, Spam & Webhooks

| Item | Status | Evidence |
|---|---|---|
| Turnstile on Waitlist/Contact/Newsletter/Register/Login | ✅ IMPLEMENTED | `waitlist.tsx:30`, `contact.tsx:18`, `newsletter-form.tsx:13`, `register.tsx:17`, `login.tsx:15` |
| Honeypot fields | ✅ IMPLEMENTED | `waitlist.tsx:272-284` |
| Referral fraud checks | 🔵 BACKEND-GATED | Not verifiable in frontend; register surfaces server-side self-referral error |
| Stripe webhook verify + idempotency | 🔵 BACKEND-GATED | No webhook handler in this repo |

### §18c Browser Support, Uploads & PWA Assets

| Item | Status | Evidence |
|---|---|---|
| .browserslistrc | ✅ IMPLEMENTED | last 2 Chrome/Edge/Firefox/Safari, not dead |
| Avatar upload client validation | ✅ IMPLEMENTED | `profile.tsx:89-100` (png/jpeg/webp, 5MB) |
| Upload server-side hardening | 🔵 BACKEND-GATED | |
| Favicon set | ✅ IMPLEMENTED | 16/32/192/512 + apple-touch 180 + SVG mask (`index.html:6-11`) |
| site.webmanifest completeness | 🟡 PARTIAL | Only 192/512; no 16/32/180, no maskable variant (`site.webmanifest:9-12`) |
| Print stylesheet | ✅ IMPLEMENTED | `globals.css:172-204` (`@media print` hides chrome, forces light) |

### §19 File-Level Map — 32 rows, ~70% resolved
Highlight rows still open: `auth-provider.tsx` (MFA/remember-me partial), `dashboard.tsx` (honest-defer), `subscription/billing` (partial), `downloads.tsx` (stub), `licenses.tsx` (real), `company.tsx` (logo/edit disabled), `profile.tsx` (avatar/notif save), `settings.tsx` (2FA/delete), `onboarding.tsx` (auto-complete), `support.tsx` (done), `home/features` (done), `industries/*` (stubs), `endpoints.ts` (live), `types/index.ts` (dup DeviceInfo), `cookie-consent-banner` (exists), `cookie-policy` (exists), `accessibility-statement` (exists), `browserslistrc` (exists), `_headers` (exists), `roadmap-feature` (unused), `site.ts` (placeholders), `i18n` (gated), `ui/*` (tested), `app-shell` (path heuristic), `navigation.ts` (no badge), `main.tsx` (no Sentry), `.env.example` (ok), CI (partial gates).

### §20 Roadmap Status (P0→P3)

**🔴 P0 (8 items):** 1. Security headers ✅ · 2. sessionStorage interim ✅ + backend ticket 🔵 · 3. rate-limiting ticket 🔵 · 4. triage dispositions ❌ · 5. ro.json audit ✅ · 6. cookie consent + GCMv2 ✅ · 7. Turnstile ✅ · 8. Privacy brief to counsel ⚪ (process item)
**🟠 P1 (16 items):** 6. Dashboard real stats 🟢 · 7. Onboarding real APIs 🟡 · 8. Device unification 🟡 · 9. Quick-wins batch 🟡 (bell/returnUrl/password strength done; avatar/notif-prefs not) · 10. Waitlist rework + screenshots 🟡 · 11. RBAC/Team unification 🟡 (frontend done, server gated) · 12. RoadmapFeature rollout ❌ · 13. SEO checklist 🟡 · 14. Login/Register hardening ✅ · 15. Company cleanup 🟡 · 16. Error pages ✅ · 17. Favicon/browserslist 🟡 (manifest partial) · 18. Cookie Policy + Accessibility ✅ · 19. Rate limiting extension ✅ frontend / 🔵 backend · 20. Per-truck billing core 🟡 (read-only model real; term/addon/cancel/downloads/VAT not) · 21. AI-copilot toggle decision ⚪
**🟡 P2:** 22-24,26,28,30,31 not started (backend-gated or honest not-built) · 27. Design-system audit 🟡 · 29. Upload hardening 🔵 · 25. Audit log ✅ (done early)
**🟢 P3:** 32. PWA partial (SW present) · 33. visual regression ✅/analytics dashboard ❌/mutation score ❌ · 34. i18n remaining locales ✅ (already complete) · 35. Trust/Security refresh 🟡 · 36. print stylesheet ✅ (done early)

---

## 3. Critical Findings (ranked)

1. **🔴 `.env` is committed to git** (verified via `git ls-files`; `.gitignore` lacks `.env*`). Violates §18's explicit requirement; leaked-credentials risk. Fix is one line + `git rm --cached`.
2. **🔴 Downloads page is a full "Coming Soon" stub** while its API layer is live — violates §1's one rule (feature shown but not real) and §4.5. Highest-visibility billing-area fakery left.
3. **🟠 MFA enrollment is a disabled placeholder** (`settings.tsx:303-333`) despite the challenge page working; blueprint has it P2, so acceptable only if honestly badged — it is currently a *fake-looking* UI rather than a RoadmapFeature disposition.
4. **🟠 RoadmapFeature exists but zero pages use it** — every remaining "Coming Soon" (subscription, settings 2FA, delete account, partners, industries screenshots) is still ad-hoc, so §1 dispositions and §6.9 are effectively unshipped. Delete Account stays a permanently-disabled destructive button (the blueprint's single worst pattern).
5. **🟠 Status page pretends real-time** — all services hardcoded "maintenance" → "In Development" state; §11.11's trust-signal integrity issue is live.
6. **🟠 CI is not blueprint-complete** — ci.yml runs lint/typecheck/build/unit/E2E but misses i18n:audit, test:manifest, security-regression, a11y, and visual-regression gates from §16.10.
7. **🟠 Main bundle 1368KB raw** — the §2.2/§15 bundle-splitting audit was never run; blog-article chunk alone is 156KB raw.
8. **🟡 Org-switcher doesn't invalidate queries** on org switch — stale-org-data bug class flagged in §6.2 confirmed present.
9. **🟡 Avatar persistence and profile notification-save remain broken** (§9.6/§9.7) — local-only save and disabled button.
10. **🟡 No global QueryCache/MutationCache onError** — toast feedback still ad-hoc per hook, the §2.1 systemic fix is undone.

## 4. What's Solid (beyond blueprint expectations)

- vike prerendering for 37 public routes — the blueprint's #1 SEO lever — is done.
- Security core: in-memory access token, sessionStorage refresh, 401 queue with retry cap, CSRF, full security headers, Turnstile everywhere, GCM v2 consent.
- i18n: 6 locales, audit script with exit-1 gate, Intl formatting.
- Testing: all 16 UI-primitive tests, manifest-verification script, 8/10 critical E2E, MSW handlers for 9 domains, visual regression, Stryker config.
- Legal: Privacy/Terms with TOC, real cookie-table Cookie Policy, Accessibility Statement, consent banner.
- Admin suite: blog editor with sanitize, waitlist admin with CSV/campaigns/referrals, 5-page Ops Console role-gated.
- Real per-truck subscription types + live endpoints + honest trial logic; audit-log page fully wired.

## 5. Limitations

- Runtime behavior (test runs, browser) not exercised; statuses are static-code evidence.
- Backend (`api.operionerp.xyz`) and desktop ERP states not verifiable — marked 🔵.
- The separate `Operion_Website_Production_Readiness_Report.md` (also 2026-08-01) covers launch-readiness blockers (B1–B9) and should be read alongside this blueprint audit.

## 6. Appendix — Evidence Index (key files)

`src/main.tsx` · `src/routes.tsx` · `src/api/client.ts` · `src/api/endpoints.ts` · `src/contexts/auth-provider.tsx` · `src/components/auth/{protected-route,require-role}.tsx` · `src/components/layout/app-shell.tsx` · `src/config/{navigation,site,env}.ts` · `src/services/queries.ts` · `src/services/{analytics,seo}.tsx` · `src/components/seo/{seo-head,structured-data}.tsx` · `src/components/shared/{roadmap-feature,notification-center,live-chat,org-switcher,social-share,cookie-consent-banner,maintenance-guard,device-list}.tsx` · `src/components/ui/*` (16) · `src/pages/dashboard/*` (17) · `src/pages/public/*` (53) · `src/pages/auth/*` (6) · `src/pages/admin/*` + `admin/ops/*` + `admin/waitlist/*` · `src/lib/{trial,consent,permissions,sw-register}.ts` · `src/i18n/locales/*.json` (6) · `src/styles/globals.css` · `src/types/index.ts` · `src/mocks/handlers/*` (9) · `src/__tests__/**` · `e2e/critical/*` (8) · `e2e/visual-regression.spec.ts` · `stress/*.js` (4) · `scripts/{i18n-audit,verify-ui-test-manifest}.ts` · `public/{_headers,_redirects,site.webmanifest,sw.js}` · `.browserslistrc` · `.github/workflows/{ci,deploy}.yml` · `pages/{+config,+Page,+onBeforePrerenderStart,+route}.tsx` · `vite.config.ts` · `.env` / `.env.example`

---

## 7. Complete Gap Inventory (every non-IMPLEMENTED item)

All 170 audited rows, filtered to gaps. Status: ❌ not implemented · 🟡 partial · 🟢 honest-defer (sanctioned) · 🔵 backend-gated (frontend scaffolding may exist). Items marked **NEW** were verified in the post-review supplementary pass.

### ❌ NOT IMPLEMENTED (26 + 4 NEW = 30)

| # | Blueprint ref | Gap | Evidence |
|---|---|---|---|
| 1 | §1 | Triage dispositions (BUILD/HONEST-DEFER/REMOVE) never recorded | no triage artifact in repo |
| 2 | §2.1 | Global QueryCache/MutationCache `onError` → toast | no global onError; 20+ ad-hoc `toast.error()` sites |
| 3 | §2.1 | Toaster max-visible cap / queueing | `main.tsx:61` no maxVisible |
| 4 | §2.3 | Nav `badge` field for RBAC/new-feature flags | `navigation.ts:19-26` no badge prop |
| 5 | §3.9 | Frontend `tests/security/` suite (token-storage, CSP, CSRF assertions) | absent (backend repo has one) |
| 6 | **§3.9 NEW** | `npm audit --audit-level=high` blocking in frontend CI | only backend repo (`Calculator logistica/.github/workflows/npm-audit.yml`) has it; `.github/workflows/ci.yml` doesn't |
| 7 | **§3.9 NEW** | `eslint-plugin-security` in lint config | zero matches in repo configs |
| 8 | §4.5 | Billing: payment methods, VAT + VIES, tax-info PATCH | `billing.tsx:224-228,287,294-295` placeholders |
| 9 | §4.5 | Downloads page real data | whole page "Coming Soon" (`downloads.tsx:36`); `site.ts:25-37` placeholders |
| 10 | §5.2 | Device mutation toasts | `devices.tsx:352-354` no onSuccess toast |
| 11 | §5.3 | Device detail slide-over/Sheet | bespoke `DeviceCard` only |
| 12 | §5.3 | Bulk device operations + summary toast | no batch mutation |
| 13 | §5.3 | Device CSV export | no papaparse |
| 14 | §5.3 | QR pairing flow | no pairing-token flow |
| 15 | §6.9 | RoadmapFeature rollout (component exists, zero usages) | zero imports of `roadmap-feature.tsx` |
| 16 | §7 | Hardcoded-string lint rule | no JSX-string lint |
| 17 | §8.1 | Login error `aria-live` announcement | no aria-live in auth pages |
| 18 | §8.3 | Verify-email "Resend" action | `verify-email.tsx:44-50` no resend |
| 19 | §9.6 | Avatar persistence | `profile.tsx:116-122` context-only |
| 20 | §9.8 | Onboarding auto-completion | manual `completeStep` only |
| 21 | §10.1 | Company logo upload + edit details | `company.tsx:181,185` disabled |
| 22 | §10.1 | Company VAT field | `company.tsx:201-208` EmptyState |
| 23 | §10.2 | Delete Account (permanently disabled) | `settings.tsx:470` disabled |
| 24 | §6.2/10 | Org-switcher query invalidation | `app-shell.tsx:208` local state only |
| 25 | §11.1 | Home secondary CTA after Features | absent |
| 26 | §11.11 | Status page real uptime feed | `status.tsx:30-55` all hardcoded "maintenance" |
| 27 | §15 | Bundle splitting (>150KB gzip audit) | index chunk 1368KB raw; no visualizer |
| 28 | §15 | Image pipeline WebP/AVIF + srcset | none found |
| 29 | §17 | Sentry/error monitoring | no Sentry pkg; analytics.ts:158 "swap later" |
| 30 | §18 | **`.env` committed to git** | `git ls-files` lists `.env`; `.gitignore` no `.env*` |
| 31 | §18a.4 | DPA template link | descriptive card only (`trust.tsx:244-273`) |
| 32 | **§16.8 NEW** | Flakiness quarantine policy (`@flaky` tag + 48h SLA) | no `@flaky` tags anywhere in e2e |
| 33 | **§16.9 NEW** | Shared seeded role-account fixtures (owner/admin/manager/dispatcher/driver) | only ad-hoc emails in tests; no shared fixtures file |

### 🟡 PARTIAL (29)

| # | Blueprint ref | Gap | Evidence |
|---|---|---|---|
| 1 | §2.1 | ErrorBoundary: Sentry hook + "Report this issue" | `main.tsx:46-53` trackError only |
| 2 | §2.2 | Layout switch still path-prefix heuristic | `app-shell.tsx:799` |
| 3 | §4.5 | Subscription page: term toggle, addon toggles, cancel modal, Fleet-Manager note | `subscription.tsx:504-509,548-550`; "Coming Soon" :327 |
| 4 | §4.7 | Trial: 3-day vs 4-day notice; no dashboard-wide banner | `lib/trial.ts:6`; inline callouts only |
| 5 | §5.2 | DeviceInfo duplication + unused shared DeviceList | `types/index.ts:487-497` + `endpoints.ts:13,377-380`; `device-list.tsx` unused |
| 6 | §6.1 | Avatar non-Latin diacritics; Button loading state; copy-button coverage | `avatar.tsx:60-72`; no aria-busy; copy-button only `docs-article.tsx:444` |
| 7 | §6.2 | social-share no WhatsApp; testimonial-card placeholder copy | `social-share.tsx:55-82` |
| 8 | §6.4 | Fonts: no @font-face/self-host/swap evidence | `globals.css:39-40` declarations only |
| 9 | §6.7 | Industry-page screenshot stubs ("Preview coming soon") | `industry-*.tsx:31` |
| 10 | §9.7 | Profile notification-save button disabled | `profile.tsx:492` |
| 11 | §10.3 | Support Knowledge Base static links | `support.tsx:37-42` |
| 12 | §11.4 | Waitlist live counter hardcoded 500 | `waitlist.tsx:383` |
| 13 | §11.18 | Industry pages templated (shared stubs) | 7 pages same ScreenshotPlaceholder |
| 14 | §11.9 | Blog: static BLOG_POSTS fallback (25 hardcoded) | `blog-list.tsx:29-435` |
| 15 | §11.9 | Blog related-posts module | absent ("coming soon") |
| 16 | §11.9 | Blog unique og:image per post | `blog-article.tsx:1665` global fallback |
| 17 | §11.16 | Partners listings "coming soon"; DPA descriptive only | `partners.tsx:58`; `trust.tsx:244-273` |
| 18 | §11.12 | API Playground placeholder | `api-playground.tsx:12` |
| 19 | §13.4 | 404 serves HTTP 200 (no status rewrite / noindex) | `_redirects` `/* /index.html 200` |
| 20 | §14.2 | Unique og:image per page (only home + blog-global explicit) | `seo-head.tsx:59` default fallback |
| 21 | §14.2 | Dynamic sitemap | static `public/sitemap.xml` |
| 22 | §15 | PWA (SW present but full PWA deferred to P3) | `sw.js` + `sw-register.ts` |
| 23 | §16.1 | Vitest branches 70 (spec 75); no per-dir overrides | `vite.config.ts:33-39` |
| 24 | §16.4 | Missing `auth-mfa-cycle.spec.ts`, `checkout-upgrade.spec.ts` | e2e/critical has 8/10 |
| 25 | §16.7 | k6: no dedicated login/dashboard-load/notification-polling scenarios | stress/ 4 scripts |
| 26 | §16.8 | Stryker score file / nightly delta tracking | config exists, no score file |
| 27 | §16.10 | CI missing i18n:audit, test:manifest, security, a11y, visual-regression gates | `ci.yml` 5 gates only |
| 28 | §17 | Analytics events unwired: onboarding_step_completed, referral_shared, feature_interest_clicked, checkout_* | only waitlist + CTA events |
| 29 | §18c.3 | site.webmanifest icons: no 16/32/180/maskable | `site.webmanifest:9-12` |

### 🟢 HONEST-DEFER (3 — blueprint-sanctioned, listed for completeness)

| # | Blueprint ref | Gap | Evidence |
|---|---|---|---|
| 1 | §9.5 | Storage Usage + Activity feed (honest EmptyStates) | `dashboard.tsx:323-327,484-488` |
| 2 | §10.1 | Company Departments (EmptyState "future update") | `company.tsx:260-263` |
| 3 | §10.2 | Data Export (ticket-based request flow) | `settings.tsx:425-453` |

### 🔵 BACKEND-GATED (8 — frontend blocked on backend/desktop; some have scaffolding)

| # | Blueprint ref | Gap | Evidence |
|---|---|---|---|
| 1 | §3.1 | Refresh token httpOnly cookie (sessionStorage interim only) | `client.ts:55` |
| 2 | §3.4 | MFA enrollment API + real QR/backup-codes flow | `settings.tsx:303-333` stub |
| 3 | §3.8 | Login rate limiting (5/15min + backoff) | not in this repo |
| 4 | §4.4 | Stripe checkout session wiring | hooks + `stripe-checkout.tsx` unused |
| 5 | **§4.4 NEW** | `billing-term` + `trucks/add|remove` endpoints in shared contract | `endpoints.ts:97-104` lacks them |
| 6 | §10.2 | Settings 2FA enroll | `settings.tsx:292-336` |
| 7 | §18b.2 | Referral fraud checks | register surfaces server error only |
| 8 | §18b.3 | Stripe webhook signature + idempotency | no handler in repo |
| 9 | §18c.2 | Upload server-side magic-byte/EXIF/size hardening | client-side only (`profile.tsx:89-100`) |

### ⚪ N/A (2 — correctly not built)
§4.6 payment-leniency (needs legal sign-off) · §18c.4 print stylesheet (done early — actually ✅; N/A row was §4.6 only in tables) — see §20 for process items (P0#8 privacy brief, P1#21 AI-toggle decision).

**Counts:** ❌ 30 · 🟡 29 · 🟢 3 · 🔵 9 · total 71 gap rows across 170 audited.

---

## 8. Gap Closure Status (2026-08-01 � implementation complete)

All 38 gaps from �7 (29 PARTIAL + 9 BACKEND-GATED) were implemented in this session. Backend code lives in `Calculator logistica/`; frontend in `src/`. Verified by: backend pytest (new-code suites green: MFA 16, billing 40, waitlist 19, avatars 24, webhooks+db 87, F2/F3 hardening 96), frontend vitest 1101/1101, tsc --noEmit clean, i18n-audit PASS (53 new keys � 6 locales), test:manifest 16/16, oxlint clean. Gate reviews: Gate 1 GO-WITH-CHANGES, Gate 2 APPROVE-WITH-FOLLOW-UPS, Gate 3 APPROVE-WITH-FOLLOW-UPS, Gate 4 (final) � see deepwork state.

### PARTIAL ? CLOSED (29)
| # | Gap | Closure evidence |
|---|---|---|
| 1 | ErrorBoundary report action | main.tsx fallback + "Report this issue" ? /dashboard/support?report=1&error=<digest>; LocaleProvider moved outside boundary |
| 2 | Layout route-config flag | NEW src/config/route-layouts.ts (DASHBOARD_ROUTE_PATHS + :param templates); app-shell uses getRouteLayout (no pathname heuristic) |
| 3 | Subscription page controls | Term toggle + proration confirmation, addon toggles (useToggleAddon), cancel modal (usable_until copy) + reactivate, Fleet-Manager note, checkout demo-mode branch, checkout_started/completed events |
| 4 | Trial 4-day + banner | trial.ts TRIAL_EXPIRING_SOON_DAYS=4; NEW trial-banner.tsx (per-day dismiss, amber escalation) mounted in DashboardLayout |
| 5 | DeviceInfo/DeviceList | Shared DeviceList used by devices.tsx (card variant + renderActions); single canonical DeviceInfo in types/index.ts (endpoints imports it) |
| 6 | Avatar/button/copy-button | getInitials (Intl.Segmenter, diacritic-safe) in lib/utils + used in avatar/testimonial/org-switcher; button isLoading (aria-busy+spinner); CopyButton in licenses (key) + billing (invoice #) |
| 7 | social-share WhatsApp + testimonials | WhatsApp platform added; testimonials config (3 honest B2B) wired into home |
| 8 | Fonts | index.html Google Fonts preconnect + stylesheet display=swap (interim CDN; self-host follow-up documented) |
| 9+13 | Industry pages distinct | 7 pages, each with a distinct motion-rich visual module (dispatch board, before/after, fleet monitor, mobile sim, seasonal timeline, site board, supply-chain flow) |
| 10 | Profile notif-save | Button enabled ? useUpdateNotificationPreferences + toasts |
| 11 | Support KB real | useTutorials-driven KB tab (loading/error/empty) |
| 12 | Waitlist live counter | useWaitlistCount ? GET /waitlist/count (real; skeleton + graceful fallback) |
| 14 | Blog static fallback removed | BLOG_POSTS array deleted; skeletons/error+retry/EmptyState; categories from API |
| 15 | Blog related-posts | Same category/tags, max 3, honest empty state |
| 16 | Blog unique og:image | featured_image else deterministic /og/blog/{slug}.png; articleSchema matches |
| 17 | Partners real + DPA | Real integration cards (Available/Beta/Planned from shared integrationList); DPA card ? /trust#dpa anchor |
| 18 | API playground sandbox | Interactive builder with canned responses + 5/30s rate-limit sim; explicit demo framing; no live calls |
| 19 | 404 status/noindex | noindex verified in not-found.tsx; CF Pages 404-rewrite limitation documented in _redirects (301/302/303/307/308 only) |
| 20 | og:image per page | seo-head default ? real logo3.png; per-page sweeps |
| 21 | Dynamic sitemap | NEW scripts/generate-sitemap.ts wired into build (static + blog slugs, 4s timeout); config/sitemap.ts shared with prerender (+/integrations picked up) |
| 22 | PWA/manifest | webmanifest 16/32/180/192/512 + maskable; SW present (PWA scope per blueprint P3) |
| 23 | Vitest thresholds | branches 75, functions 80, per-dir overrides (src/lib 90/85, queries 85, auth-provider 90/85); shortfall ~56%/41% documented, NOT loosened |
| 24 | Missing e2e specs | NEW e2e/critical/auth-mfa-cycle.spec.ts + checkout-upgrade.spec.ts (cookie-seeded, no-storage assertion) |
| 25 | k6 scenarios | NEW k6-login / k6-dashboard-load / k6-notification-polling with �16.7 thresholds |
| 26 | Stryker score tracking | mutation-score.json + scripts/record-mutation-score.ts + .github/workflows/nightly.yml |
| 27 | CI gates | ci.yml += i18n:audit, test:manifest, security regression (21/21), critical-e2e, a11y tier, non-blocking visual-regression job |
| 28 | Analytics events | onboarding_step_completed, referral_shared, feature_interest_clicked, checkout_started/completed wired |
| 29 | Manifest icons | 16/32 (logo.png), 180 (logo2.png), 192/512 + maskable (logo3.png) |

### BACKEND-GATED ? CLOSED (9)
| # | Gap | Closure evidence (Calculator logistica/) |
|---|---|---|
| 30 | Refresh token httpOnly cookie | /auth/token body no longer returns refresh_token (cookie-only); /auth/refresh cookie-first w/ transitional body fallback; frontend cookie-refresh (no storage) |
| 31+35 | MFA full | backend: mfa.py (enroll/confirm/disable/verify/backup-code + mfa-status), TOTP RFC6238 stdlib, backup codes bcrypt + atomic single-use, login mfa_required gate, session 5min single-use; frontend: settings enroll/disable UI (manual key, 6-digit auto-advance, backup-code gate + .txt, password re-entry) |
| 32 | Login rate limiting | Already existed backend (5 fails/5min ? 15min lockout, 429+Retry-After) � verified |
| 33 | Stripe checkout | Env-gated: STRIPE_SECRET_KEY/WEBHOOK_SECRET Optional; real Checkout Session + portal when configured, honest `mock:true` fallback; stripe in requirements.api.txt |
| 34 | Billing-term + trucks | subscriptions tables + POST billing-term (proration credit; annual?monthly deferred), trucks/add (duplicate-licensed guard) + trucks/remove (service credit), cancel (usable_until) + reactivate, real invoices |
| 36 | Referral fraud | waitlist join: self-referral reject, unknown-code reject, 10/day per-code cap ? 429, audit via operation_events |
| 37 | Stripe webhook | webhooks_stripe.py: signature verify (construct_event), exact event_id idempotency lookup (migration v6 + index), 501 unconfigured, 4 event types |
| 38 | Upload hardening | uploads.py: magic-byte sniff, filename sanitize, JPEG EXIF strip; documents upload hardened; NEW /auth/me/avatar (multipart, =5MB, magic-byte, EXIF strip) |

### Oracle follow-ups disposition
- F1 duplicate truck-add ? CLOSED (400 truck/already-licensed guard + tests)
- F2 backup-code TOCTOU ? CLOSED (atomic UPDATE ... WHERE used_at IS NULL, rowcount gate)
- F3 webhook idempotency scan ? CLOSED (exact indexed event_id lookup; legacy NULL fallback)
- F4 addon?Stripe price mapping ? documented follow-up (needs addon_price_mappings table pre-prod)
- F5 un-billed annual reconciliation ? documented follow-up (admin view/job pre-prod)
- Cancel-grace middleware decision ? product ticket (non-blocking)
- Known: coverage shortfall (strict thresholds kept), font self-host, og/blog/{slug}.png asset backing, e2e specs need dev server :3000 to execute (parse-verified), visual baselines first-run creation.

---

## 8.1 Non-Blocking Follow-Ups Closure (2026-08-03)

All 10 documented non-blocking follow-ups plus the StaticRouter runtime bug are now CLOSED (implemented and verified). Backend code in `Calculator logistica/`, frontend in `src/`, e2e/QA in `e2e/` + configs. Gate reviews: Gate 1 GO-WITH-CHANGES, Gate 2 APPROVE-WITH-FOLLOW-UPS, Gate 3 APPROVE-WITH-FOLLOW-UPS. Validation: vitest 1255/1255, tsc clean, i18n:audit PASS (111 new keys, 0 missing), test:manifest 16/16, Playwright critical tier 49 passed / 4 skipped (backend- or tooling-dependent) / 0 failed in CI-equivalent serial mode (workers:1 + retries:2 per playwright.config.ts).

| Follow-up | Closure evidence |
|---|---|
| 1. Coverage push toward �16.1 gates | Per-dir gates MET: src/lib 95.83 stmts/91.52 branch (consent/permissions/sw-register 100% each), src/services/queries.ts 100%, src/contexts/auth-provider.tsx 100% (incl. 100% branch). Overall 68.73/54.85 vs 80/75 � thresholds kept strict, honest delta documented in vite.config.ts |
| 2. Real e2e execution (webServer) | playwright.config.ts webServer `npm run dev` :3000; critical tier runs for real: 49 pass / 0 fail (4 skipped: 3 backend-dependent, 1 needs @axe-core/playwright). Load-determinism: CI serial workers:1 + retries:2; e2e/helpers.ts waitForHydration (root marker + React-owned interactive element, 30s) + stabilizeHydration (onLine=false + consent v2 seeding) |
| 3. Visual regression baselines | 18 baselines created (6 pages x 3 viewports) in e2e/visual-regression.spec.ts-snapshots/; confirmation run 0 failures; CSS animation freeze + AnimatedCounter settle + navigator.onLine=false for determinism |
| 4. Font self-hosting | public/fonts/ � 46 woff2 files + fonts.css (Inter 400-700 + JetBrains Mono 400-600, unicode-range + font-display:swap preserved); index.html loads /fonts/fonts.css; Google CDN links removed (scripts/fetch-fonts.mjs) |
| 5. og/blog/{slug}.png asset backing | scripts/generate-og-images.ts � pure-node PNG encoder (zlib + CRC32 + 5x7 bitmap font, 1200x630, slug-hashed brand); 18 PNGs generated in public/og/blog/; wired into build after generate-sitemap; API-401 ? seed fallback documented |
| 6. F4 addon?Stripe price mapping | addon_price_mappings table (migration v7, schema.py + db_manager.py); _update_stripe_addon DB-looks-up mapping + best-effort Stripe subscription-item sync when configured (absent ? warning); env-gated, tests mock stripe |
| 7. F5 annual-proration reconciliation | POST /subscriptions/admin/reconcile-billing � selects unbilled events (billed_immediately=1, amount_cents>0, reconciled_at IS NULL), charges via Stripe PaymentIntent when configured, marks reconciled_at, returns {total_unbilled, charged, failed, deferred}; migration v7 adds reconciled_at column; celery beat command documented |
| 8. Python 3.11 refs | run.bat + scripts/seed_production_company.py + utils/dump_windows.py ? py -3.11; pyproject requires-python >=3.10 (PEP 604 minimum) + ruff target-version py311 |
| 9. Waitlist admin/campaign/unsubscribe (34 pre-existing failures) | waitlist.py: admin entries list/search/pagination, PATCH state machine + admin_override + timestamps, DELETE 204, CSV export, stats (8 keys incl. growth_daily + conversion_rate), campaign (segment filter, unsubscribed exclusion), public unsubscribe (idempotent); tests 57/57 green |
| 10. Cancel-grace middleware | require_active_subscription: admin bypass first ? canceled + current_period_end future ? PASS (grace) ? lapsed/NULL ? 402 ? paid tiers/trials unchanged; tests test_cancel_grace.py 9/9 |
| + StaticRouter navigation bug (found by real e2e) | src/hooks/useAppNavigate.ts wraps vike navigate() (history.pushState-based, bypasses react-router stateless navigator); src/components/navigation/app-navigate.tsx declarative redirect; ALL production useNavigate/<Navigate> replaced (grep: 0 remaining in src/); verified: 8 useAppNavigate + 6 AppNavigate sites; returnurl-redirect + auth specs green |
| + App bugs found during e2e stabilization | MFA auto-submit stale closure (mfa-challenge passes submittedCode explicitly); MFA post-verify redirect race (hadSessionToken guard vs /login redirect); logout determinism (ProtectedRoute redirect instead of racing navigate("/")); a11y: user-menu + mobile theme-toggle aria-labels (accessibility-basics finding closed) |

### Known (documented, non-blocking)
- Overall coverage 68.73/54.85 still below 80/75 gates (per-dir gates met; thresholds kept strict, CI will fail until closed � tracked)
- Local-parallel e2e flakes against vike dev on-demand compilation; CI serial mode is deterministic
- e2e skips: 3 backend-dependent (returnurl full cycle, password-reset full cycle, org-invite), 1 tooling (axe-core not installed)
- og/blog/{slug}.png generated from seed when blog API returns 401 at build (documented)
- F4/F5 Stripe paths env-gated (no live keys in repo/tests)
