# Operion Website — Production Readiness Audit Report

**Audit date:** 2026-08-01
**Target:** Vite/React/TypeScript SPA (Vike) at repo root — marketing, billing/commerce, support, waitlist — deployed to Cloudflare Pages
**Method:** Static code audit of all 8 priority checks + 6 standard categories; live header checks against `operion.com` and `api.operionerp.xyz`; `npm audit` run against the lockfile; test inventory of `src/__tests__` and `e2e/`.
**Scope note:** The backend (`api.operionerp.xyz`, code in `Calculator logistica/`) is external to this repo. Anything requiring server-side verification is marked **UNVERIFIED** rather than assumed correct.

---

## 1. Executive Verdict

### ❌ **NO — not ready for a public launch that processes real signups and real payments.**

**Single biggest reason:** Billing correctness is the one system the launch depends on (real money, real trial dates), and it is the least verified part of the stack: the frontend has **zero** trial-expiry enforcement or even client-side rendering logic for expired/locked states, **zero** tests for trial expiry, proration, or locked/canceled states, and the only test file touching the subscription page asserts rendering, not money logic. Per the audit rule ("treat every unverified claim as false until proven true"), the trial-expiry behavior — which the audit prompt explicitly says to verify fail-gracefully vs. fail-open — cannot be proven from this codebase.

Compounding: the site ships with a critical auth-token exposure path (JS-readable refresh tokens), a public security page that claims MFA is **"Active"** while the settings UI says it's **"coming in a future update"**, the audit-mandated waitlist analytics events are **zero-wired** (all 9 CTA surfaces + both waitlist lifecycle events untracked), and CSP exists only as a meta tag — absent from `_headers`.

---

## 2. Critical Blockers

Numbered, with evidence and real-world consequence.

**B1. Trial-expiry behavior is unverifiable and untested — billing can silently fail open.**
- Evidence: `src/types/index.ts:94` defines `SubscriptionStatus = "trialing" | "active" | "past_due" | ... | "locked"`, but the only client usage of `trial_ends_at` is a date **display** (`src/pages/dashboard/subscription.tsx:381-384`). `src/lib/permissions.ts` contains role permissions only — no subscription/trial check anywhere in the app. No test exists for `trialing → locked` transition, `trial_ends_at` in the past, or proration (`src/__tests__/integration/pages/dashboard/subscription-v2.test.tsx` asserts rendering only; no billing/proration test file exists in `src/__tests__`).
- Consequence: if the backend does not enforce trial expiry on protected endpoints, an expired trial keeps full access indefinitely. If it does, expired users get an API 403 with no graceful frontend state. Either way, the launch-critical behavior is a black box. **Launch blocker.**

**B2. Auth refresh tokens remain JavaScript-readable — XSS → session takeover.**
- Evidence: refresh token written to `sessionStorage` at `src/contexts/auth-provider.tsx:93,136,158,189` and read back with a **legacy `localStorage` fallback** at `auth-provider.tsx:72-74`. Access token is in-memory only (`src/api/client.ts:20-24` — good), but the refresh token is a long-lived credential readable by any XSS. No httpOnly cookie migration exists anywhere in the repo (only a CSRF cookie is read, `client.ts:49-51`).
- Consequence: exactly the critical XSS-exposure scenario the audit prompt warns about — any XSS on any page yields a valid refresh token. **Launch blocker per priority check #1** (the prompt's interim step — sessionStorage — is only partially done: legacy localStorage tokens are still read).

**B3. Public security page overstates security: MFA marked "Active" while MFA enrollment does not exist.**
- Evidence: `src/i18n/locales/en.json:1134` `security.statusActive: "Active"` rendered for the MFA row of the public security features table (`src/pages/public/security.tsx:152-153`). Meanwhile the in-product UI is disabled: `src/pages/dashboard/settings.tsx:303-333` ("Enable 2FA" button `disabled` with tooltip `settings.twoFactorComingInUpdate` = "Coming in a future update", `en.json:1281`), and profile says "will be available in a future update" (`en.json:1207`). TOTP challenge-on-login exists (`auth-provider.tsx:126-132,182-207`), but users cannot enroll.
- Consequence: prospective customers are told MFA is live when it is not — a trust and legal (misrepresentation) problem the audit prompt flags explicitly. Also a rate-limit gap: MFA verify is a plain POST (`src/api/endpoints.ts:82-83`) with no client throttle — brute-force protection is server-side only (**UNVERIFIED**).

**B4. CSP is not in production response headers — only a permissive meta tag.**
- Evidence: `public/_headers` (8 headers) contains **no Content-Security-Policy**. The only CSP is `<meta http-equiv="Content-Security-Policy">` in `index.html:5` with `style-src 'self' 'unsafe-inline'`, `script-src 'self' https://www.googletagmanager.com` (third-party script injection vector), and `frame-ancestors 'none'` — a directive **ignored by browsers in meta tags** (only honored via HTTP header). Live check: `operion.com` returned **no response** (HTTP status 000) during this audit — production headers could not be confirmed because the production domain does not respond. `api.operionerp.xyz` does respond and does carry a CSP (but it whitelists `http://localhost:*` in `connect-src` — backend hygiene issue).
- Consequence: no real CSP protection against XSS/injection in production; the audit requirement "confirm CSP is present in production response headers" fails. **Launch blocker per priority check #2.**

**B5. Waitlist analytics: zero events wired — the audit's priority check #8 fails outright.**
- Evidence: `trackCTAClick`, `trackEvent`, `trackPageView` all defined in `src/services/analytics.ts:27-153` but **never called from any CTA**. All 9 waitlist CTA surfaces (home hero `home.tsx:151`, home waitlist section `home.tsx:693`, navbar desktop/mobile `app-shell.tsx:582,701`, ROI calculator `roi-calculator.tsx:460`, route demo `route-demo.tsx:317`, blog `blog-article.tsx:1769`, downloads `downloads.tsx:48`) have no tracking call. Blueprint-specified events `waitlist_view`, `waitlist_submit_attempt`, `waitlist_submit_success`, `waitlist_cta_click` (`Operion_Waitlist_Blueprint_V1.md:198-206`) are **not implemented**. No double-firing risk (nothing fires at all); silent-failure risk is moot. Consent gating also broken: `analytics.ts` functions don't check `src/lib/consent.ts` state before firing (only `trackError` claims to, and its check is gtag-presence, not consent — `analytics.ts:145`).
- Consequence: waitlist funnel is unmeasurable at launch; GDPR/consent architecture is decorative. **Blocker for the waitlist/marketing phase.**

**B6. Contact form is a no-op stub that lies to users.**
- Evidence: `src/pages/public/contact.tsx:50-55` — `onSubmit` only shows a success toast and resets the form. `// TODO: Implement backend endpoint`. Turnstile token captured (`contact.tsx:31`) and discarded. No `/api/v1/contact` endpoint exists in `src/api/endpoints.ts`.
- Consequence: a customer's support request is silently deleted and they receive a false "message sent" confirmation — on the front door of a company that will hold customers' fleet data. Also a privacy-policy mismatch (data "collected" per policy, never transmitted).

**B7. Split positioning is live across locales: "AI Logistics OS" (EN only) vs "All-in-One ERP"/"Enterprise Logistics, Simplified" (5 locales).**
- Evidence: EN hero title `en.json:268` = "The Complete Logistics Operating System, Powered by AI" with badge `en.json:295` = "All-in-One Logistics ERP" — the two competing claims coexist **in the same hero**. All other locales use the legacy tagline: DE "Unternehmenslogistik, vereinfacht", RO "Logistică Enterprise, Simplificată", ES/FR/PL equivalents (`de.json:1255`, `ro.json:1255`, `es.json:1255`, `fr.json:1255`, `pl.json:1255`). CTA destinations are inconsistent: hero CTA "See the AI in Action" → `/waitlist` (a waitlist, not a demo); "Watch the Demo" → `/roadmap`.
- Consequence: the previously-flagged positioning conflict is not resolved; it is replicated. Trust and conversion problem at launch.

**B8. No CI/CD and no verifiable staging — and the production site does not respond.**
- Evidence: no `.github/workflows/`, no `wrangler.toml`, no Pages config in repo. `operion.com` returned status 000 (no connection) at audit time; only the API host responds. Deployment path is opaque (dashboard-managed).
- Consequence: no preview/staging verification loop, no audit trail for what shipped. The audit requirement "is there a staging environment / preview deploy process" is answered NO/UNVERIFIED. **Blocker before any paid launch.**

**B9. Dependency vulnerabilities: 3 HIGH, direct in the HTTP layer.**
- Evidence: `npm audit --omit=dev` (run 2026-08-01): **axios ^1.7.9** — HIGH, 28 advisories incl. SSRF/credential leakage/prototype-pollution/CRLF/DoS (fixed in 1.18.0); **postcss ≤8.5.17** — HIGH, path traversal via sourceMappingURL; **react-router 7.18.1** — HIGH, RSC-mode CSRF bypass (GHSA-qwww-vcr4-c8h2, fixed in 8.3.0 — a major bump).
- Consequence: axios is the app's entire HTTP layer (auth, billing, waitlist) — SSRF/credential-leak vectors are directly relevant to a site that will hold payment-adjacent and fleet data.

---

## 3. Findings Table

| # | Category | Severity | Description | Evidence | Recommended Fix |
|---|----------|----------|-------------|----------|-----------------|
| F1 | Billing | 🔴 Critical | Trial-expiry behavior unverifiable/untested; zero frontend entitlement logic; zero billing tests | `subscription.tsx:381-384`, `permissions.ts`, `subscription-v2.test.tsx` | Verify backend enforcement; add client state handling for `locked`/`past_due`; add expiry/proration tests; document expected trial-expiry contract |
| F2 | Auth | 🔴 Critical | Refresh token JS-readable (sessionStorage + legacy localStorage fallback read) | `auth-provider.tsx:72-74,93`, `client.ts:20-24` | Complete httpOnly/Secure/SameSite cookie migration; delete localStorage fallback read |
| F3 | Trust/Security | 🔴 Critical | MFA "Active" badge on public page while enrollment is disabled/"coming in future update" | `security.tsx:152-153`, `en.json:1134,1207,1281`, `settings.tsx:303-333` | Ship MFA enrollment (or) change badge to match reality; add rate-limit on MFA verify (server) |
| F4 | Security | 🔴 Critical | No CSP in `_headers`; meta CSP has `unsafe-inline`, GTM script source, ineffective `frame-ancestors`; prod site unreachable so headers unverified | `public/_headers`, `index.html:5` | Add CSP (with nonce/hash policy) to `_headers`; remove `unsafe-inline`; enforce via header not meta; verify live after deploy |
| F5 | Analytics | 🔴 Critical | Waitlist events never wired (0/9 CTA surfaces); consent not enforced in trackers | `analytics.ts:27-153`, `home.tsx:151,693`, `app-shell.tsx:582,701` | Wire `trackCTAClick`/lifecycle events per blueprint; gate all trackers on consent state |
| F6 | Functionality | 🔴 Critical | Contact form is a stub — success toast, no send | `contact.tsx:50-55` | Implement backend endpoint; wire Turnstile token; test |
| F7 | Positioning | 🟠 High | Split positioning live (EN "AI OS" vs 5 locales "Enterprise ERP"); hero badge contradicts title; CTA targets mismatch | `en.json:268,295`, `de.json:1255` + 4 more | Unify copy across all locales; align CTA label→destination |
| F8 | Security | 🟠 High | 3 HIGH prod vulnerabilities (axios 28 CVEs, postcss, react-router CSRF) | `npm audit` 2026-08-01 | Upgrade axios ≥1.18.0; patch postcss; plan react-router 8 migration |
| F9 | Architecture | 🟠 High | Dual team model: frontend Organization type is "FRONTEND-ONLY" placeholder; backend has only `users.company_id`; billing tied to `company_id`, not org role; org endpoints may not exist server-side | `types/index.ts:383-423`, `endpoints.ts:102-105,325-334`, `subscription.ts:627-661` | Confirm Organizations API exists on backend; route invites/seats/billing ownership through it; delete or gate legacy `companyApi` |
| F10 | Architecture | 🟠 High | `fleetApi` (fleet/GPS endpoints) defined in website client — dormant but violates the boundary constraint if ever wired | `endpoints.ts:706-740`, `queries.ts:716-739` (0 usages in pages) | Delete dormant fleetApi/hooks from the website client; keep boundary explicit |
| F11 | Compliance | 🟠 High | AI Payment Leniency UI is live-but-disabled (visible toggle + legal note); `payment_deferred_until` displayed; e-Factura/ANAF/SPV: zero occurrences — **nothing shipped** ✅ | `subscription.tsx:552-585,618-622` | Keep gated until legal sign-off; remove or gate the UI shell until then (currently fine, watch it) |
| F12 | Compliance | 🟠 High | Privacy/cookie policy mismatches implementation: Turnstile (Cloudflare) undisclosed; Google not named as third party despite `_ga/_gid/_gat`; `api.operionerp.xyz` undisclosed; retention "to be defined at launch" | `cookie-policy.tsx:14-22`, `consent.ts:7`, `privacy.tsx:2297-2300` | Update policy: name Turnstile/Google/API; finalize retention; reconcile contact-form data claim |
| F13 | Accessibility | 🟠 High | Brand color contrast failure: `#6366F1` (light `--primary`) on white ≈ **4.47:1** — marginally below AA 4.5:1 for normal text; dark-mode primary `#818CF8` on white ≈ **2.98:1** — fails even large-text 3:1. White-on-primary buttons fail | `globals.css:53-54,92-93`, `button.tsx:11`, `waitlist.tsx:169` | Darken primary (e.g. `#4F46E5` = 5.1:1) or add darkened foreground for primary backgrounds |
| F14 | Performance | 🟡 Medium | Inline GA config blocks first paint; ~415 KB of logo PNGs in head (173.8+138.8+102.3 KB); no route-level code splitting; fully static SPA but all JS in one bundle | `index.html:113-139`, `public/logo*.png`, `site.ts:6` | Async/defer GA; compress logos (WebP/SVG); lazy-load non-critical routes |
| F15 | Security | 🟡 Medium | Bot protection uneven: waitlist ✅ (Turnstile+honeypot+backend token), register ✅ (Turnstile), contact ❌ (widget but token discarded), newsletter ❌ (no Turnstile — also a stub), login ❌ (relies on server 429) | `waitlist.tsx:111,129-138`, `register.tsx:41,65`, `contact.tsx:31,52`, `newsletter.tsx:18-29` | Wire Turnstile validation server-side on all public endpoints; fix contact/newsletter |
| F16 | Security | 🟡 Medium | No repo-based deployment pipeline; no IaC; prod domain unreachable at audit time | repo: no workflows/wrangler; live check status 000 | Add GitHub Actions → Pages preview/staging; verify DNS/deploy |
| F17 | Security | 🟡 Medium | No httpOnly cookie migration (only CSRF cookie read); i18n copy claims "tokens not persisted to storage" — inaccurate | `client.ts:49-51`, `en.json:1126` | Fix marketing copy; complete cookie migration |
| F18 | Testing | 🟡 Medium | Billing test coverage ~0: only render tests; no trial/proration/locked-state tests; e2e covers navigation only | `subscription-v2.test.tsx`, `e2e/public-navigation.spec.ts:31-42` | Add unit + e2e for trial expiry, proration, entitlement states |
| F19 | UX | 🟡 Low | `pending_truck_count` display compares against current licensed count — pending-change banner won't show when values equal | `subscription.tsx:479-484` | Compare against previous value / explicit pending flag |
| F20 | A11y | 🟡 Low | Skip-link uses `focus:outline-none` without full replacement; minor | `accessibility.tsx:28` | Ensure visible focus ring on skip link |
| F21 | Security | ✅ Low | No hardcoded secrets/keys in bundle; open-redirect guard in global search is solid | `env.ts`, `site.ts:19-21`, `global-search.tsx:230-236` | None (verify VITE_ vars injected at build, not committed) |

---

## 4. What's Actually Solid

Genuinely well-built, with evidence:

1. **Auth expiry/refresh flow — no fail-open found.** `verifyJwt` (`src/services/jwt.ts:18-37`) is UI-gating only; the 401 interceptor (`src/api/client.ts:80-146`) handles refresh, and every failure path — no refresh token, failed refresh, network error — correctly clears state and redirects to `/login`. `isAuthenticated` derives from a server-validated user object (`auth-provider.tsx:228`). This is the correct design and was traced end-to-end.

2. **Payment data hygiene.** Zero occurrences of card number/CVC/expiry anywhere in `src/` + `public/`. Checkout is a Stripe hosted redirect (`src/components/shared/stripe-checkout.tsx:28-30`, `createCheckoutSession`); only publishable key + customer/subscription IDs are client-visible. Pricing math is display-only; truck count and totals are server-authoritative (`subscription.tsx:268-275` uses `licensed_truck_count` from the server). No client-side price manipulation path exists.

3. **Waitlist form flow.** Zod validation, honeypot (`waitlist.tsx:129`), Turnstile with token sent to backend (`waitlist.tsx:138`), graceful 409/429 handling (`waitlist.tsx:139-149`), referral code + WhatsApp share success state. MSW mocks are confined to tests (`__tests__/setup.ts:7`); nothing mock can leak into production.

4. **Client-side input validation is comprehensive** — zod schemas on register, waitlist, contact, login. `dangerouslySetInnerHTML` usage is restricted to hardcoded/static content (blog articles, docs, tutorials) and a sanitizing markdown-ish transformer (`docs-article.tsx:49-53`) — no user-controlled HTML.

5. **No secrets in the bundle.** All config via `import.meta.env.VITE_*` (`src/config/env.ts`, `site.ts`); `.env` contains only comments. The `global-search.tsx:230-236` open-redirect guard is a nice defensive touch.

6. **Product boundary: no live violation.** `fleetApi` endpoints exist but are **dormant** — zero usages in any page (`queries.ts:716-739` unused). The dashboard contains no telematics/GPS widgets. Route demo is a marketing calculator, not fleet ops.

7. **e-Factura/compliance: nothing shipped.** Zero occurrences of e-Factura/ANAF/SPV in code; AI Payment Leniency is a disabled, non-functional shell with an explicit legal note and "Coming Soon" callout. Passes priority check #7 as-is (must stay gated).

8. **Baseline headers present in `_headers`** — `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, HSTS (preload, 2y), Referrer-Policy, Permissions-Policy, COOP, CORP. Only CSP is missing.

9. **Email provider abstraction is provider-agnostic** — `EmailProvider` interface + swappable `ResendProvider`/`LoggingEmailProvider` (backend, `Calculator logistica/backend/services/email_provider.py:16-101`). Lives outside this repo, but the design constraint is satisfied there.

10. **The project typechecks cleanly** — `npm run typecheck` (`tsc --noEmit`, strict mode) exits with zero errors across `src/` and `pages/`, including the test suite. Editor LSP warnings in some test files do not reproduce in the compiler. The test suite itself is runnable via vitest (schemas, roles, i18n, config, UI components are covered).

---

## 5. Prioritized Remediation Roadmap

### Phase 0 — Before the waitlist/marketing phase goes live
1. **F5** Wire waitlist analytics events (`waitlist_view`, `waitlist_cta_click` ×3 CTA surfaces, `waitlist_submit_success`) per `Operion_Waitlist_Blueprint_V1.md:198-206`; gate all trackers on consent (`consent.ts`).
2. **F6** Implement the contact form backend endpoint (or remove the form + Turnstile until real) — a fake success toast is a launch blocker for trust.
3. **F2** Complete token migration: stop reading localStorage refresh tokens; move to httpOnly cookies (or at minimum remove the localStorage fallback and clear legacy keys).
4. **F4** Ship real CSP via `_headers` (no `unsafe-inline`; use nonces or hashes); keep `frame-ancestors`/`X-Frame-Options` aligned.
5. **F3** Fix the MFA messaging mismatch — badge must not say "Active" until enrollment ships.
6. **F7** Unify hero positioning copy across all 6 locales; fix CTA label→destination mismatches.
7. **F12** Update privacy/cookie policy: name Turnstile, Google Analytics, and the API backend; finalize retention wording.

### Phase 1 — Before the September 2026 public launch
8. **F1/B1** Verify backend trial-expiry enforcement end-to-end; add client handling for `locked`/`past_due`; add unit + e2e tests for trial expiry, proration, and truck-count changes.
9. **F9** Resolve org model: confirm the Organizations API exists server-side and route invites/seats/billing ownership through it — or officially declare the single-company model canonical and remove the placeholder org layer.
10. **F8** Upgrade axios (≥1.18.0) and postcss; plan the react-router 8 migration (CSRF advisory).
11. **F13** Fix brand-color contrast (darken primary to ≥4.5:1 against white; audit all `bg-primary` + `text-primary-foreground` uses).
12. **F10** Delete dormant fleetApi/hooks from the website client (boundary hygiene).
13. **B8** Stand up GitHub Actions → Cloudflare Pages preview/staging; confirm the production domain resolves and carries headers; document the deploy process.
14. **F15** Wire server-side Turnstile validation on all public endpoints (contact, newsletter), and consider Turnstile on login.
15. **F11** Decide AI Payment Leniency: keep gated until legal/accounting sign-off; ideally remove the visible disabled shell until then.

### Phase 2 — Can wait post-launch
16. **F14** Performance: defer GA, compress logo assets, route-level code splitting.
17. **F19** Fix `pending_truck_count` display comparison.
18. **F20** Skip-link focus ring.
19. **F17** Fix the i18n token-storage copy ("not persisted to storage" is inaccurate today).
20. **F16** Broader IaC (wrangler config in repo, environment parity).

---

## 6. Verdict by Category

| Category | Verdict |
|----------|---------|
| Security (headers, secrets, validation) | ⚠️ Needs Work — CSP missing from headers; tokens JS-readable; deps vulnerable; no secrets leaked; validation solid |
| Auth (tokens, refresh, MFA) | ⚠️ Needs Work — refresh/expiry solid, no fail-open; MFA overclaimed; storage migration incomplete |
| Billing correctness | ❌ Not Ready — untested trial/proration behavior; payment delegation excellent |
| Organizations/team model | ⚠️ Needs Work — dual model; org API existence unverified |
| Product boundary | ✅ Ready — dormant fleet code only, nothing wired |
| e-Factura/compliance | ✅ Ready — nothing shipped; keep leniency gated |
| Waitlist | ⚠️ Needs Work — flow solid; analytics entirely missing |
| Legal content | ❌ Not Ready — policy/code mismatches; contact form collects nothing |
| Performance | ⚠️ Needs Work — static-first ✅, but blocking GA + heavy logos + no code splitting |
| Accessibility | ⚠️ Needs Work — labels/headings ✅; brand-color contrast fails AA |
| Positioning/UX | ❌ Not Ready — split positioning live in 5 locales |
| Testing & deployment | ❌ Not Ready — zero billing tests; no CI/staging; prod unreachable |
