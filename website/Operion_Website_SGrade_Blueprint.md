# 🏆 OPERION WEBSITE S-GRADE OVERHAUL BLUEPRINT — v2 (COMPLETE COVERAGE)

> Prepared for: Gigi Bomba / Cargo Dyvagri SRL
> Scope: `operion-website` repo — every route, every shared component, every layer of the stack
> Target: Public launch ~Sept 1 — sections flagged 🔴P0/🟠P1 target that date, 🟡P2/🟢P3 are post-launch
> Execution model: Prescriptive spec for AI coding agents, verification-gated, failing→passing tests required before any item is marked done

This version supersedes the first pass. It walks the spec dump **section by section, page by page, component by component** so nothing is left un-audited. Where the first blueprint already covered something in depth, it's kept but cross-referenced rather than repeated at length; where the first pass was thin (i18n, admin pages, the full public page catalog, error/edge pages, component-level audits, environment/deployment), this version goes deep.

---

## 0. HOW TO USE THIS DOCUMENT

Feed one section to your coding agent at a time, in Section 21's priority order. Every block has: **current state → target state → implementation spec → verification checklist**. Never accept "done" without pasted-back proof (test output, screenshot, curl/response body) — this is the pattern already working for you elsewhere in this project and it does not get relaxed here.

**Grading rubric (unchanged from v1, restated for reference):**

| Grade | Meaning |
|---|---|
| F | Visual stub, no logic |
| D | UI + mock data, no persistence |
| C | Real, but functional/UX/security gaps |
| B | Correct, lacks polish/edge cases/tests |
| A | Correct, tested, accessible, polished |
| **S** | A + memorable, differentiated, reduces support burden by design |

---

## 1. THE ONE RULE THAT GOVERNS EVERYTHING ELSE

> A disabled button, a "Coming Soon" badge on a paid feature, or mock data presented as real is worse than not showing the feature at all.

Every item graded D or F below gets one of three explicit dispositions — never left ambiguous:

1. **BUILD** — full implementation, backend included, pre-launch.
2. **HONEST DEFER** — removed from primary UI, replaced by the shared `<RoadmapFeature>` component (spec in §6.9) showing what it will do, a real target quarter (or "under evaluation"), and a "notify me" capture.
3. **REMOVE** — delete dead UI outright.

Do this triage pass across the entire file-level map (§20) **before** writing code, so effort isn't spent polishing things that get deleted next week.

---

## 2. ARCHITECTURE, PROVIDERS & APP SHELL (Spec §3–4)

### 2.1 Provider stack — audit each layer

| Provider | Current | Technical fix |
|---|---|---|
| `ErrorBoundary` (react-error-boundary) | Generic "Something went wrong" + Try Again | Add Sentry (or equivalent) `onError` hook to actually report the error with component stack + user id (if authed) — a silent boundary that never notifies anyone in prod is a monitoring gap, not just a UX one. Add a "Report this issue" secondary action that pre-fills a Support ticket (you already have a working Support API) with the error digest attached. |
| `QueryClientProvider` | `staleTime: 5min, retry: 1, refetchOnWindowFocus: false` globally | Move to **per-query overrides**: static content (blog, changelog, docs) → `staleTime: 30min`; volatile data (devices, sessions, notifications) → `staleTime: 30s–60s` (fixes the flagged "no staleTime on useDevices" gap in one pass, §4 of v1). Add a global `onError` handler in `QueryCache`/`MutationCache` config that pipes failures into your toast system automatically instead of requiring every hook consumer to handle it manually — reduces the "missing toast feedback" gaps flagged across Devices/Licenses. |
| `ThemeProvider` | light/dark/system, `.dark`/`.light` class, `localStorage` | No functional gap. Add only: a `<meta name="color-scheme">` tag toggle so native form controls (date pickers, scrollbars) also theme correctly — commonly missed. |
| `LocaleProvider` | 6 locales, flat key-value, `t(key)` with fallback-then-raw-key | See §8 (i18n) — this provider's *mechanism* is fine, the *content completeness* behind it is the real gap. |
| `AuthProvider` | See §3 in full | |
| `Toaster` (sonner) | bottom-right, richColors, close button | Add a max-visible-toasts cap (3–4) with queueing — bulk operations (§5's device bulk-deactivate) can otherwise fire 10+ toasts at once and flood the corner. |

### 2.2 Routing (`App.tsx`, 807 lines) — structural fixes

- **Code-split boundary audit**: verify every top-level route is behind `React.lazy` (spec says "yes" but "some pages are large" — meaning the *chunks* are large, not that splitting is missing). Action: run `vite build --mode analyze` (or `rollup-plugin-visualizer`), identify any chunk >150KB gzip, and split further at the *component* level for heavy ones (e.g., if `billing.tsx` pulls in a charting library for usage graphs, dynamic-import the chart component specifically, not just the page).
- **404 / catch-all route (`*`)**: audit that it actually renders a real, on-brand 404 page (see §13.4) and not a generic router fallback.
- **Route-level SEO regression risk**: since routes are lazy-loaded, verify `react-helmet-async` head tags render *before* first paint is measured by crawlers — for pure client-side rendering this is a known SEO risk (crawlers that don't execute JS, or execute it with a timeout, may miss injected meta tags on lazy chunks). If you're not on SSR/prerendering, add **prerendering for the ~50 public marketing pages specifically** (via `vite-plugin-ssr`, `vike`, or a static prerender step in the build for public routes only — dashboard stays CSR since it's behind auth and irrelevant to SEO). This is a bigger lift but is the single highest-leverage SEO technical fix available given your stack, more impactful than any meta-tag tweak in §14.
- **AppShell layout switch** (`isDashboard = pathname.startsWith("/dashboard")`): fragile string-prefix check — fine today, but if you ever add a route like `/dashboard-demo` (marketing) it'll misfire. Switch to an explicit route-config flag (`meta: { layout: 'dashboard' }` per route) rather than a path-prefix heuristic, for correctness as routes grow.

### 2.3 Navigation config (`navigation.ts`, 144 lines)

- `publicNavItems` (9 items + dropdowns), `footerNavSections` (5 columns), `dashboardNavItems` (12 items) — structurally fine. Technical gap: verify **active-route highlighting** correctly handles nested routes (e.g., `/dashboard/organizations/:slug/settings` should still highlight the "Organizations" sidebar item) — a common bug in hand-rolled nav-highlighting logic using exact-match instead of `startsWith`/route-tree matching.
- Add a `badge` field to nav config entries so RBAC-gated items (once §3.4 ships) or "new feature" flags can render a small pill without one-off JSX per item.

---

## 3. AUTHENTICATION & SECURITY — FULL TECHNICAL SPEC

(Expands v1 §2; this is the most safety-critical section, kept maximally detailed.)

### 3.1 Token storage migration (P0)

**Current**: `operion-access-token`, `operion-refresh-token`, `operion-avatar-url`, `operion-locale`, `operion-theme` all in `localStorage`.

**Target end-state**:
- Access token: in-memory only, held in `AuthContext` React state, never serialized to any storage.
- Refresh token: **httpOnly + Secure + SameSite=Strict** cookie, set by backend `Set-Cookie` header on `/auth/token`, `/auth/refresh`, `/registration/register`.
- `axios` instance: `withCredentials: true`, remove the `Authorization` header attachment for the refresh call specifically (browser sends the cookie automatically); keep `Authorization: Bearer <access_token>` from in-memory state for regular API calls.
- On app mount: call `POST /auth/refresh` immediately (cookie sent automatically) to silently obtain a fresh access token — replaces the current "read token from localStorage" bootstrap.
- Avatar URL / locale / theme are **not sensitive** — fine to remain in localStorage, no change needed there.

**Backend contract change required** (file this as a ticket against `api.operionerp.xyz` today, it's the blocking dependency):
```
POST /api/v1/auth/token
Set-Cookie: refresh_token=<jwt>; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth; Max-Age=<seconds>
Response body: { access_token, token_type, expires_in, user }   // no refresh_token in body anymore
```

**Interim mitigation (ship this week, before backend cookie support lands)**:
- Move both tokens from `localStorage` to `sessionStorage` — cuts persistence window to the tab's lifetime, meaningfully shrinks the exfiltration value of a one-off XSS payload.
- Ship the CSP in §3.6 immediately — it's the actual mitigating control while tokens are still JS-readable.
- Track the httpOnly-cookie migration as a dated tech-debt ticket, not an indefinite "later."

### 3.2 CSRF — keep, verify one detail

Double-submit cookie pattern (`csrf_token` cookie → `X-CSRF-Token` header) is correctly designed. Verify explicitly: the CSRF cookie itself must **not** be httpOnly (JS needs to read it to echo it back) but the *refresh token* cookie from §3.1 **must** be httpOnly — these are two different cookies with two different flag requirements; don't let an agent "simplify" by applying the same flags to both.

### 3.3 401 refresh queue — keep as designed

Promise-queue pattern preventing duplicate concurrent refresh calls is correct. One hardening addition: cap retry-after-refresh to **one attempt** (already implied by `_retry` flag) and on a second 401 for the same request, force full logout + redirect rather than looping — verify this terminal condition exists explicitly in the interceptor code, it's an easy infinite-loop trap to introduce accidentally during refactors.

### 3.4 Multi-Factor Authentication — full technical spec

**Backend additions**:
```sql
ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN mfa_secret TEXT;              -- encrypted at rest, not plaintext
CREATE TABLE mfa_backup_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    code_hash TEXT NOT NULL,      -- bcrypt/argon2, never store plaintext
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**New endpoints**:
```
POST /api/v1/auth/mfa/enroll          → generates TOTP secret, returns otpauth:// URI + QR payload
POST /api/v1/auth/mfa/confirm         → { code } → verifies, sets mfa_enabled=true, returns 10 backup codes
POST /api/v1/auth/mfa/disable         → requires password re-entry, sets mfa_enabled=false
POST /api/v1/auth/mfa/verify          → { mfa_session_token, code } → used mid-login
POST /api/v1/auth/mfa/backup-code     → { mfa_session_token, backup_code } → alternate to TOTP code
```

**Login flow change**:
```
POST /auth/token → if mfa_enabled: return { mfa_required: true, mfa_session_token } (short-lived, ~5min, single-use)
                    NOT full access/refresh tokens
Frontend: render MFA challenge screen → POST /auth/mfa/verify → full tokens issued
```

**Frontend spec**:
- Settings → Security tab: replace the "Coming Soon" callout with real enroll flow — QR (use `qrcode` npm package or render server-provided PNG), manual entry key fallback (accessibility — not everyone can scan a QR off the same screen), 6-digit confirm input, backup-codes reveal screen with mandatory "I've saved these" checkbox gating the "Done" button, download-as-.txt option for the codes.
- Login page: conditional second step — same centered-card layout, 6-digit input with auto-advance/auto-submit on 6th digit, "Use a backup code instead" link, "Trouble? Contact support" fallback.
- Disable-MFA flow: require password re-entry (step-up auth) before disabling — never allow disabling MFA from an already-open session with zero friction.

**Verification**: unit tests for TOTP window tolerance (±1 step for clock drift), backup code single-use enforcement, session-token expiry enforcement, and an E2E Playwright flow: enroll → logout → login with TOTP → login with backup code → verify used code rejected on second attempt.

### 3.5 RBAC / Team management — full technical spec

- Canonical model: **Organizations** (already has full CRUD + members + invitations per your API). Company page's "Team" tab and `/dashboard/organizations` are two half-built views of the same concept today — collapse to one.
- `RequireRole` wrapper:
  ```typescript
  function RequireRole({ roles, children }: { roles: UserRole[]; children: ReactNode }) {
    const { user } = useAuth();
    if (!user || !roles.includes(user.role)) return <Navigate to="/dashboard" replace />;
    return <>{children}</>;
  }
  ```
- Apply to: Company → Team management actions (invite/remove/role-change: owner/admin only), Billing/Subscription pages (owner/admin only — a `driver` role should not see or touch billing), Admin routes (already gated, verify `AdminRoute` and `RequireRole` don't conflict/duplicate logic — consolidate to one mechanism).
- Permission matrix (show as a tooltip/modal in the UI, and enforce server-side — **never trust the frontend role check alone**, the backend must independently verify role on every mutating endpoint):

| Action | owner | admin | manager | dispatcher | driver |
|---|---|---|---|---|---|
| View billing | ✅ | ✅ | ❌ | ❌ | ❌ |
| Change subscription | ✅ | ❌ | ❌ | ❌ | ❌ |
| Invite/remove members | ✅ | ✅ | ❌ | ❌ | ❌ |
| Manage devices/licenses | ✅ | ✅ | ✅ | ❌ | ❌ |
| Submit support tickets | ✅ | ✅ | ✅ | ✅ | ✅ |

(Adjust the matrix to your actual business rules — the point is it must be an explicit, documented, server-enforced table, not implicit.)

### 3.6 Security headers / CSP — exact config

```
# Netlify _headers file (or equivalent Cloudflare rule)
/*
  Content-Security-Policy: default-src 'self'; script-src 'self' https://www.googletagmanager.com https://www.google-analytics.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://api.operionerp.xyz https://www.google-analytics.com; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=(self)
  Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
  Cross-Origin-Opener-Policy: same-origin
  Cross-Origin-Resource-Policy: same-site
```
Verify Stripe (once §4 ships) needs its own `script-src`/`frame-src` allowances (`https://js.stripe.com`, `https://checkout.stripe.com`) — add only when that integration lands, don't pre-open the policy speculatively.

**Verification**: securityheaders.com grade A, Mozilla Observatory grade A- or better, paste both reports.

### 3.7 Audit log — schema + surfaced UI

```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    actor_user_id UUID NOT NULL,
    action TEXT NOT NULL,           -- 'login','logout','password_change','mfa_enabled','member_invited','role_changed','device_deactivated','license_transferred', etc.
    target_type TEXT,               -- 'user','device','license','organization'
    target_id UUID,
    metadata JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_log_company_created ON audit_log (company_id, created_at DESC);
```
Frontend: reuse the existing dashboard Activity tab component (currently 5 hardcoded mock events on `/dashboard`), point it at `GET /api/v1/audit-log?company_id=...` with pagination + filter-by-actor/action/date, gate behind `RequireRole roles={['owner','admin']}`.

### 3.8 Rate limiting & brute-force protection (not in original spec dump — genuine gap)

Nothing in your dump mentions login rate limiting. Confirm with backend team it exists (`/auth/token` should be rate-limited per-IP and per-account, e.g. 5 attempts/15min with exponential backoff, plus a CAPTCHA or equivalent after N failures). If it doesn't exist, this is a 🔴 P0 backend ticket — credential-stuffing against an unprotected login endpoint is one of the most common real-world attacks on exactly this kind of B2B login form. Frontend: surface a clear "Too many attempts, try again in X minutes" state rather than a generic error.

### 3.9 Dependency & static analysis pipeline

- `npm audit --audit-level=high` (or Dependabot/Renovate) blocking in CI.
- `eslint-plugin-security` added to the existing Oxlint/ESLint config.
- Extend `tests/security/` (mirroring the pattern from your backend security suite) with: token-storage assertions (no tokens in `localStorage` post-migration), CSP header presence test, RBAC route-guard tests (wrong-role user gets redirected, not shown content even briefly), CSRF header presence on mutating requests.

---

## 4. BILLING, SUBSCRIPTIONS, DOWNLOADS — FULL TECHNICAL SPEC (rewritten to match the real per-truck business model)

This replaces the earlier generic tiered-plan version of this section. The actual model is per-truck, dual-dimensional (billing term × fleet size), and is enforced jointly by the **desktop ERP's Fleet Manager** and the **website's Subscription page** — this is the trickiest architectural wrinkle in the whole blueprint, so it gets full treatment below.

### 4.1 The business model, restated as precise technical requirements

| Component | Price | Billed | Notes |
|---|---|---|---|
| ERP (base) | €10 / active truck / month | Per truck | Mandatory, included for every active truck — all ERP features come with it, no separate module toggles |
| AI Copilot (ARGO) | +€10 / active truck / month | Per truck | Optional — **confirm with Gigi whether this is a company-wide on/off toggle (all trucks billed at €20 once enabled) or a genuinely per-truck selectable add-on.** The source doc's own worked example ("10 trucks, AI enabled, 10 × €20 = €200") reads as a single company-wide flag applied uniformly, not per-truck selection — this blueprint specs it as **company-wide toggle** below, but flag this explicitly as an open decision before building, since it changes both the schema and the desktop-app UI meaningfully. |
| Priority Support | €50 / month flat | Company-wide, not per truck | |
| API Access | €100 / month flat | Company-wide, not per truck | |

- **Two independent dimensions**: billing **term** (monthly/annual) and **fleet size** (truck count) — never coupled in the data model.
- **Monthly**: adding a truck activates it immediately (usable now) with **no charge today**; the new monthly price takes effect at the **next** billing cycle. Removing a truck takes effect at the next cycle; the following invoice is simply lower.
- **Annual**: adding a truck mid-term is prorated and **charged immediately**: `additional_charge = price_per_truck_per_month × remaining_full_months_in_term`. Removing a truck mid-term deactivates it **immediately**, with **no refund** — the unused remaining value becomes a **service credit** on the account, redeemable only against a future truck addition within the same term (this is the specific anti-refund-abuse mechanic described — implement it as a ledger balance, not a discount code).
- Free trial: **14 days, no credit card**, full product access, silent lockout (not an auto-charge) at expiry, with an in-app + email notice **4 days before** expiry.

### 4.2 Desktop ERP ↔ Website integration — the core architectural point

The Fleet Manager (where trucks are actually added) lives in the **desktop PySide6 ERP**, not the website. The website's Subscription page is the billing source of truth. These must share one backend state, not two:

```
Desktop ERP: user clicks "Add Truck" in Fleet Manager
  → if new truck would exceed licensed_truck_count:
        show a checkbox: "Add to subscription" (this truck will cost +€10/mo ERP [+ €10/mo if AI Copilot is company-wide enabled])
  → user ticks it → desktop app calls POST /api/v1/subscriptions/trucks/add { truck_id }
  → backend:
        - increments licensed_truck_count (this is the cap the desktop Fleet Manager enforces)
        - if billing_term = 'annual': computes proration, creates an immediate Stripe charge + fiscal invoice
        - if billing_term = 'monthly': schedules the price increase for current_period_end, charges nothing now
        - returns 200 with the updated subscription state
  → desktop app unlocks the truck slot ONLY on a confirmed 200 — never optimistically before backend confirmation
       (critical: the desktop app may run in flaky-connectivity conditions in a fleet office; optimistic unlock risks a truck being used but never actually billed — a direct revenue leak)
  → Website Subscription page reflects the same state on next load/poll, regardless of whether the change originated in the desktop app or the website itself
```

The **website Subscription page therefore has two real jobs**: (1) manage the account-level things that only make sense on the web (billing term switch, payment method, invoices, priority support/API access toggles, cancellation), and (2) **display**, read-only, the current truck count and per-truck cost — the truck count itself is *added/removed* from the desktop Fleet Manager, not from the website. Don't build a redundant "add truck" control on the website; build a clear, accurate read-only fleet-size display with a link/explanation pointing back to the desktop app's Fleet Manager for the actual add/remove action. This avoids two independent code paths trying to be the source of truth for the same number.

### 4.3 Schema (replaces the tiered-plan schema entirely)

```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    billing_term TEXT NOT NULL CHECK (billing_term IN ('monthly','annual')),
    status TEXT NOT NULL CHECK (status IN ('trialing','active','past_due','payment_deferred','canceled','locked')),
    licensed_truck_count INT NOT NULL DEFAULT 0,        -- the cap enforced by the desktop Fleet Manager right now
    pending_truck_count INT,                             -- monthly only: next-cycle count if an addition/removal hasn't taken effect yet
    ai_copilot_enabled BOOLEAN NOT NULL DEFAULT false,   -- company-wide toggle — see 4.1's open question
    priority_support_enabled BOOLEAN NOT NULL DEFAULT false,
    api_access_enabled BOOLEAN NOT NULL DEFAULT false,
    price_per_truck_erp_cents INT NOT NULL DEFAULT 1000,     -- kept as data, not hardcoded, so future pricing changes/grandfathering don't require a code deploy
    price_per_truck_ai_cents INT NOT NULL DEFAULT 1000,
    priority_support_price_cents INT NOT NULL DEFAULT 5000,
    api_access_price_cents INT NOT NULL DEFAULT 10000,
    annual_discount_pct NUMERIC(4,2) NOT NULL DEFAULT 15.00,
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    trial_ends_at TIMESTAMPTZ,
    payment_deferred_until TIMESTAMPTZ,                  -- leniency feature, see 4.6 — null unless active
    service_credit_cents INT NOT NULL DEFAULT 0,         -- from annual mid-term truck removals
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every truck add/remove is logged as an event, not just reflected as a counter change —
-- this is what makes proration, service-credit accounting, and the audit log (§3.7) all auditable after the fact.
CREATE TABLE subscription_truck_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id),
    truck_id UUID NOT NULL,                -- references the desktop ERP's own vehicle/truck record
    event_type TEXT NOT NULL CHECK (event_type IN ('added','removed')),
    billed_immediately BOOLEAN NOT NULL,   -- true for annual adds (charged now); false for monthly adds (deferred to next cycle) and monthly removes
    amount_cents INT,                      -- the prorated charge amount, if any
    source TEXT NOT NULL CHECK (source IN ('desktop_erp','website')),
    created_by_user_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    subscription_id UUID REFERENCES subscriptions(id),
    stripe_invoice_id TEXT,
    fiscal_invoice_provider TEXT,           -- 'smartbill' | 'oblio' | 'fgo'
    fiscal_invoice_id TEXT,
    fiscal_invoice_pdf_url TEXT,
    amount_cents INT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    status TEXT NOT NULL CHECK (status IN ('draft','open','paid','void','uncollectible','deferred')),
    issued_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payment_methods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    stripe_payment_method_id TEXT NOT NULL,
    brand TEXT, last4 TEXT, exp_month INT, exp_year INT,
    is_default BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.4 Shared API endpoints (one contract, consumed by both desktop ERP and website)

```
GET  /api/v1/subscriptions/current                        → full state: term, truck count, price breakdown, trial status, addon flags
POST /api/v1/subscriptions/trucks/add      { truck_id }    → called by the desktop Fleet Manager's "Add to subscription" checkbox
POST /api/v1/subscriptions/trucks/remove   { truck_id }
POST /api/v1/subscriptions/toggle-addon    { addon: 'ai_copilot' | 'priority_support' | 'api_access', enabled: bool }
POST /api/v1/subscriptions/billing-term    { term: 'monthly' | 'annual' }   -- switching term is its own proration case, spec it explicitly, don't leave it implicit
POST /api/v1/subscriptions/checkout                                        -- Stripe Checkout session for the current computed total
POST /webhooks/stripe                                                       -- signature-verified + idempotent, per §18b.3
```

**Switching billing term mid-cycle** (monthly→annual or annual→monthly) is not mentioned in the source doc but will absolutely happen in practice — spec it now rather than discovering it as an edge case in production: monthly→annual should prorate the remaining days of the current monthly period as a credit against the new annual charge; annual→monthly should only take effect at the existing annual term's natural end (don't let a customer escape an annual commitment early via a term switch — that would undermine the entire "no refund on annual" rule in 4.1).

### 4.5 Frontend page-by-page rebuild

| Page | Current | Rebuild spec |
|---|---|---|
| `subscription.tsx` | 100% mock, disabled Upgrade/Downgrade/Cancel, tier-based UI that no longer matches the real model | Rebuild around: current truck count (read-only, sourced from `licensed_truck_count`, with a note "manage trucks from the desktop app's Fleet Manager"), a clear price breakdown (`N trucks × €10 ERP` + `N trucks × €10 AI Copilot` if enabled + flat add-ons), a billing-term toggle (monthly/annual) with the proration/credit consequence spelled out *before* the user confirms the switch, AI Copilot / Priority Support / API Access toggles wired to `toggle-addon`, Cancel → confirmation modal with explicit "trucks stay usable until `current_period_end`" copy |
| `billing.tsx` | 100% mock invoices/payment/tax | Same as before: real invoice list + real fiscal PDF download, Stripe SetupIntent/Elements for payment methods, VAT field validated against EU VIES format, persisted via a real `PATCH /company/tax-info` |
| `downloads.tsx` | Hardcoded config, "TBD" file size | Wire to real `GET /downloads/latest` + `/downloads/versions`; real version, changelog excerpt, signed URL, SHA256 checksum, file size, release date |
| Trial banner (new, dashboard-wide) | Doesn't exist | A persistent, dismissible-per-day (not permanently dismissible) banner during `status = 'trialing'` showing days remaining, escalating visually inside the last 4 days to match the 4-day notice rule in 4.1 |

### 4.6 The AI-driven payment-leniency feature — flag for review before building

The source material describes a genuinely novel mechanic: the AI Copilot, having visibility into the transport company's own accounts receivable (their customers' overdue invoices), can proactively **defer Operion's own subscription charge** and roll the billing cycle forward "as if paid" when it detects the customer is in a cash crunch.

**This needs accountant/legal sign-off before it's built, not after** — restating the same caution already given for the core billing/e-Factura work, because this specific feature adds real complications on top of it:
- It's a form of **automated credit extension** — deciding to defer payment based on an automated inference about a customer's cash position is edging toward a credit decision, which can carry its own regulatory considerations depending on how it's structured and communicated.
- **You cannot skip issuing a fiscal invoice just because payment is deferred** — Romanian e-Factura obligations are tied to the transaction/service period, not to whether cash has changed hands. A deferred-payment invoice still needs to exist and be reported, just marked outstanding rather than paid — confirm the exact timing rules with your accountant against this specific "deferred, not discounted" mechanic.
- **Revenue recognition**: deferring the payment date without deferring the service period (the customer keeps using Operion during the deferral) has real accounting implications for how/when that revenue is recognized — this is exactly the kind of thing that's cheap to get right up front and expensive to unwind later.

**If/when cleared to build**, the technical shape is straightforward: a scheduled job evaluates a simple risk signal (e.g., "X% of the customer's own tracked receivables are overdue by Y+ days") ahead of a renewal date; if triggered, `payment_deferred_until` is set and `status` moves to `payment_deferred` — a distinct status from `past_due`, with no lockout and no dunping/collection emails, just a quiet extension. **Sequence this as P2/P3 regardless of technical readiness** — ship the straightforward per-truck billing (4.1–4.5) first, prove it in production, and only layer this on afterward once it's been reviewed.

### 4.7 Free trial, migration tooling, and team setup — cross-references to keep the model coherent

- **Trial mechanics**: `trial_ends_at` set on company creation at registration (14 days out), no payment method collected at signup (already true of your Register flow, §8.2 — no change needed there). Desktop ERP gates full functionality on `status = 'trialing' AND trial_ends_at > now()`; on expiry, moves to a **locked, non-destructive** read-only-or-blocked state (data preserved, not deleted) until a real subscription exists. Notification job fires at `trial_ends_at - 4 days` via email + the notification-center component (§9.1) + a dashboard/desktop banner.
- **Migration tooling** (OCR photo ingestion + CSV import) is primarily a desktop-app concern, but the **website's onboarding checklist** (§9.8) should include a "Migrate your existing data" step that deep-links into the desktop app's migration tab, auto-completing when the desktop app reports a successful migration event through the shared backend — same auto-completion pattern already speced for other onboarding steps. Any uploaded document photos go through the same file-upload-safety rules already speced in §18c.2 (magic-byte validation, size limits, malware scanning where infra allows) — the EXIF-stripping privacy concern from that section is less relevant here (these are photos of business documents, not personal photos), but the type/size/malware checks fully apply.
- **Team setup model — flag an explicit decision, don't silently pick one**: the source material describes the *owner* directly typing login credentials for a driver/dispatcher, which is a different model from the email-invite-and-accept flow already speced for Organizations in §3.5. Recommended resolution: keep **drivers** on the simpler owner-issued-credentials flow (matches the reality of a mobile-app driver who may not check email), while keeping **dispatcher/manager/admin** roles on the more secure self-set-password email-invite flow already built — update §3.5 with a one-line cross-reference to this split rather than re-speccing RBAC itself.
- **Freight exchange connect** ("click Connect → browser OAuth flow → done") is the Freight Exchange Integration module already speced in your AI Co-Pilot V4 blueprint — no new website work implied beyond a clear per-provider "Connect" entry point in Company/Settings.

### 4.8 Launch-realistic sequencing

Given the model is now fully specified (unlike the earlier generic-tier version), **this is buildable pre-launch** if backend capacity allows — it's no longer a "defer to post-launch" candidate the way an undefined Stripe integration was. If the desktop-ERP↔website sync (4.2) can't be finished in time for Sept 1, the honest-defer fallback is: ship the website Subscription page as **fully real and read-only** (accurate truck count, accurate price, accurate trial countdown) while the *only* thing deferred is the live "Add to subscription" checkbox inside the desktop app — in that interim state, truck additions go through a manual/support-assisted process rather than the automated flow, which is still honest (nothing fake is shown) even though it's not yet the fully automated end-state.

---

## 5. DEVICE MANAGEMENT — FULL TECHNICAL SPEC

(Expands v1 §4 with the exact current-state table from your dump for precision.)

### 5.1 Current fragmentation (verbatim from spec, for the agent's reference)

| Concept | Endpoints | UI location | Status |
|---|---|---|---|
| Mobile Devices | `GET/DELETE /mobile/devices` | `/dashboard/devices` | ✅ Real API |
| License Devices | `GET/DELETE /licenses/:id/devices` | `/dashboard/licenses` | ⚠️ Mock data, deactivate disabled |
| Auth Sessions | `GET/DELETE /auth/sessions` | `/dashboard/devices` (bottom) + Profile | ✅ Real API |

### 5.2 Unification spec

- Merge duplicated `DeviceInfo` type definitions (`endpoints.ts` vs `types/index.ts`) into one canonical interface, imported everywhere.
- Build one shared `<DeviceList>` component consumed by three contexts (mobile devices, license devices, auth sessions) rather than three bespoke card-list implementations — reduces future maintenance to one place.
- License Devices: replace `mockDevices` with `useLicenseDevices(licenseId)` → real query; enable the deactivate button → `useDeactivateLicenseDevice()` → `DELETE /licenses/:id/devices/:deviceId` (endpoint already exists, this is pure frontend wiring).
- Add `staleTime: 60_000` to `useDevices` (currently refetches every mount per your own gap note).
- Add `sonner` toast on every mutation (deactivate, revoke) — currently silently missing per your gap list.

### 5.3 New capability specs

| Capability | Technical spec |
|---|---|
| Search/filter | Client-side `useMemo` filter over loaded list by name/user/platform — no new endpoint needed for current scale; move server-side if device counts grow past a few hundred per company |
| Detail view | Slide-over `<Sheet>`/drawer component, triggered on row click, shows full metadata (id, platform, last_seen, created_at, linked user, IP if available) |
| Bulk operations | Row checkboxes + a `useDeactivateDevices(ids[])` batched mutation (or `Promise.allSettled` over the single-delete endpoint if no batch endpoint exists) with one summary toast ("3 of 4 devices deactivated, 1 failed") instead of one toast per row |
| CSV export | Client-side, `papaparse`'s `unparse()` over the already-loaded list — zero backend dependency |
| QR pairing (mobile) | Backend: `POST /mobile/pairing-token` → short-lived (2–5 min) signed token → frontend renders as QR (`qrcode` lib) → mobile app scans → exchanges token for session at `POST /mobile/pairing-token/redeem`. Genuinely differentiated UX for drivers on a truck-mounted tablet who don't want to type credentials — prioritize this even at 🟡 medium listed priority because it directly reduces support-ticket volume, which is a stated priority for you given the ops/ARGO investment |
| Remote force-logout | Already have `DELETE /auth/sessions/:id` — surface it from the unified device view, not only buried in Profile → Sessions |

### 5.4 Explicitly post-launch (don't scope-creep before Sept 1)

Geolocation/map, battery/signal/app-version health, per-device driver reassignment, admin cross-tenant view.

---

## 6. DESIGN SYSTEM & COMPONENT LIBRARY — EXHAUSTIVE PER-COMPONENT AUDIT

Your spec dump lists 17 hand-rolled UI primitives and ~25 shared feature components. Since these are hand-rolled (not a maintained shadcn/ui install), each one needs an individual accessibility/robustness pass — bugs here propagate to every page that uses them.

### 6.1 Core UI primitives — audit checklist per component

| Component | Audit points |
|---|---|
| `avatar` | Fallback initials render correctly for names with non-Latin characters (Romanian diacritics: ă, â, î, ș, ț); broken image URL falls back gracefully, doesn't show a broken-image icon |
| `badge` | Color-contrast check per variant in both themes (§7.3) |
| `breadcrumb` | `aria-label="breadcrumb"`, current page marked `aria-current="page"`; verify it correctly reflects nested dashboard routes (ties to §2.3's nav-highlighting fix) |
| `button` | All 6 variants × 4 sizes have visible focus rings (`focus-visible:ring`) — verify `ghost`/`link` variants specifically, lowest-contrast variants are where focus rings get missed; loading state disables the button and shows a spinner, not just visually dims it |
| `callout` | `variant="danger"` used for errors — verify `role="alert"` for screen-reader announcement |
| `card` | No functional gap — verify consistent `hover:shadow-md` only on genuinely interactive cards, not static info cards (a hover effect on a non-clickable card is a common UX confusion bug) |
| `copy-button` | Verify it's actually wired everywhere something copyable exists (license key, referral code, invoice number, future API key) — audit for missing usages, not just correctness of existing ones |
| `input` | Error state wires `aria-invalid` + `aria-describedby` to the error text (ties to §7.3) |
| `loading-spinner` | `role="status"` + visually-hidden "Loading..." text for screen readers |
| `pagination` | Keyboard-operable (arrow keys or tab-through), current page announced |
| `progress` | Used for onboarding %, storage usage — verify `aria-valuenow/min/max` present |
| `separator` | `role="separator"` or `aria-hidden` if purely decorative — no functional gap likely |
| `skeleton` | **Must match the actual shape** of the content it replaces (flagged in v1 — restated because it's a genuine, visible polish gap): audit every usage (device cards, invoice rows, blog cards) individually |
| `tabs` | Full keyboard support (arrow-key navigation between tabs per WAI-ARIA tabs pattern, not just click) — commonly missed in hand-rolled tab components |
| `tag` | Color-contrast per category color |
| `tooltip` | Keyboard-triggerable (focus, not just hover) — a hover-only tooltip is inaccessible to keyboard/screen-reader users, and you use tooltips for the RBAC permission matrix (§3.5) specifically |

### 6.2 Feature components — targeted fixes

| Component | Fix |
|---|---|
| `global-search` (⌘K) | Extend with quick-actions per v1 §6.5 ("Invite teammate", "Create ticket", "Download desktop app") — turns search into a productivity surface |
| `live-chat` (ARGO AI) | Currently "Coming Soon" — see §11.8 (Support page) for full spec |
| `notification-center` | Currently unused despite existing — see §7.1 (frontend quick wins) for wiring spec |
| `org-switcher` | Verify it correctly refetches company-scoped queries (devices, licenses, billing) on switch — a common bug is stale cached data from the previous org bleeding into the new context; add explicit `queryClient.invalidateQueries()` scoped by org id on switch |
| `release-card` | Currently fed hardcoded release data on Dashboard — wire to real Content/changelog API (§11 dashboard section) |
| `newsletter-form` | Verify distinct success/error handling matching waitlist form's care level (v1 §7.5) |
| `social-share` | Prioritize WhatsApp share target explicitly for the Romanian SME audience (v1 §7.2), not just generic Twitter/LinkedIn |
| `table-of-contents` | Used on blog/docs — verify scroll-spy highlighting works with the lazy-loaded route content (timing bug risk: ToC built before content mounts) |
| `testimonial-card` / `logo-cloud` | Currently likely placeholder-driven per the "Coming soon" screenshots pattern — see §12.1 (Home page) for real-content sourcing plan |
| `comparison-table` | Used on Pricing — verify responsive behavior at 375px (a comparison table is one of the hardest responsive patterns; horizontal scroll with sticky first column is the standard fix, verify it's implemented, not just `overflow-x-auto` with no visual scroll affordance) |

### 6.3 Theme & color system technical audit

- OKLCH tokens for `--primary`, `--background`, `--card`, `--destructive`, `--sidebar` — run every text/background pairing through a contrast checker (`oklch()` lightness values can visually look fine and mathematically fail WCAG AA). Specifically check: `muted-foreground` text on `card` background in dark mode (`oklch(0.18 0 0)` card) — this pairing is the most common contrast failure in dark-mode OKLCH systems.
- Add `color-scheme` meta toggle per §2.1.
- Verify `@custom-variant dark (&:is(.dark *))` Tailwind v4 strategy doesn't break when a component is portal-rendered outside the themed root (modals/tooltips/toasts rendered via `createPortal` sometimes escape the `.dark` class ancestor chain) — explicitly test toast and modal theming in dark mode.

### 6.4 Typography & spacing

- Inter (sans) + JetBrains Mono — verify `font-display: swap` is set to avoid invisible-text-during-load (FOIT), and that both fonts are self-hosted or preloaded (not blocking on a third-party font CDN) for performance (ties to §14 Core Web Vitals).
- `--radius: 0.625rem` with sm/md/lg/xl variants — no functional gap, just verify consistent application (audit for any component using a raw `rounded-lg` Tailwind class instead of the token, which would drift from the design system on a future token change).

### 6.5 Animation system

- `motion` staggered entrance (`opacity:0,y:20 → opacity:1,y:0`, delay increments of 0.05s, custom cubic-bezier easing, `viewport={{once:true}}`) — mechanically sound. Two additions:
  - Verify `prefers-reduced-motion` disables **all** motion usages, not just a subset — audit every `motion.div` for a shared wrapper/hook (`useReducedMotionSafe`) rather than relying on each usage remembering to check it individually.
  - Cap total stagger delay: if a grid has 12+ cards at 0.05s increments, the last card waits 600ms to appear — add a max delay ceiling (e.g., cap at 0.3s, group remaining items) so long grids don't feel sluggish.

### 6.6 "Every page looks the same" risk (from v1, restated with technical fix)

Home/Pricing/Waitlist already have distinctive visual moments (animated SVG map, gradient hero, glass card). Features and Industry pages currently reuse the anchor-section + card-grid + placeholder pattern identically per page — technical fix: build **one additional distinctive visual module** (e.g., an interactive before/after slider, an animated stat counter, or a real embedded product screenshot carousel) and vary *which* module appears on Features vs each Industry page, so the templated card-grid isn't the only thing every page has in common.

### 6.7 Screenshot/placeholder replacement (P1, credibility-critical)

Home page's 3-tab Screenshots section and Features page's per-section screenshot placeholders both currently say "Coming soon." Technical spec: capture real product screenshots (dispatcher board, route planner, AI copilot chat, document generator) at 2x resolution, export WebP with PNG fallback, add subtle browser-chrome framing (you already have this pattern built for the Home hero mockup — reuse that exact component/style for consistency) rather than a bare screenshot. If full walkthroughs are ready before real screenshots, a short (~15s) looping muted video/GIF in the same frame outperforms a static image for conveying a live product.

### 6.8 Empty states — systematic pass

Audit every page that can legitimately show zero items (devices, invoices, team members, tickets, licenses, notifications, referrals) and ensure each `EmptyState` usage has: a distinct icon, specific (not generic) copy, and — where relevant — an inline primary CTA (e.g., "No team members yet" → "Invite your first teammate" button inline, not just descriptive text with no action).

### 6.9 `<RoadmapFeature>` shared component (referenced throughout this doc)

Replaces every ad-hoc "Coming Soon" callout (Live Chat, AI Assistant, MFA-if-deferred, Data Export, API Keys, floating licenses, offline activation, previous-versions list):
```typescript
interface RoadmapFeatureProps {
  title: string;
  description: string;          // what it will do, 1-2 lines, sets real expectation
  targetQuarter?: string;        // e.g. "Q4 2026" — omit if genuinely unknown, show "Under evaluation" instead
  featureKey: string;            // for interest tracking
}
```
Backend addition: `feature_interest (id, user_id, feature_key, created_at)` table — "Notify me" writes here. This doubles as **prioritization data**: real signal on which deferred feature users actually want, versus the current placeholder that captures nothing.

---

## 7. INTERNATIONALIZATION — COMPLETENESS AUDIT (not covered in v1, real gap)

Your `LocaleProvider` mechanism (flat key-value JSON, `domain.section.key` namespacing, current→default→raw-key fallback) is architecturally sound. The real risk with 6 locales and ~50+ pages is **translation completeness drift** — it's very easy for `en.json` to get new keys during feature work while `ro.json`/`de.json`/`fr.json`/`es.json`/`pl.json` silently fall back to English (or worse, to the raw key string) without anyone noticing, since the fallback is silent by design.

**Technical spec**:
- Add a CI script (`scripts/i18n-audit.ts`) that diffs key sets across all 6 locale files against `en.json` (source of truth) and **fails the build** if any non-English locale is missing keys present in English — this closes the "raw key falls through silently" risk with a hard gate, matching your existing "block on regression" testing discipline.
- Given Romanian is very likely your primary launch market, treat `ro.json` completeness as a P0 launch blocker specifically — audit it first and separately from the other 4 locales, which can reasonably lag slightly post-launch.
- Add a lint rule or the same script checking for **hardcoded user-facing strings** in JSX (a common regression as new pages get built quickly) — flag any bare string literal inside a `<p>`/`<h1>`/`<span>` etc. that isn't wrapped in `t()`.
- `hreflang` tags (ties to §14.2) depend on this completeness — don't ship `hreflang="ro"` pointing at a page that's actually still 40% English fallback text.
- Locale-aware formatting: verify dates, currency (€ formatting), and numbers use `Intl.DateTimeFormat`/`Intl.NumberFormat` keyed to the active locale rather than hardcoded `en-US` formatting — a common miss even in otherwise-complete i18n systems (e.g., invoice amounts should show `1.234,56 €` for `ro`/`de` locales, not `1,234.56`).

---

## 8. AUTH PAGES — FULL TECHNICAL SPEC (Spec §12)

### 8.1 Login (`login.tsx`, 108 lines)

- Add: password strength indicator is NOT needed here (login, not creation) — but DO add: returnUrl capture/redirect (§9.2), "Remember me" checkbox (§9.3), MFA challenge step (§3.4), rate-limit-aware error state (§3.8: "Too many attempts, try again in X minutes" rather than a generic "invalid credentials" that doesn't distinguish lockout from wrong password).
- Accessibility: form labeled correctly, error summary announced on failed submit (`aria-live="assertive"` on the top-level error, since silent inline-only errors are easy to miss for screen-reader users on a re-submit).

### 8.2 Register (`register.tsx`, 154 lines)

- 6 fields (Full Name, Email, Company Name, Referral Code from `?ref=`, Password, Confirm Password) — add password strength meter (§9.4), add explicit Terms/Privacy checkbox with links (currently not mentioned in spec — verify it exists; if not, this is a legal-compliance gap, not just UX, given GDPR consent requirements).
- Referral code pre-fill from URL param — verify it's also editable manually (a user pasting a referral link but wanting to correct/clear the code should be able to).
- Email format validation via `zod` should reject obviously invalid patterns client-side before hitting the API, but never rely on client-side validation alone for anything security-relevant (duplicate email, etc. must be server-checked regardless).

### 8.3 Forgot Password / Reset Password / Verify Email

- Standard token-based flows per your dump — technical hardening: reset tokens should be **single-use** and **short-lived** (~30–60 min), and the "forgot password" endpoint should return an identical response regardless of whether the email exists (prevents email-enumeration via response-timing/content differences) — verify this explicitly with the backend team, it's a very common and very easy oversight.
- Verify-email: add a "Resend verification email" action with its own rate limit (prevents email-bombing abuse of the resend button).

---

## 9. FRONTEND-ONLY QUICK WINS — FULL TECHNICAL SPEC (Spec §10, backend already supports these)

### 9.1 Notification bell → real dropdown

- Wire existing (unused) `notification-center` component to `PortalNotification` list.
- `useNotifications()` with `refetchInterval: 30_000` (poll — full WebSocket is 🟢 P3, not required for launch).
- Unread-count badge on the bell icon; "Mark all read" bulk action; click-through uses the notification's `link` field via `react-router`'s `navigate()`.

### 9.2 Return URL after login

```typescript
// ProtectedRoute
if (!isAuthenticated) {
  return <Navigate to={`/login?returnUrl=${encodeURIComponent(location.pathname + location.search)}`} replace />;
}
// login.tsx on success
const returnUrl = searchParams.get('returnUrl');
navigate(returnUrl ?? '/dashboard', { replace: true });
```
Validate `returnUrl` is a same-origin relative path before navigating to it (open-redirect prevention — never navigate to an arbitrary external URL from a query param).

### 9.3 "Remember me"

Unchecked → session-scoped storage (post §3.1 migration, this maps to a shorter-lived or non-persistent refresh cookie if the backend supports a `remember` flag on `/auth/token`; if not, this is a small backend addition — a `remember: boolean` field controlling refresh-token `Max-Age`).

### 9.4 Password strength indicator

Live-updating meter (weak/fair/good/strong) + checklist (✓ 8+ chars, ✓ number, ✓ symbol, ✓ uppercase) mirroring actual server-side complexity rules — a ~40-line component using a simple scored-rules function is sufficient, no need for a heavy external library (`zxcvbn` is overkill for this use case and adds real bundle weight).

### 9.5 Dashboard real stats (highest-visibility fakery — fix first)

Replace all of: 4 stat cards, Subscription Summary, Storage Usage, Active Sessions, Latest Release, Announcements with real data from Companies/Devices/Licenses/Sessions/Content APIs already wired elsewhere in the app. If Storage Usage has no real backend field yet, **honest-defer**: drop the card or swap for a metric you do have (Active Licenses, Team Members count) rather than leaving a fabricated "2.3GB/10GB, 23%".

### 9.6 Profile avatar persistence

One-endpoint fix: wire the existing upload UI to `PATCH /auth/me` (multipart or presigned-URL pattern matching however the backend expects file uploads elsewhere in the ERP — check for an existing pattern in the desktop/mobile apps to stay consistent rather than inventing a new upload convention just for the website).

### 9.7 Notification preferences save

Wire the currently-disabled save button to a real endpoint; if none exists, minimal backend addition is a single `notification_preferences JSONB` column on the user row — no new table required.

### 9.8 Onboarding checklist → real API

`GET /onboarding/checklist` exists but is unused; `onboarding.tsx` uses 100% hardcoded data. Swap for the real query, and — for the "S-grade" version — wire step completion to fire **automatically** from real app events (email verified → step 1 auto-completes; desktop download initiated → step 4 auto-completes; first route created — if that event is emittable from the ERP backend — auto-completes step 5) rather than requiring manual checkbox clicks for everything. This turns the checklist from a static to-do list into a genuinely reactive progress tracker.

---

## 10. DASHBOARD PAGES — REMAINING PAGE-BY-PAGE DETAIL (Spec §10, pages not fully covered above)

### 10.1 Company page (`company.tsx`, 319 lines)

- General/Team/Billing tabs. Team tab: unify with Organizations per §3.5. Upload Logo / Edit Details currently disabled → wire to `PATCH /company` (already exists) with real file upload for logo. VAT placeholder → real field, validated per §4.4's tax-info spec. Departments (hardcoded) → either build real department management (if the ERP backend has this concept) or remove the hardcoded fake list entirely per the Section 1 rule — a fake "4 departments" stat with no way to manage departments is a pure credibility loss with zero function.

### 10.2 Settings page (`settings.tsx`, 373 lines)

- Appearance/Notifications/Language & Region/Security/Data & Privacy tabs — mostly local-state or disabled today. Notifications → same fix as §9.7. Security tab → password status real (already partially wired), 2FA → real per §3.4 (or honest-defer via `<RoadmapFeature>` if MFA slips past launch). Data & Privacy: Data Export "Coming Soon" → minimum viable pre-launch version is a real, if manual, flow: "Request my data" button creates a Support ticket via the already-working Support API with a special category, handled manually until a self-serve export job exists — this is a GDPR-adjacent compliance signal, not optional polish, given you're operating in the EU. Delete Account → same treatment, see §1's disposition rules; do not ship a permanently-disabled destructive button, that's the single worst pattern in the entire "Coming Soon" list from a trust standpoint.

### 10.3 Support page (`support.tsx`, 376 lines)

- Submit Ticket / My Tickets / Knowledge Base tabs — bug report + feature request forms already post to real API, good. Live Chat "Coming Soon" and AI Assistant "Coming Soon": given your `live-chat` component already exists and references "ARGO AI" (your Co-Pilot/Ops brand), the highest-leverage move here is connecting this to the **Ops Console / ARGO Support** system you've already built the backend blueprint for (per your own project history) rather than treating it as a brand-new feature — this is very likely your fastest path to a working AI-assisted live chat, since the orchestrator and support-ticket infrastructure conceptually already exist server-side. Flag this explicitly to whoever's building `operion-ops` as a shared-infrastructure opportunity rather than building a second, separate chat system for the website.

### 10.4 Onboarding page (`onboarding.tsx`, 444 lines)

- Beyond §9.8's checklist-wiring fix: the circular SVG progress indicator, 4 tutorial cards, 3 releases, 5 best practices should all pull from real Content/Tutorials/Changelog APIs (already exist per your API list) rather than hardcoded arrays — this page is currently the single most mock-data-dense page in the dashboard after Subscription/Billing.

### 10.5 Organizations & Referrals pages

Already real/full per your dump — no rebuild needed. Technical note: once §3.5's RBAC unification lands, verify Organizations' member-management UI is the *one* place this logic lives (don't let Company→Team redevelop parallel invite/role logic — literally reuse the same mutation hooks).

---

## 11. PUBLIC MARKETING PAGES — FULL CATALOG AUDIT (Spec §11, ~50 pages)

Grouped by function since auditing 50 pages individually in prose would bury the signal — each group gets concrete, specific technical direction.

### 11.1 Home (`home.tsx`, 564 lines) — see §6.6/§6.7 for visual-differentiation and screenshot fixes. Additional: add the secondary sticky/inline CTA after the Features section (v1 §7.4) since the page is long enough that a converted visitor shouldn't have to re-scroll to act.

### 11.2 Features (`features.tsx`, 223 lines) — see §6.6/§6.7. Additional: verify each anchored section (Route Planning, Fleet, Dispatch, Documents, Analytics, AI/Automation, Integrations) has genuinely distinct problem-statement copy, not templated filler — a logistics buyer evaluating 7 feature areas will notice if 5 of them read identically with nouns swapped.

### 11.3 Pricing (`pricing.tsx`, 116 lines) — JSON-LD (Product+FAQ) already present, extend per §14.1 with Organization schema too. "Early Access — Free" framing is honest and correct for pre-launch — keep as-is until §4's billing ships, then this page becomes the actual checkout entry point.

### 11.4 Waitlist (`waitlist.tsx`, 374 lines) — full narrative rework already specified in v1 §7 (problem-first structure, live counter instead of static "500+", WhatsApp share priority, honest urgency). No changes to that spec here — it stands.

### 11.5 About / Argo / Mission — brand pages. Technical note: "Argo" is your AI engine's name and also appears as a public-facing page — verify no naming confusion with the internal "ARGO Support" orchestrator (per your project history) if that name is ever mentioned publicly; keep the public-facing narrative about the AI engine's *user-facing capabilities*, not its internal architecture.

### 11.6 FAQ / Contact — verify Contact form has the same success/error rigor as Waitlist/Newsletter (v1 §7.5 pattern) — a broken/silent contact form on a B2B site is a direct lead leak.

### 11.7 Privacy Policy & Terms — content outline + rendering spec

**Standing caveat, unchanged**: neither Claude nor any coding agent should draft or "finalize" the actual legal text of the Privacy Policy or Terms — this needs a lawyer's review before publication, same as the billing/e-Factura caveat in §4.1. What follows is a **content checklist** — the specific things this Privacy Policy needs to cover given what Operion actually does, so your counsel is working from a complete brief rather than a generic template. This is factual scoping, not legal advice.

Given the actual product surface described in the business model, a generic SaaS privacy-policy template would miss several genuinely Operion-specific data flows that need their own disclosure:

- **Driver location/GPS data**: the mobile app almost certainly captures driver location for dispatch/tracking purposes. The **transport company** is very likely the data controller for this data (it's their employee/contractor being tracked for their business purposes) with **Operion as processor** — this needs a proper Data Processing Agreement (already flagged in §18a.4) referenced from the Privacy Policy, and the policy needs to clearly distinguish "data we control as your SaaS provider" (account/billing data) from "data you control and we process on your behalf" (fleet/driver operational data).
- **OCR-processed document photos**: photos of CMRs, invoices, and other paper documents uploaded for migration/automation may contain third-party personal data (driver names, customer contact details, signatures) that Operion's OCR pipeline processes. State plainly what happens to these photos after processing (retained? deleted? for how long?) — this is a concrete, checkable claim, not boilerplate.
- **Gmail/email API access ("automail")**: this is the single highest-scrutiny data flow in the entire product. Using Google's Gmail API to send/read mail on a customer's behalf requires specific OAuth scopes, and depending on which scopes are requested, **Google's own verification process** (potentially including an annual third-party security assessment for "restricted" scopes) applies independently of your own privacy policy — flag this to whoever owns the Gmail integration as its own compliance workstream, separate from the website's Privacy Policy page, but the policy must accurately describe what's accessed and why once that scope decision is made.
- **Freight exchange OAuth connections** (TIMOCOM etc.): similarly needs a clear statement of what's accessed/stored (tokens, load data) and for how long.
- **AI processing of operational/company data**: state explicitly whether customer data is ever used to train or fine-tune any AI model (the standard, competitively-favorable answer for a B2B tool is "no, your data is not used to train models" — but this must be *true* of however the AI Copilot is actually implemented before it's published as a claim) and name the AI provider(s) involved as sub-processors if the Copilot calls out to a third-party LLM API.
- **Sub-processor list**: a concrete, named list — Stripe (payments), SmartBill/Oblio/FGO (fiscal invoicing), whichever AI provider powers the Copilot, hosting/CDN (Cloudflare), and any OCR service if it's a third-party API rather than self-hosted. A specific, accurate sub-processor list is both more compliant and a stronger trust signal than a vague "we may share data with service providers" line — same principle already applied to the Cookie Policy in §18a.2.
- **International data transfers**: if any sub-processor (especially an AI provider) is US-based, the policy needs to reference the transfer mechanism (Standard Contractual Clauses, etc.) — this is a real, checkable legal requirement under GDPR, not optional detail.
- **Data retention specifics**: cross-reference §18a.4's retention periods (audit log, deleted-account grace period, backup RPO/RTO) rather than restating vague "as long as necessary" language once those numbers actually exist.

**Rendering scope for the agent** (this part is normal implementation work, not legal work): markdown/rich-text rendering, a table of contents for a document this long, print-friendly styling (§18c.4), a clearly dated "last updated" stamp with a changelog of material changes (a trust-building pattern increasingly common on B2B privacy pages), and a version history if the policy changes meaningfully post-launch — customers on an annual contract in particular may reasonably want to see what changed since they signed up.

### 11.8 Security — since you're building real security features (§3), this page should describe your **actual** posture (MFA availability, encryption at rest/in transit, audit logging, security-headers grade) rather than generic boilerplate — this becomes a genuine differentiator once §3 ships, worth revisiting content-wise after the security work lands, not before.

### 11.9 Blog (`/blog`, `/blog/:slug`, category, author) — already full CRUD + real API, good. Technical additions: Article JSON-LD schema (§14.1), unique `og:image` per post (§14.2), reading-time estimate + related-posts module (cheap, improves session depth/SEO dwell time).

### 11.10 Tutorials — verify these consume real Content API, not a static list — audit against the same "hardcoded despite live endpoint" pattern found elsewhere (§9.8's onboarding bug is a known instance of this class of gap; check tutorials for the same mistake).

### 11.11 Changelog / Roadmap / Status — these are trust-signal pages (transparency). Status page specifically: if the "pulsing green dot" is currently hardcoded rather than reflecting a real uptime/incident feed, that's a trust-signal integrity issue worth fixing properly — either wire to a real status provider (Statuspage.io, Better Uptime, or a simple self-hosted healthcheck endpoint) or don't imply real-time monitoring you don't have.

### 11.12 Security report / Developers / Toolkit / API Playground / Integrations Explorer — developer-facing pages. API Playground specifically implies live API interaction — verify it's sandboxed (a rate-limited demo key or mocked responses), never exposing a path to hit production endpoints with unauthenticated/unintended access.

### 11.13 Products / Integrations — Integrations page is directly relevant to your active TIMOCOM/Trans.eu/Alpega partnership conversations (per your project history) — prioritize making this page reflect real integration status accurately (live/in-progress/planned) rather than aspirational, since a partner evaluating you may check this page directly.

### 11.14 Community / Newsletter / Customers — Customers page implies testimonials/case studies; per §6.2/§6.7, source real content here as soon as the family-member MVP tester's feedback is available (even anonymized) rather than placeholder logos/quotes.

### 11.15 Careers / Press / Brand — lower priority for a pre-launch B2B product; verify these aren't broken/empty-looking if linked from the footer nav, but don't over-invest here before Sept 1.

### 11.16 Enterprise / Partners / Trust / Trust Center — Trust Center is directly analogous to a SOC2-style trust page; once §3's security work + real audit logging exist, this page should enumerate them concretely (this is the same content opportunity as §11.8's Security page — consider merging Trust Center and Security into one authoritative page rather than maintaining two overlapping trust narratives, which is a common redundancy in marketing-site information architecture).

### 11.17 Product Tour / ROI Calculator / Route Demo — these are your interactive-demo pages, high-value for conversion. ROI Calculator specifically: verify the underlying math/assumptions are labeled as illustrative (avoid making unsubstantiated cost-savings claims to a professionally skeptical logistics buyer) — show the formula/assumptions transparently rather than a black-box output number, which builds more credibility with this specific audience than a bigger flashy number would.

### 11.18 Industry pages (transport/freight/fleet/owner-operators/agriculture/construction/manufacturing) — per §6.6, audit for genuinely distinct body content per industry, not a shared template with swapped headings (a common thin-content SEO trap flagged in §14.3 as well). Each should reference the specific pain points of that vertical (e.g., agriculture's seasonal/harvest routing constraints differ meaningfully from long-haul freight's tachograph/rest-period constraints) — this is a content-writing task more than a technical one, but the *page template* should support genuinely different section structures per industry if the content warrants it, not force every industry into an identical card-grid.

---

## 12. ADMIN PAGES (Spec §13 — not covered in v1 at all)

### 12.1 Admin Blog Editor

Full CRUD (title, slug, excerpt, content, category, tags, featured image, SEO fields, publish toggle) already exists. Technical hardening: verify the rich-text/markdown editor sanitizes output before render (stored-XSS risk on a CMS-style editor is one of the more common real-world attack vectors — verify content is sanitized both on save and on render, defense in depth) — this directly matters since blog content renders on public pages with no auth wall, making it a genuine attack surface if an admin account is ever compromised or if multiple admins with varying trust levels exist.

### 12.2 Admin Waitlist

Overview (stats/conversion rate), Entries (paginated + search/filter + CSV export), Campaign (email sends), Referral tracking — already comprehensive. Technical addition: since §11.4's waitlist rework adds a **live counter** to the public page, verify the Overview tab's stats query is efficient enough to also back that public-facing counter (or use a cached/denormalized count rather than hitting the same expensive aggregate query on every public pageview — a public page should never run an unbounded admin-grade analytics query on each visitor).

### 12.3 Ops Console (5 pages: Tickets, Approvals, Guardrails, Dashboards, Knowledge)

This is the frontend surface for your `operion-ops` / ARGO Support system per your project history. Technical note specific to this blueprint's scope: verify this console is properly gated by `RequireRole`/`AdminRoute` (§3.5) and is not reachable by a `dispatcher`/`driver`-role authenticated user who guesses the URL — since this console has direct operational control (approvals, guardrail overrides), it should arguably have its own stricter role check beyond generic "admin" (e.g., a dedicated `ops_admin` permission) given the two-agent autonomous design's blast radius if misused.

---

## 13. ERROR PAGES & EDGE STATES (Spec §4 — `/500`, `/maintenance`, `/offline`, `*` — not covered in v1)

### 13.1 `/500` (server error page)

Verify it's a real, on-brand page (not a generic framework fallback) with: clear "something went wrong on our end" copy, a "Try again" / "Go home" action, and a way to report the issue (reuse the Support ticket pre-fill pattern from §2.1's ErrorBoundary fix).

### 13.2 `/maintenance`

Verify this is genuinely reachable via a feature-flag/redirect mechanism you control (so you can flip the whole site into maintenance mode during a deploy or incident) rather than being a route that exists but nothing ever actually routes to.

### 13.3 `/offline`

Since there's no service worker yet (PWA is 🟢 P3 per v1 §9), verify what currently triggers this route — if nothing does without a service worker, this page is presently dead code; either wire basic offline detection (`navigator.onLine` + a listener) to actually show it, or note it as depending on the PWA work and defer both together.

### 13.4 `*` (catch-all 404)

Verify it's a real, helpful 404 (search box or link back to key pages: Home, Features, Pricing, Docs — not just "Page not found") and that it returns an actual HTTP 404 status where your hosting setup allows it (SPA fallback routing via Netlify's `_redirects` can otherwise serve a 200 for genuinely missing pages, which is bad for SEO — verify your `_redirects`/hosting config handles this correctly, e.g., via a status-code rewrite rule if Netlify's redirect syntax supports it, or accept the SPA limitation explicitly and mitigate via a `noindex` meta tag on the 404 page content).

---

## 14. SEO — FULL TECHNICAL SPEC (Spec §18, expands v1 §8)

### 14.1 Structured data expansion

- **Organization** schema sitewide (name, logo, `sameAs` social links) via a shared layout-level component — currently only Product/FAQ schema exists, and only on Pricing.
- **Article** schema on every blog post (headline, author, datePublished, dateModified, image).
- **SoftwareApplication** schema on Home/Features (`applicationCategory: BusinessApplication`, `operatingSystem`, `offers`).
- **BreadcrumbList** schema wherever the `breadcrumb` component already renders.
- **LocalBusiness** schema if Cargo Dyvagri SRL has a physical registered address relevant to local/Romanian search.

### 14.2 Technical checklist

- [ ] Unique `<title>`/meta description per page — audit Industry pages specifically for template-driven duplicates.
- [ ] `hreflang` for all 6 locales — blocked on §7's i18n completeness audit passing first.
- [ ] Core Web Vitals: LCP < 2.5s, CLS < 0.1, INP < 200ms on Home/Features/Pricing/Blog-post — verify hero images have explicit `width`/`height` (CLS prevention), fonts use `font-display: swap` (§6.4).
- [ ] Unique `og:image` per page/post, not the global fallback everywhere.
- [ ] Dynamic XML sitemap (blog posts + industry pages included, not a static hand-maintained file).
- [ ] Prerendering for public routes (§2.2) — the single highest-leverage item on this list given a CSR SPA architecture.

### 14.3 Content/keyword strategy

Target Romanian long-tail queries your blog/tutorials infrastructure already supports (e.g., "calcul profitabilitate transport marfă," "software dispecerat transport," "planificare rute flotă camioane"). Industry pages (§11.18) are high-value long-tail SEO surface *only if* genuinely distinct per vertical — audit against the thin-content trap explicitly.

---

## 15. PERFORMANCE & SCALABILITY (Spec §22, expands v1 §9)

- Bundle analysis (§2.2) — split any chunk >150KB gzip.
- Image pipeline: WebP/AVIF + `srcset`, especially for §6.7's real product screenshots.
- PWA: service worker for offline dashboard shell + "Add to Home Screen" — genuinely useful for dispatchers living in the web portal on a tablet; 🟢 P3, don't block launch on it.
- API caching: per-endpoint `staleTime` tuning (§2.1) already specified — apply consistently across all `useQuery` hooks, not just the ones flagged in the original gap list.
- Vite/Rollup prod build: verify tree-shaking isn't defeated by any barrel-file (`index.ts` re-export) patterns in shared component directories — a common silent bundle-bloat cause in component libraries with 40+ components.

---

## 16. QA & TESTING — ENFORCEMENT, NOT JUST TOOLING (Spec §19, expands v1 §10)

Your infrastructure (Vitest unit/integration/mutation, Playwright E2E/chaos/a11y/responsive, k6 load, Oxlint/Stryker) is broader than most Series-A startups' — the gap to S-grade is **enforcement completeness and explicit coverage targets**, not more tools. This section replaces good intentions with numbers, file names, and CI gate configuration an agent can implement directly.

### 16.1 Coverage targets — explicit numbers, not "good coverage"

"Good test coverage" is not a spec an agent can verify against. These are:

| Layer | Tool | Target | Enforcement |
|---|---|---|---|
| Business logic (`src/lib/`, `src/utils/`, validation schemas, RBAC permission checks, i18n fallback logic) | Vitest | **90% statements / 85% branches** | Hard CI gate — build fails below threshold |
| React Query hooks (`src/services/queries.ts`, all `use*` hooks) | Vitest + Testing Library hook-testing pattern | **85% statements**, every hook has at least one success-path and one error-path test | Hard CI gate |
| UI primitives (`src/components/ui/*`, 17 components) | Vitest + Testing Library | **100% of components have at least one render test + one interaction test + one a11y assertion** (a presence check, not a %  — see 16.2) | Hard CI gate via a components-manifest script |
| Shared feature components (`src/components/shared/*`, ~25 components) | Vitest + Testing Library | **75% statements** | Soft gate (warns, doesn't block) for pre-existing components; hard gate for anything touched/added after this blueprint starts |
| Pages (`src/pages/**`) | Integration (Vitest + MSW) + E2E (Playwright) | Not measured by unit-coverage % — measured by **critical-path E2E presence** (16.4) instead, since page-level unit % is a weak signal for route components | E2E presence checklist, not a percentage |
| Overall repo statement coverage | Vitest `--coverage` | **≥ 80%** | Hard CI gate |
| Mutation score (Stryker) | Stryker | **≥ 70%** scoped to `src/lib/`, `src/services/`, `src/contexts/` (highest-value targets: auth, RBAC, i18n fallback, currency/date formatting) — do not chase mutation score on presentational components, low ROI there | Nightly run, score committed to `mutation-score.json`, PR bot posts delta vs. `main` |

**`vitest.config.ts` enforcement — hand this directly to the agent:**
```typescript
export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',
      thresholds: {
        statements: 80,
        branches: 75,
        functions: 80,
        lines: 80,
        // per-directory overrides for the higher-stakes layers
        'src/lib/**': { statements: 90, branches: 85 },
        'src/services/queries.ts': { statements: 85 },
        'src/contexts/auth-provider.tsx': { statements: 90, branches: 85 },
      },
    },
  },
});
```
If coverage drops below any threshold, `vitest run --coverage` exits non-zero — wire this exit code directly as the CI gate; don't rely on a human reading a report to catch drift.

### 16.2 UI primitive test manifest (closes the "17 components, unaudited" gap from §6.1)

Every hand-rolled primitive needs an explicit, named test file — not just "some tests exist somewhere." Create/verify this exact file list under `src/components/ui/__tests__/`:

```
avatar.test.tsx          → fallback initials, broken-image fallback, diacritic names (Ștefan, Ăgnes)
badge.test.tsx           → all variants render, contrast-safe class applied
breadcrumb.test.tsx      → aria-current="page" on last item, nested route rendering
button.test.tsx          → all 6 variants × 4 sizes render, disabled state, loading state, focus-visible ring present
callout.test.tsx         → variant="danger" has role="alert"
card.test.tsx            → hover class only applied when `interactive` prop is set
copy-button.test.tsx     → click copies to clipboard (mock navigator.clipboard), shows confirmation state
input.test.tsx           → error state wires aria-invalid + aria-describedby
loading-spinner.test.tsx → role="status", visually-hidden text present
pagination.test.tsx      → keyboard arrow navigation, current page aria-current
progress.test.tsx        → aria-valuenow/min/max present and correct
separator.test.tsx       → role="separator" or aria-hidden as appropriate
skeleton.test.tsx        → renders with the dimensions passed as props (regression guard for "shape must match content," §6.1)
tabs.test.tsx            → arrow-key navigation between tabs (WAI-ARIA tabs pattern), correct panel shown
tag.test.tsx             → contrast-safe class per category
tooltip.test.tsx         → opens on focus (not just hover), closes on Escape
```

**CI gate**: `scripts/verify-ui-test-manifest.ts` asserts every file in `src/components/ui/*.tsx` has a matching file in `__tests__/` — fails the build if a primitive is added or modified without its test file. This operationalizes "100% of components have at least one test" as an enforced rule instead of an unverified aspiration.

### 16.3 Feature → test-type matrix (explicit, no ambiguity about what "done" requires)

For every P0/P1 feature in this blueprint, this is the exact set of tests required before it can be marked done. Use this table as the literal per-feature checklist — an agent pastes back a ✅/file-path per cell, not a paragraph of prose.

| Feature | Unit | Integration (MSW) | E2E (Playwright) | A11y | Security |
|---|---|---|---|---|---|
| Token storage migration (§3.1) | Token never written to `localStorage`/`sessionStorage` post-migration (assert via a spy on `Storage.prototype.setItem`) | Refresh flow against a mocked httpOnly-cookie response | Full login → refresh → logout cycle | — | `tests/security/no-token-in-storage.spec.ts` |
| MFA (§3.4) | TOTP window-tolerance logic, backup-code single-use logic | Enroll → confirm → backup codes returned (mocked backend) | Enroll → logout → login with TOTP → login with backup code → verify used code rejected on reuse | Modal focus trap, QR alt text present | Rate-limit on `/mfa/verify` attempts |
| RBAC (§3.5) | `RequireRole` unit tests for every role in the permission matrix | Wrong-role user hits a gated query, gets 403 (mocked) | Each role logs in; verify the exact set of visible nav items/actions matches the matrix, per role | Focus never trapped in hidden/gated content | Server-side role check verified independently of the frontend guard (cross-reference the backend test here) |
| Stripe checkout (§4) | Plan-tier → price mapping logic | Checkout-session creation (MSW-mocked Stripe response) | Full upgrade flow to Stripe-hosted checkout (Stripe **test mode**, not fully mocked, for at least one real E2E run) | Return-from-checkout redirect doesn't trap focus | Network-tab assertion in Playwright: no card data ever appears in a request to your own domain |
| Device unification (§5) | Merged `DeviceInfo` type used consistently (a `tsd`-style type-level test) | List/search/filter logic against a mocked device list | Deactivate one device; bulk-deactivate 3 (2 succeed, 1 fails → correct summary toast) | Slide-over detail view is focus-trapped and Escape-closable | Deactivate action scoped to the acting user's own company (no cross-tenant deactivation possible) |
| i18n completeness gate (§7) | `scripts/i18n-audit.ts` unit-tested against fixture locale files (missing-key case, extra-key case, fully-covered case) | — | — | — | — |
| Notification bell (§9.1) | Unread-count calculation logic | `useNotifications` poll behavior (MSW + fake timers for the 30s interval) | Open dropdown, mark one read, mark all read, click-through navigates correctly | Dropdown keyboard-operable, unread count announced via `aria-live` | — |
| Onboarding auto-completion (§9.8) | Step-completion trigger logic per event type | Event → step marked complete (mocked) | Full flow: verify email → step 1 auto-ticks with no manual click | — | — |
| Audit log (§3.7) | Log-entry shape validation | Paginated fetch + filter logic | Admin views log, filters by actor/action/date | Table keyboard-navigable | Non-admin request to the endpoint returns 403 (explicit test) |

Treat this as a living table — add a row in this exact column structure for every new P1/P2 feature as it gets scoped.

### 16.4 Critical-path E2E inventory (explicit list — replaces "add E2E tests" as a spec)

These are the **must-exist, must-block-every-PR** flows — the minimum bar for calling the site launch-ready from a QA standpoint:

```
e2e/critical/auth-full-cycle.spec.ts        register → verify email → login → logout → login again
e2e/critical/auth-mfa-cycle.spec.ts         enroll MFA → logout → login with TOTP → backup-code fallback
e2e/critical/waitlist-conversion.spec.ts    land on home → click waitlist CTA → submit → see referral code
e2e/critical/rbac-boundaries.spec.ts        one sub-test per role, asserting exact visible/hidden nav + actions
e2e/critical/device-lifecycle.spec.ts       list devices → deactivate → verify removed from active list
e2e/critical/checkout-upgrade.spec.ts       (once §4 ships) starter → professional upgrade, Stripe test mode
e2e/critical/support-ticket-cycle.spec.ts   submit bug report → appears in My Tickets → status visible
e2e/critical/org-invite-cycle.spec.ts       invite teammate → accept invite (2nd browser context) → appears in member list
e2e/critical/password-reset-cycle.spec.ts   forgot password → reset link → new password → login with new password
e2e/critical/returnurl-redirect.spec.ts      hit a protected route unauthenticated → login → land back on original route, not /dashboard
```

This tier runs on **every PR** — deliberately smaller and faster than the full suite so it never slows the team down. Your existing broader suite (`public-navigation`, `v2/v3-navigation`, `docs-navigation`, full `responsive`, full `accessibility`, `chaos/*`) stays on a merge-to-main or nightly cadence (see 16.10 for exact pipeline placement).

### 16.5 Visual regression (new capability — not in your current test list)

- Tool: Playwright's built-in `toHaveScreenshot()` — no new dependency, you already run Playwright.
- Scope: Home, Pricing, Waitlist, Dashboard-overview, Login, and one representative Industry page — 6 pages × 3 viewports (375px, 768px, 1440px) × 2 themes (light/dark) = 36 baseline snapshots to start. Don't snapshot all ~50 public pages — that's a maintenance burden with low marginal signal; these 6 are your highest-traffic, highest-conversion, and most CSS-complex pages.
- CI behavior: a diff above a defined pixel-threshold (start at 0.1% to catch real regressions without flaking on anti-aliasing noise) fails the PR check and posts the diff image as a CI artifact for human review — this is a **soft gate requiring human sign-off**, not an auto-block, since legitimate intentional design changes will trigger it too.
- Baseline update process: a labeled PR comment (`/update-visual-baselines`) or a dedicated npm script run intentionally by whoever made the design change — never silently auto-accepted by CI.

### 16.6 Contract testing for the API layer (new — addresses the commented-out-endpoints risk directly)

Your `endpoints.ts` has `subscriptionApi`/`downloadApi`/`invoicesApi` currently commented out, about to go live per §4 — exactly the situation where frontend and backend silently drift on response shape. Add **MSW (Mock Service Worker)**-based contract tests:
- One handler file per API domain (`src/mocks/handlers/subscriptions.ts`, `devices.ts`, `auth.ts`, etc.) mirroring the exact response shape documented in `types/index.ts`.
- Integration tests run against these mocked handlers, so a shape mismatch between what the frontend expects and what the fixture provides is caught in CI, never in production.
- When a previously-mocked endpoint (billing, downloads) goes live for real: run a one-time **schema diff check** — capture a real staging response, diff its shape against the MSW fixture, update the fixture. This is the exact check that would catch the classic "backend ships `amount` as a string, frontend expects a number" bug before it reaches a real customer's invoice.

### 16.7 Load testing (k6) — explicit scenarios and pass thresholds

Your `stress/` directory exists but the dump doesn't name specific scenarios — make them explicit:

| Scenario | Load profile | Pass threshold |
|---|---|---|
| Login endpoint under load | Ramp 0→50 virtual users over 30s, hold 1min | p95 response time < 800ms, error rate < 1% |
| Dashboard initial load (auth + company + devices + licenses fetched in parallel) | 30 concurrent users | p95 < 1.5s, zero 5xx responses |
| Waitlist submission spike (e.g. a launch-day social post) | 0→200 users in 10s, hold 1min | p95 < 1s, error rate < 2%, **no duplicate-entry data corruption** under concurrent submits with the same email (explicit race-condition check) |
| Notification polling (30s interval, many concurrent sessions) | 200 concurrent polling sessions | No backend degradation — confirms the §9.1 poll interval is safe at expected launch scale |

Run the waitlist spike scenario specifically before any planned launch-day marketing push — it's the traffic pattern most likely to actually occur at a predictable moment and is cheap to rehearse in advance.

### 16.8 Flakiness policy (operational discipline, not just tooling)

- An E2E test that fails intermittently (not on every run) gets tagged `@flaky` and quarantined into a non-blocking CI job within 48 hours of the second observed flake — it does not get to silently erode trust in the whole suite by sitting there ignored.
- A quarantined test carries a tracked ticket and a **2-week SLA** to be fixed or deleted — a flaky test quarantined indefinitely is functionally equivalent to not having the test at all.
- Track flake rate as a real number (flaky runs / total runs per week). A rising flake rate is an early signal of test-environment instability (timing issues, unmocked network calls, shared test-data collisions) worth investigating before it compounds.

### 16.9 Test data & fixtures strategy

- Maintain seeded test accounts for **every role** (`owner`, `admin`, `manager`, `dispatcher`, `driver`) in one shared fixtures file, used consistently across E2E and integration tests — this directly powers the RBAC boundary tests in 16.3/16.4 and stops every test file from inventing its own ad-hoc test user.
- Isolate test data per run (unique email suffixes, e.g. `test+${runId}@operion.dev`) to avoid cross-run collisions on shared staging environments — increasingly important once waitlist/register E2E flows run on every PR (16.4).
- Never run destructive E2E tests (delete account, deactivate device, cancel subscription) against a shared staging environment without a dedicated, disposable test company/tenant per run — cross-contaminating test data with real staging data is a common, avoidable source of confusing "why did this break" debugging sessions.

### 16.10 CI pipeline — explicit stage order (fast-fail first)

```
1. Lint (Oxlint) + typecheck (tsc --noEmit)          — fails fast, seconds
2. Unit tests + coverage thresholds (16.1)            — Vitest
3. i18n completeness gate (§7)                        — scripts/i18n-audit.ts
4. UI test-manifest gate (16.2)                        — scripts/verify-ui-test-manifest.ts
5. Build (vite build)                                  — catches build-time errors before wasting time on E2E
6. Critical-path E2E (16.4)                            — every PR
7. Security regression suite (§3.9)                    — every PR
8. A11y suite (axe)                                    — every PR
9. Visual regression (16.5)                            — every PR, soft-gate
   ---- merge-to-main / nightly only, below this line ----
10. Full E2E suite (public-navigation, responsive, docs-navigation, chaos/*)
11. Load tests (16.7)                                  — nightly, or on-demand pre-launch
12. Mutation testing (Stryker, 16.1)                   — nightly, score tracked
```
Ordering is deliberate: cheap/fast checks (lint, typecheck, i18n gate) run first so a trivial mistake fails in seconds rather than after a 10-minute E2E run — a real developer-experience and CI-cost concern once the suite grows to the size implied by 16.3/16.4.

---

## 17. ANALYTICS & OBSERVABILITY (Spec §18, expands v1 §11)

- Move beyond GA4 page-views to **event-level** tracking: `waitlist_submitted`, `referral_shared`, `feature_interest_clicked` (§6.9), `onboarding_step_completed` (§9.8), `checkout_started`/`checkout_completed` (§4).
- Lightweight internal funnel view (even a lean `/admin/analytics` reading your own event table, or GA4 Explorations) for waitlist→register→active conversion visibility without waiting on a full BI tool.
- Error monitoring: Sentry (or equivalent) wired into the `ErrorBoundary` (§2.1) so production errors actually page/notify someone, not just show the user a graceful fallback silently.

---

## 18. ENVIRONMENT & DEPLOYMENT HARDENING (Spec §22 — not covered in v1)

- **Env vars**: verify `VITE_API_URL`, `VITE_GA_MEASUREMENT_ID` and any new ones (Stripe publishable key, Sentry DSN) are documented in a `.env.example` and never committed with real values — audit `.gitignore` covers all `.env*` variants.
- **Vite proxy** (`/api` → `api.operionerp.xyz`, dev-only CORS avoidance): verify this doesn't leak into a production build config by accident — prod must call the real API URL directly with correct CORS configured server-side, not rely on a proxy that only exists in dev.
- **Netlify `_redirects`**: verify SPA fallback doesn't swallow genuinely-missing-page 404s incorrectly (§13.4) and that it's updated to include the security `_headers` file from §3.6.
- **Cloudflare Workers (API)**: confirm Observability/logging is actually enabled and someone gets alerted on error-rate spikes — "tooling available" per your dump is not the same as "actively monitored."
- **TypeScript project references** (app + node configs): verify `strict: true` is enabled repo-wide, not just for new files — a common half-migrated state in growing TS codebases where legacy files opt out of strict checks silently.
- **CI/CD pipeline**: confirm the full test suite (§16) + the new i18n audit (§7) + security regression suite (§3.9) all run on every PR, not just on merge to main — catching issues at PR time is materially cheaper than post-merge.

---

## 18a. LEGAL, PRIVACY & COOKIE COMPLIANCE — TECHNICAL SPEC (genuine gap, not covered elsewhere)

Your dump documents Privacy/Terms pages and GA4 tracking, but nothing about **consent gating** — for an EU-based company collecting emails on a public waitlist and running GA4/GTM, this is a real compliance gap, not a nice-to-have.

### 18a.1 Cookie consent banner + Google Consent Mode v2

- Add a lightweight consent banner (you don't need a heavy CMP vendor at this stage — a custom component fits your existing design system fine): **Accept all / Reject non-essential / Customize**, with categories **Necessary** (session/CSRF cookies — always on, no toggle), **Analytics** (GA4), **Marketing** (none currently, but leave the category scaffolded for future ad-pixel use).
- Technical mechanism: gate the GTM/GA4 script injection behind a consent check — do not fire `gtag('config', ...)` until consent is granted. If you use Google's tags at all, implement **Google Consent Mode v2** explicitly (`gtag('consent', 'default', { analytics_storage: 'denied', ad_storage: 'denied' })` on load, then `gtag('consent', 'update', {...})` on the user's actual choice) — this is the mechanism Google now expects, and skipping it risks GA4 data being flagged/discarded for EU traffic regardless of your own banner.
- Store the consent choice (cookie or localStorage, non-sensitive) with a timestamp and re-prompt after a reasonable period (e.g., 6–12 months) or on a documented policy version bump.

### 18a.2 Cookie Policy page (separate from Privacy Policy)

Build this from an **actual cookie audit** of the deployed site (session cookie, CSRF cookie, GA4 `_ga`/`_gid`, referral-tracking cookie if one exists) rather than generic boilerplate — list name, purpose, duration, and category per cookie in a real table. Generic "we may use cookies" copy is a common and easily-spotted compliance shortcut; a specific, accurate table is both more compliant and a small trust signal.

### 18a.3 Accessibility statement page

A short, dedicated page stating your target conformance level (WCAG 2.1 AA, matching the axe-enforced bar in §16), known limitations if any, and a contact channel for accessibility issues. This is increasingly expected for B2B procurement (some enterprise/public-sector buyers require it explicitly) and costs little once §6.3's actual a11y work is done — it's just honestly documenting what you've already built.

### 18a.4 Data retention, backup, and DPA availability (mostly backend/ops, but the website must state it accurately)

- Document real retention periods once decided: `audit_log` (§3.7) retention window, the 14-day grace period for account deletion (§10.2), backup frequency/RPO/RTO for the underlying database. This is backend/infra work, but whatever the real numbers are, the Security/Trust Center pages (§11.8/§11.16) must state them accurately rather than vaguely — since your active TIMOCOM/Trans.eu/Alpega partnership conversations will very plausibly involve a security questionnaire asking exactly this.
- Add a downloadable **Data Processing Agreement (DPA)** template link on the Enterprise/Trust page — standard ask from any EU B2B enterprise buyer before they'll sign; having it ready before it's asked for is a small credibility edge in exactly the partnership conversations you're already having.

---

## 18b. ANTI-ABUSE, SPAM PROTECTION & WEBHOOK RELIABILITY (genuine gap, not covered elsewhere)

### 18b.1 Bot protection on public forms

Your dump mentions a honeypot field on the waitlist form — good first layer, but honeypots alone are trivially bypassed by any semi-competent scraper/bot, and a launch-day traffic spike (§16.7) is exactly when spam-bot signups are most likely to hit the waitlist. Add **Cloudflare Turnstile** (pairs naturally if you're already on Cloudflare Pages/Workers; more privacy-friendly than reCAPTCHA and doesn't require a Google dependency) as an invisible challenge on Waitlist, Contact, and Newsletter forms, escalating to a visible challenge only when Turnstile's own risk score flags a request — keeps the low-friction UX v1's §7 waitlist rework depends on while closing the actual bot gap.

### 18b.2 Referral fraud prevention

Once the referral mechanic (v1 §7.2) has a real reward attached ("move up N spots," "X months free"), it becomes worth gaming. Minimum viable protections: reject a referral where referrer and referee emails share the exact same address or an obviously identical local-part+domain pattern; rate-limit redemptions per referral code per day (catches obvious script-based abuse without penalizing genuine organic sharing); log referral redemptions through the same `audit_log` mechanism (§3.7) so abuse patterns are at least visible after the fact even if not blocked in real time on day one.

### 18b.3 Stripe webhook reliability (directly relevant once §4 ships)

- **Always verify the webhook signature** (`stripe.webhooks.constructEvent` with your webhook signing secret) before processing any event — never trust an unsigned payload hitting your webhook endpoint, since the URL itself is not a secret.
- **Idempotency**: Stripe retries webhook delivery on any non-2xx response, and can also legitimately send the same event twice. Your webhook handler must be idempotent (upsert on `stripe_event_id`, or check-then-skip on already-processed events) — a non-idempotent handler double-issuing a fiscal invoice (§4.1) on a retried webhook is a real, embarrassing failure mode for exactly the compliance-sensitive billing flow you're building.
- Use Stripe's **idempotency keys** on your own outbound requests (creating Checkout Sessions, Payment Intents) so a network retry from your own frontend/backend doesn't create a duplicate session/charge.

### 18b.4 Rate limiting — extend beyond login (cross-reference to §3.8)

§3.8 already flags login rate-limiting as a P0 backend gap. Extend the same discipline explicitly to: **password-reset requests** (prevent email-bombing a target's inbox by repeatedly triggering reset emails), **support-ticket submission** (prevent spam-ticket flooding of your support queue, especially once Live Chat/AI Assistant §10.3 is live and easier to hit programmatically), and **waitlist/newsletter submission** (complements 18b.1's bot protection — rate-limiting by IP is a cheap second layer even with Turnstile in place).

---

## 18c. BROWSER SUPPORT, FILE-UPLOAD SAFETY & PWA ASSETS (closes remaining small-but-visible gaps)

### 18c.1 Explicit browser support matrix

Nothing in your dump states which browsers are actually supported — "modern browsers" is not a spec an agent (or a QA suite) can verify against. Add a `.browserslistrc` (or `browserslist` field in `package.json`) with an explicit target, e.g.:
```
last 2 Chrome versions
last 2 Edge versions
last 2 Firefox versions
last 2 Safari versions
not dead
```
This single config drives Vite's build target *and* any CSS autoprefixing consistently, and gives you a concrete, testable answer when a dispatcher reports a bug on an older in-cab tablet browser — you'll know immediately whether it's in scope.

### 18c.2 File-upload safety (extends §9.6's avatar-persistence fix with the security dimension it was missing)

Once avatar upload actually persists (§9.6), it becomes a real attack surface, not just a UX fix:
- **Server-side file-type validation via magic-byte sniffing**, not just trusting the client-sent MIME type or file extension (both are trivially spoofable).
- **Max file size enforced on both client and server** (client-side for UX speed, server-side because the client check is not a security boundary).
- **Re-encode uploaded images server-side** (strip EXIF metadata in the process) — beyond the security benefit, this closes a real privacy leak, since photos taken on a phone frequently embed GPS coordinates in EXIF data that would otherwise be stored and potentially served back verbatim.
- If your backend infrastructure supports it, run a virus/malware scan (ClamAV or a cloud scanning API) on uploaded files before they're persisted to storage — a reasonable bar for a B2B product handling company accounts, even if the current attack surface is "just an avatar."

### 18c.3 Favicon & PWA manifest completeness

Verify the full icon set exists (16×16, 32×32, 180×180 for iOS home-screen, 192×192 and 512×512 for Android/PWA, plus a maskable-icon variant) and that `site.webmanifest` has correct `theme_color`/`background_color` matching your actual OKLCH brand tokens (§6.3) rather than defaults. A missing or generic favicon is a small thing, but it's one of the most visible "this wasn't finished" signals — visible in every browser tab, every bookmark, and every link preview.

### 18c.4 Print stylesheet

Add a `@media print` stylesheet for anything a user would plausibly print: invoices (once §4 ships), Terms/Privacy pages, and any contract-like content. Without this, a dark-mode invoice prints as white text on a black background wasting a full page of ink — an easy, cheap fix (`color-scheme: light` forced within `@media print`, hide nav/footer/sidebar chrome) that a B2B customer printing an invoice for their own accounting records will actually notice if it's missing.

---

## 19. FILE-LEVEL CHANGE MAP (complete reference)

| File/Area | Current issue | Spec section |
|---|---|---|
| `src/contexts/auth-provider.tsx` | localStorage tokens, no MFA state, no returnUrl, no remember-me | §3.1, §3.4, §9.2, §9.3 |
| `src/api/client.ts` | Bearer from localStorage, no cookie support | §3.1 |
| `src/components/auth/protected-route.tsx` | No RequireRole, no returnUrl | §3.5, §9.2 |
| `src/pages/dashboard/dashboard.tsx` | 100% mock stats/activity/announcements | §9.5 |
| `src/pages/dashboard/subscription.tsx` | 100% mock, disabled actions, tier-based UI that doesn't match the real per-truck model | §4.5 |
| `src/pages/dashboard/billing.tsx` | 100% mock invoices/payment/tax | §4.5 |
| `src/pages/dashboard/devices.tsx` | Duplicated device concepts, no search/detail/bulk | §5 |
| `src/pages/dashboard/licenses.tsx` | mockDevices, disabled deactivate | §5.2 |
| `src/pages/dashboard/company.tsx` | Hardcoded team/dept stats, disabled logo/edit | §10.1, §3.5 |
| `src/pages/dashboard/profile.tsx` | Avatar doesn't persist, disabled notif save | §9.6, §9.7 |
| `src/pages/dashboard/settings.tsx` | Multiple disabled/"coming soon" tabs | §10.2, §6.9 |
| `src/pages/dashboard/onboarding.tsx` | Hardcoded checklist + tutorials + releases despite live APIs | §9.8, §10.4 |
| `src/pages/dashboard/downloads.tsx` | Hardcoded config, "TBD" size | §4.5 |
| Desktop ERP Fleet Manager (cross-repo) | No shared subscription-state integration yet — truck cap/"Add to subscription" flow doesn't exist | §4.2, §4.4 |
| `src/pages/dashboard/support.tsx` | Live Chat/AI Assistant "Coming Soon" | §10.3 |
| `src/pages/public/waitlist.tsx` | Needs narrative rework | v1 §7 (unchanged) |
| `src/pages/public/home.tsx` | Screenshot placeholders, single CTA point | §6.6, §6.7, §11.1 |
| `src/pages/public/features.tsx` | Screenshot placeholders, templated sections | §6.6, §11.2 |
| `src/pages/public/pricing.tsx` | JSON-LD only Product+FAQ | §14.1 |
| `src/pages/public/industries/*` (7 pages) | Risk of templated thin content | §11.18 |
| `src/api/endpoints.ts` | subscriptionApi/downloadApi/invoicesApi commented out; duplicated DeviceInfo | §4.4, §5.2 |
| `src/types/index.ts` | DeviceInfo duplicated | §5.2 |
| `src/components/shared/cookie-consent-banner.tsx` (new) | Doesn't exist — GA4/GTM fire unconditionally | §18a.1 |
| `src/pages/legal/cookie-policy.tsx` (new) | Doesn't exist, only Privacy/Terms | §18a.2 |
| `src/pages/legal/accessibility-statement.tsx` (new) | Doesn't exist | §18a.3 |
| Waitlist/Contact/Newsletter forms | Honeypot only, no real bot protection | §18b.1 |
| Referral redemption logic | No fraud/self-referral checks | §18b.2 |
| Stripe webhook handler (backend) | Needs signature verification + idempotency once §4 ships | §18b.3 |
| `browserslist` / `.browserslistrc` | Doesn't exist — no explicit supported-browser target | §18c.1 |
| Avatar upload endpoint (backend) | No magic-byte validation, EXIF stripping, or size enforcement server-side | §18c.2 |
| `public/manifest.webmanifest`, favicon set | Likely incomplete/default icons | §18c.3 |
| Invoice/legal page stylesheets | No `@media print` handling | §18c.4 |
| `src/config/site.ts` | downloadConfig placeholder values | §4.4 |
| `src/i18n/*.json` (6 files) | Completeness drift risk, no CI gate | §7 |
| `src/components/ui/*` (17 components) | Individual a11y gaps | §6.1 |
| `src/components/shared/*` (~25 components) | Targeted fixes per component | §6.2 |
| `src/components/layout/app-shell.tsx` | Path-prefix layout switch, nav-highlighting edge cases | §2.2, §2.3 |
| `src/config/navigation.ts` | No badge support for RBAC/new-feature flags | §2.3 |
| `src/main.tsx` | No Sentry/error reporting wired to boundary | §2.1, §17 |
| Netlify/Cloudflare config | No security headers, `_redirects` 404 handling unverified | §3.6, §13.4, §18 |
| `.env.example` / CI config | Unverified secret hygiene, missing i18n/security gates | §18, §16 |

---

## 20. PHASED ROADMAP

### 🔴 P0 — This week, before any feature work
1. Security headers/CSP (§3.6) — pure config.
2. Interim token-storage mitigation to sessionStorage + backend ticket for httpOnly cookie migration (§3.1).
3. File the rate-limiting backend ticket if it doesn't already exist (§3.8).
4. Triage every D/F-graded item per §1's three-way disposition — planning task, do before more UI code.
5. `ro.json` i18n completeness audit specifically (§7) — your primary launch market.
6. Cookie consent banner + Google Consent Mode v2 (§18a.1) — you are actively collecting emails and running GA4 on EU traffic today; this is a live compliance gap, not a future one.
7. Turnstile bot protection on Waitlist/Contact/Newsletter forms (§18b.1) — cheap, and a launch-day traffic spike is exactly when spam signups hit hardest.
8. Hand the §11.7 Privacy Policy content brief to counsel now — it's a long lead-time item (Gmail API scope review, sub-processor confirmation) and shouldn't be started the week of launch.

### 🟠 P1 — Pre-launch (Sept 1 target)
6. Dashboard real stats (§9.5) — highest-visibility fakery.
7. Onboarding checklist + tutorials + releases → real APIs (§9.8, §10.4).
8. Device management unification (§5) — endpoints already exist, frontend-only.
9. Frontend wiring batch: notification bell (§9.1), returnUrl (§9.2), password strength (§9.4), avatar persistence (§9.6), notification prefs (§9.7).
10. Waitlist narrative rework + real home/features screenshots (v1 §7, §6.7).
11. RBAC/Team unification on Company/Organizations (§3.5) — needed before onboarding the family-member MVP tester's team; resolve the driver-credentials-vs-email-invite split per §4.7.
12. `<RoadmapFeature>` component rollout across every "Coming Soon" instance, with Delete Account/Data Export getting at minimum the ticket-based honest-defer flow (§10.2, §6.9).
13. SEO technical checklist + structured data (§14.1, §14.2) — cheap relative to impact.
14. Login/Register hardening: rate-limit-aware errors, Terms/Privacy consent checkbox verification, single-use/short-lived reset tokens, email-enumeration prevention (§8).
15. Company page cleanup: remove or build real Departments, wire logo/edit (§10.1).
16. Error/edge pages verified real and on-brand (§13).
17. Favicon/PWA manifest completeness + `.browserslistrc` explicit support matrix (§18c.1, §18c.3) — cheap, visible-quality items.
18. Cookie Policy page built from a real cookie audit + Accessibility Statement page (§18a.2, §18a.3).
19. Rate limiting extended to password-reset and support-ticket submission, not just login (§18b.4).
20. **Per-truck billing core build (§4.1–§4.5, §4.7)** — this is now fully specified (unlike the earlier generic-tier model) and is realistically buildable pre-launch if backend capacity allows: schema, shared API contract between desktop Fleet Manager and website, real Subscription/Billing pages, free-trial lockout + 4-day notice banner. If the desktop↔website sync can't finish in time, ship the honest-defer fallback in §4.8 (real read-only subscription state, manual truck-addition process) rather than the old fake-tier stub.
21. Confirm the AI-Copilot billing toggle scope (company-wide vs. per-truck, §4.1) before building — this decision changes the schema and desktop UI, resolve it early in the P1 window, not mid-build.

### 🟡 P2 — Launch window / weeks after
22. Webhook signature verification + idempotency (§18b.3) ships alongside the P1 billing build, not as an afterthought, once Stripe is actually wired.
23. **AI-driven payment-leniency feature (§4.6)** — explicitly held for legal/accounting review; do not build ahead of that sign-off regardless of how ready the core billing work is.
24. MFA (§3.4) — high-value, backend-dependent, target within weeks of launch given the stakes for an ERP holding fleet/financial data.
25. Audit log (§3.7).
26. Live Chat/AI Assistant tied into `operion-ops`/ARGO infrastructure rather than built separately (§10.3).
27. Design-system component-level audit pass (§6.1-§6.5) — after functional gaps close, not before.
28. Prerendering for public routes (§2.2) — biggest single SEO lever available.
29. Server-side avatar/file-upload hardening: magic-byte validation, EXIF stripping, size limits, virus scan if infra allows (§18c.2).
30. Referral-fraud checks once a real reward mechanic is attached to referrals (§18b.2).
31. Data retention/backup/DPA documentation finalized and reflected accurately on Security/Trust/Enterprise pages (§18a.4) — relevant to your active TIMOCOM/Trans.eu/Alpega conversations.

### 🟢 P3 — Post-launch hardening
32. PWA support, device geolocation/health indicators, admin cross-tenant device view, WebSocket real-time updates.
33. Visual regression test suite, analytics event dashboard, Stryker mutation-score tracking.
34. Full i18n completeness for the remaining 4 non-Romanian, non-English locales if not already done at P0.
35. Trust Center/Security page content refresh reflecting shipped security features (§11.8, §11.16).
36. Print stylesheet for invoices/legal pages (§18c.4) — low priority until real invoices exist per §4.

---

## 21. MASTER DEFINITION OF DONE (paste into every agent prompt, unchanged discipline from your existing pattern)

- [ ] No mock/hardcoded data remains where a real API call is possible — or the gap is explicitly honest-deferred via `<RoadmapFeature>` (§6.9), never silently missing.
- [ ] `t()` i18n compliance in all 6 locale files, verified by the CI audit script (§7), not just `en.json`.
- [ ] Design-token/CSS-variable usage only — no hardcoded hex colors introduced.
- [ ] A failing test existed before the fix; a passing test exists after — pasted as proof.
- [ ] Loading, empty, and error states all implemented — not just the happy path.
- [ ] Toast feedback on every mutation (success and failure), routed through the global `onError`/`onSuccess` handlers (§2.1) where possible rather than ad-hoc per-hook.
- [ ] Keyboard-accessible, passes the `axe` a11y suite with zero new violations, focus rings visible on all interactive elements touched.
- [ ] No new console errors/warnings in dev or prod build.
- [ ] Mobile responsive at 375px, verified via Playwright responsive suite — no horizontal scroll on any data table.
- [ ] Security regression suite still passes (§3.9) — no feature reintroduces a fixed vulnerability class.
- [ ] RBAC-gated features verified server-side, not just frontend-hidden (§3.5).
- [ ] Any new form (public-facing or authenticated) has bot/abuse protection appropriate to its risk (§18b), and any new cookie/tracking behavior is gated by consent state (§18a.1).
- [ ] Any new file-upload path validates type/size server-side and strips sensitive metadata before storage (§18c.2).

---

*End of v2. This document supersedes v1 in full; work through §20 in order, and hand each numbered sub-section above to a coding agent as its own self-contained prompt once you reach it in the roadmap.*
