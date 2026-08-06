# Security

This file documents tracked security exceptions and posture. Every item below was
explicitly evaluated; none is an unnoticed gap.

## React Router GHSA-qwww-vcr4-c8h2 (CVE-2026-28757)

The app pins `react-router@7.18.2`. The advisory is **not exploitable here**:
it affects only unstable RSC APIs in React Router framework mode, while Operion is a
Vike-SSR + client-side React Router SPA with no RSC usage. No 7.x backport exists;
the fix landed only in 8.3.0, a major bump. v8 migration is deferred to a post-launch
maintenance window and tracked as a known upgrade.

## Turnstile verification policy

Server-side validation (Cloudflare siteverify) runs on waitlist, registration,
contact, newsletter, and login endpoints via `backend/services/turnstile.py`.

- **Token present → fail closed.** Any token that cannot be verified (missing secret,
  network error, non-200, invalid token) is rejected with HTTP 400.
- **Token absent → fail open by default.** Desktop/mobile ERP clients cannot render
  the widget; rejecting them would break launch.
- **`REQUIRE_TURNSTILE=1` → fail closed on absent token.**

Recommendation: enable `REQUIRE_TURNSTILE=1` post-launch once every web flow ships
the widget, and consider per-endpoint toggles (web vs ERP clients).

## CSP tradeoff

`public/_headers` ships a tightened `Content-Security-Policy`, but retains
`style-src 'unsafe-inline'` because motion/react and Tailwind set inline styles at
runtime. All other directives are restricted (`object-src 'none'`, `base-uri 'self'`,
`frame-ancestors 'none'`, etc.).

## Session storage for refresh tokens

Refresh tokens are kept in `sessionStorage` (see `src/api/client.ts`) as an interim
measure from the security audit; this avoids persisting them in `localStorage`.
Migration to httpOnly cookies is a documented follow-up.

## Reporting vulnerabilities

Report security issues to `contact@operionerp.xyz`. Do not open public issues for
live vulnerabilities; coordinate disclosure first.
