# Deployment — cloudflare tunnel origin (PC-hosted)

How the Operion website is built, served, and kept live.

> **Hosting model (2026-08-06):** everything runs on the operator's PC. A
> `cloudflared` tunnel service (remote-managed via the Cloudflare dashboard —
> `tunnel run --token …`) exposes it to the internet. The tunnel's ingress
> maps:
>
> | Hostname | Origin |
> |---|---|
> | `operionerp.xyz` | `http://127.0.0.1:8080` (this site) |
> | `api.operionerp.xyz` | `http://127.0.0.1:8000` (backend) |
>
> The website origin is `scripts/serve-site.mjs` — a small Node server that
> serves the vike build output (`dist/client`), applies the security headers
> from `public/_headers`, and does SPA fallback (mirrors
> `public/_redirects`). Cloudflare Pages is NOT used for hosting (a Pages
> deployment exists as a bonus preview channel only).

---

## 1. Build

```bash
npm ci
npm run build    # = tsc -b && sitemap && og-images && vike build
```

Output: `dist/client/` (prerendered pages + assets + public/ copies). That
directory is what the origin serves.

## 2. Serve

```bash
node scripts/serve-site.mjs        # serves dist/client on 127.0.0.1:8080
# env: PORT (default 8080), HOST (default 127.0.0.1)
```

The server:
- serves `dist/client` statically with correct MIME types,
- applies `public/_headers` rules (CSP, HSTS, X-Frame-Options DENY, …),
- SPA-fallback: unknown paths serve `dist/client/index.html` (200).

The tunnel's ingress already points `operionerp.xyz → 127.0.0.1:8080`, so no
tunnel/DNS changes are needed when the server runs.

## 3. Keep it running

- `scripts/start-site.cmd` — looped launcher (auto-restarts the server if it
  exits).
- `scripts/start-site.vbs` — hidden-window runner; a copy lives in the user's
  Startup folder (`operion-site.vbs`) so the site starts at logon.

## 4. Deploy a new version

```bash
git pull            # (from the Logistics-ERP megarepo, website/ dir)
npm ci
npm run build
# restart the origin server:
Stop-Process -Name node -ErrorAction SilentlyContinue   # then the .cmd loop restarts it,
                                                          # or start serve-site.mjs again
```

## 5. Verify

```bash
curl -sI https://operionerp.xyz | head -n 1        # expect: HTTP/1.1 200 OK
curl -sI https://operionerp.xyz | grep -i content-security-policy
curl -sI https://operionerp.xyz | grep -i x-frame-options    # DENY
curl -sI https://api.operionerp.xyz/health/live              # backend liveness
```

## 6. Source of truth

The frontend lives at `website/` in the `Logistics-ERP` GitHub megarepo
(commit 2026-08-06). The PC serves local builds; GitHub is the code home and
CI (lint/typecheck/vitest/playwright run there).
