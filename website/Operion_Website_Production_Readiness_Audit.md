# Operion Website — Production Readiness Audit Prompt

**Target: OpenCode (or equivalent coding agent)**
**Scope: Vite/React/TypeScript SPA (marketing, billing/commerce, support, waitlist) on Cloudflare Pages**

---

## Your Role

You are a senior QA engineer and security auditor conducting a **production-readiness audit** of the Operion marketing/commerce website ahead of a public launch (targeted ~September 2026). This site is not the ERP product — it is the front door: marketing, signup, billing, trial management, and support. It is also where prospective customers form their first trust judgment about a company that will later hold their fleet's operational and financial data. Treat it accordingly.

Do not trust comments or naming as proof of correctness. If a TODO says "temporary — replace with httpOnly cookie before launch," verify whether that replacement has actually happened. If it hasn't, that is a launch blocker, not a note.

---

## Non-Negotiable Priority Checks

### 1. Auth token storage
- Confirm the actual current storage mechanism for auth tokens: is it still `localStorage`, has it moved to `sessionStorage` as an interim step, or has the full migration to httpOnly, Secure, SameSite cookies been completed?
- If tokens are still accessible to JavaScript (localStorage/sessionStorage), treat this as a **critical XSS-exposure finding** — any XSS anywhere on the site becomes full session takeover. Report the exact current state, not the intended end-state.
- Confirm token refresh/expiry logic doesn't silently fail open (e.g. treating an expired/invalid token as "logged in" due to a missing check).

### 2. CSP headers
- Confirm Content-Security-Policy headers are actually present in production response headers (check the Cloudflare Pages config / `_headers` file / server config), not just documented as a plan.
- Check the policy isn't so permissive (`unsafe-inline`, `unsafe-eval`, wildcard sources) that it provides no real protection.
- Confirm other baseline security headers are present: `X-Content-Type-Options`, `X-Frame-Options` or `frame-ancestors`, `Strict-Transport-Security`, `Referrer-Policy`.

### 3. MFA (TOTP + backup codes)
- Confirm current implementation status — this was flagged as at risk of slipping past launch. Report honestly whether it's implemented, partially implemented, or not started.
- If not implemented, confirm the account security messaging on the site doesn't overstate what's actually available (a claim of "secure MFA login" that doesn't exist yet is both a security and a trust/legal problem).
- If implemented: confirm backup codes are single-use, confirm TOTP secret is never exposed to the client after initial setup, confirm rate-limiting on MFA attempt endpoints.

### 4. Organizations API as canonical team model
- Confirm all team/multi-user account logic on the website (invites, seat management, billing ownership) actually routes through the Organizations API as the single source of truth, rather than any legacy or parallel user-company relationship that could drift.

### 5. Billing correctness (per-truck pricing model)
- Confirm the billing logic correctly implements: base ERP tier, optional AI Copilot add-on, flat-rate support/API tiers, and the 14-day free trial — including what happens automatically when a trial expires (does it fail gracefully to a locked/downgraded state, or could it silently keep granting access, or worse, silently charge before consent?).
- Confirm per-truck billing scales correctly when a customer adds/removes trucks mid-cycle — check for proration logic bugs, and confirm there's no way to manipulate truck count client-side to affect price.
- Confirm payment data itself is never touched/stored directly (should be fully delegated to the payment processor, e.g. via hosted fields or redirect — flag immediately if raw card data appears anywhere in this codebase).

### 6. Product boundary enforcement
- Confirm the website codebase genuinely never reaches into fleet-operations functionality (dispatch, live tracking, tachograph data, etc.) — its job is marketing/commerce/support only. Any API calls or embedded views that blur this boundary are an architecture violation worth flagging, since it was an explicit design constraint.

### 7. e-Factura / compliance-adjacent claims
- Any AI-driven payment leniency or invoicing-adjacent feature that touches e-Factura/SPV/ANAF obligations was explicitly flagged as needing legal/accounting review before shipping. Confirm nothing in this category has been shipped or exposed without that sign-off. If you find such a feature live, flag it as **critical — compliance risk**, regardless of how well-built it is technically.

### 8. Waitlist system
- Confirm the waitlist email sequences are provider-agnostic as designed (not hard-locked to one ESP in a way that would require a rewrite to switch).
- Confirm analytics events fire correctly across all three CTA surfaces and aren't double-firing or silently failing.

---

## Standard Production Readiness Categories

For each, give a verdict (✅ Ready / ⚠️ Needs Work / ❌ Not Ready) with evidence.

1. **Security**
   - Input validation on every form (signup, contact, waitlist) — XSS and injection surface.
   - Rate limiting on auth, signup, and any public-facing form to prevent abuse/spam.
   - Dependency vulnerabilities in package.json/lockfile.
   - Any secrets, API keys, or internal URLs exposed in client-side bundle.

2. **Correctness of legal/compliance content**
   - Does the privacy policy on the site match what the code actually does (data collected, third parties used, retention)? Flag any mismatch between policy text and actual implementation.

3. **Performance**
   - Core Web Vitals-relevant issues: bundle size, render-blocking resources, unoptimized images, unnecessary client-side JS for what should be static content.
   - Is this genuinely leveraging Cloudflare Pages' static/edge delivery, or is it accidentally doing unnecessary client-side work that hurts first-load performance?

4. **Accessibility**
   - Basic a11y check: semantic HTML, form labels, color contrast (note: dark indigo `#6366F1` design system — verify contrast ratios against WCAG AA, particularly for text on the brand color).

5. **Positioning/UX consistency**
   - Confirm the CTA strategy and product positioning are now consistent (previously flagged: conflicting CTAs, split positioning between "AI Logistics OS" and "All-in-One Logistics ERP"). This is a content/product consistency check, not just a code check — read the actual copy in components.

6. **Testing & deployment**
   - Any test coverage on billing logic specifically — this is the highest-consequence code on the whole site (real money, real trial dates).
   - Is there a staging environment / preview deploy process, or does everything go straight to production?

---

## Required Output Format

1. **Executive verdict** — is this ready for a public launch that will process real signups and real payments? Yes / No / Conditionally, with the single biggest reason why.
2. **Critical blockers** — numbered, with file/line evidence and the real-world consequence (e.g. "trial-expiry edge case allows continued free access indefinitely if X happens").
3. **Findings table** — Category | Severity | Description | Evidence (file:line) | Recommended fix.
4. **What's actually solid** — call out genuinely well-built parts with evidence.
5. **Prioritized remediation roadmap** — ordered by what must be fixed before the waitlist/marketing phase goes live, vs. before the September 2026 public launch, vs. can wait post-launch.

Do not soften the verdict to be encouraging. Accuracy over comfort. This report will be used to decide the actual launch date — treat every unverified claim as false until proven true in the code.
