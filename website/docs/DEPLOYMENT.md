# Deployment — Cloudflare Pages

This document describes how the Operion website is built, deployed, and verified.
Deployments are driven by GitHub Actions (`.github/workflows/deploy.yml`) and hosted
on **Cloudflare Pages**.

> **⚠️ LAUNCH BLOCKER — READ FIRST**
> The production domain is **https://operionerp.xyz** — the zone IS in the Cloudflare
> account (it hosts `api.operionerp.xyz`) and the Pages project `operion-website`
> exists, but **no successful deployment has landed yet** (pages.dev returns 522 as
> of 2026-08-06) and the GitHub secrets/variables are not configured. Until that is
> done, **nothing is live on operionerp.xyz**.
> See [Known gaps & pre-launch checklist](#known-gaps--pre-launch-checklist).

---

## Table of contents

1. [Build & deploy commands](#1-build--deploy-commands)
2. [One-time Cloudflare setup](#2-one-time-cloudflare-setup)
3. [How deployments work](#3-how-deployments-work)
4. [Headers & redirects](#4-headers--redirects)
5. [Security headers](#5-security-headers)
6. [Rollback](#6-rollback)
7. [Known gaps & pre-launch checklist](#7-known-gaps--pre-launch-checklist)
8. [Verification checklist](#8-verification-checklist)

---

## 1. Build & deploy commands

```bash
npm ci                 # install dependencies (exact versions from lockfile)

npm run build          # = `tsc -b && sitemap && og-images && vike build`
                       #   type-checks, then vike statically renders the app
                       #   OUTPUT: dist/client/  (this is what gets deployed)

npm run lint           # oxlint
npm run typecheck      # tsc --noEmit (type-check only, no emit)

npm run preview        # serve the local dist/ build to sanity-check it
```

The deploy pipeline runs `npm ci` → `npm run lint` → `npm run build`, then uploads
**`dist/`** to Cloudflare Pages. There is no manual upload step — `git push` triggers it.

## 2. One-time Cloudflare setup

> **Status (2026-08-01):** the Pages project **`operion-website`** already exists in
> the Cloudflare account (subdomain `operion-website.pages.dev`, production branch
> `main`, build `npm run build`, output **`dist/client`**), and `operionerp.xyz` is the
> intended production domain (its zone is already in the account — it hosts
> `api.operionerp.xyz`). Remaining manual steps: **GitHub secrets/variables (steps 2–3)**,
> **custom-domain attachment + DNS verification (step 4)**, and the first successful
> deployment.

1. **Create a Cloudflare Pages project** — **already done** (name: `operion-website`)
   - Dashboard: **Workers & Pages → Create → Pages → Connect to GitHub**, or
   - CLI: `npx wrangler pages project create operion-website`
   - If the project ever needs recreating, it can be created "empty" (no production
     branch attached yet) — the workflow will deploy to it on the first run.

2. **Add GitHub repository secrets** (Settings → Secrets and variables → Actions → **Secrets**)
   | Secret | Value |
   | --- | --- |
   | `CLOUDFLARE_API_TOKEN` | Cloudflare API token with **Cloudflare Pages → Edit** permission |
   | `CLOUDFLARE_ACCOUNT_ID` | Your Cloudflare account ID (dashboard URL, or Cloudflare → Overview right sidebar) |

3. **Add a GitHub repository variable** (Settings → Secrets and variables → Actions → **Variables**)
   | Variable | Value |
   | --- | --- |
   | `CLOUDFLARE_PAGES_PROJECT` | Exact name of the Pages project from step 1 |

4. **Attach the production domain** (Cloudflare Pages → `<project>` → **Custom domains**)
   - Add `operionerp.xyz` (and `www.operionerp.xyz` if used) as a custom domain.
   - Cloudflare will show you the DNS records to create (CNAME `operionerp.xyz` → `<project>.pages.dev`).
   - **This requires the `operionerp.xyz` zone to be in the Cloudflare account first** —
     it currently is not (see [Known gaps](#7-known-gaps--pre-launch-checklist)).

> Notes:
> - Do **not** hardcode the project name in the workflow — it is read from the
>   `CLOUDFLARE_PAGES_PROJECT` repo variable so it can be fixed in one place.
> - The workflow file also documents this setup in its header comment, so it travels
>   with the repo.

## 3. How deployments work

Triggered by `.github/workflows/deploy.yml`:

| Event | Deployment | Result |
| --- | --- | --- |
| `push` to `main` | **Production** | Deployed to `<project>.pages.dev` and, once configured, to `operionerp.xyz` |
| `pull_request` | **Preview** | Deployed to a unique `<hash>.<project>.pages.dev` URL; the PR gets a check/status link |
| `workflow_dispatch` | Manual | Uses the current default branch (production) |

**Preview workflow for reviewers:**

1. Open a PR against `main`.
2. The workflow builds the branch and Cloudflare Pages publishes a **preview URL**
   (shown in the PR's checks / `pages-action` deployment status).
3. Reviewers test the real rendered site (routes, i18n, headers) before merge.

**Production:**

1. Merge to `main`.
2. `pages-action` uploads `dist/` with `branch: main` → production deployment.
3. Production domain serves the latest deployment; `_headers`/`_redirects` apply automatically.

## 4. Headers & redirects

Cloudflare Pages picks up two special files from `public/` (they are copied into
`dist/client/` by the build) — **no configuration required**:

- **`public/_headers`** — per-path HTTP headers, applied to every deployment.
  Currently defines the full security header set (see next section) plus `/_headers`
  itself.
- **`public/_redirects`** — rewrite/redirect rules. Currently:
  ```
  /*    /index.html   200
  ```
  This is the SPA fallback: every unknown path serves `index.html` (which the client
  router then resolves), so deep links and hard refreshes work.

Changing either file only needs a commit + push; the next deploy applies it.

## 5. Security headers

Headers ship from **`public/_headers`** and are enforced by the edge on every response:

| Header | Value shipped |
| --- | --- |
| `Content-Security-Policy` | `default-src 'self'; …` (Google Tag Manager, Turnstile, Google Analytics, operion APIs allowed) |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=(), payment=(self)` |
| `Cross-Origin-Opener-Policy` | `same-origin` |
| `Cross-Origin-Resource-Policy` | `same-site` |

If the CSP must change (e.g. a new third-party script), edit `public/_headers`,
commit, and let the next deploy apply it — no manual cache/edge refresh needed.

## 6. Rollback

Cloudflare Pages keeps a deployment history. To roll back:

**Dashboard:** Workers & Pages → `<project>` → **Deployments** → ⋯ → **Rollback to this deployment**.

There is no automatic rollback; a bad merge is reverted via a normal `git revert` + push.

## 7. Known gaps & pre-launch checklist

Verified gaps at audit time (2026-08-06, see *OPERION_Production_Readiness_Audit.md*):

- ❌ No successful deployment has landed — pages.dev returns 522 (project exists, origin empty).
- ❌ GitHub secrets/variables not configured (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_PROJECT`).
- ❌ Custom-domain/DNS state for `operionerp.xyz` unverified (zone is in the account).

**What must happen before launch:**

- [ ] Verify the Pages project and connect the GitHub repo (or wire the workflow's API token).
- [ ] Add secrets `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` and variable
      `CLOUDFLARE_PAGES_PROJECT` in GitHub repo settings.
- [ ] Attach `operionerp.xyz` as a custom domain on the Pages project and point DNS
      (CNAME `operionerp.xyz` → `<project>.pages.dev`).
- [ ] Merge a change to `main` and confirm a **production** deployment succeeds.
- [ ] Confirm a PR produces a **preview** URL.
- [ ] Run the [verification checklist](#8-verification-checklist) against the live domain.

> Until steps above are done, deployments only appear on `<project>.pages.dev`
> (and preview hashes) — the production domain will not respond.

## 8. Verification checklist

After deploying, verify the production domain directly (adjust the hostname):

```bash
# 1. Site is reachable and serves HTML
curl -sI https://operionerp.xyz | head -n 1                 # expect: HTTP/2 200

# 2. Security headers are present (CSP / X-Frame-Options / HSTS)
curl -sI https://operionerp.xyz | grep -i "content-security-policy"
curl -sI https://operionerp.xyz | grep -i "x-frame-options"          # expect: DENY
curl -sI https://operionerp.xyz | grep -i "strict-transport-security"
curl -sI https://operionerp.xyz | grep -i "x-content-type-options"   # expect: nosniff

# 3. SPA fallback works for deep links
curl -sI https://operionerp.xyz/pricing | head -n 1          # expect: 200 (served via _redirects)

# 4. Preview URL (from the PR) returns the same header set
curl -sI https://<hash>.<project>.pages.dev | grep -i "content-security-policy"
```

Checklist:

- [ ] `https://operionerp.xyz` returns **HTTP 200**.
- [ ] `Content-Security-Policy` header present.
- [ ] `X-Frame-Options: DENY` present.
- [ ] `Strict-Transport-Security` present.
- [ ] `X-Content-Type-Options: nosniff` present.
- [ ] A deep link (e.g. `/pricing`) returns 200 (SPA fallback via `_redirects`).
- [ ] PR preview URL is generated and carries the same headers.
