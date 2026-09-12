# k6 Stress & Load Tests

Load scenarios for the Operion website + API (blueprint §16.7). Each scenario lives in
`stress/` as a standalone k6 script — no shared harness, no test runner beyond `k6 run`.

## Prerequisites

- [k6](https://grafana.com/docs/k6/latest/) installed (`k6 version` to confirm).
- The app under test is reachable. Defaults target a local setup:
  - Website: `http://localhost:3000` (`BASE_URL`)
  - API: `http://localhost:8000` (`API_URL`)

## Environment variables

| Variable   | Used by                          | Default                    |
| ---------- | -------------------------------- | -------------------------- |
| `BASE_URL` | website scenarios                | `http://localhost:3000`    |
| `API_URL`  | API scenarios                    | `http://localhost:8000`    |
| `TOKEN`    | authenticated API scenarios      | `loadtest-<scenario>-token` (placeholder) |

Pass them with `-e`:

```bash
k6 run stress/k6-login.js -e BASE_URL=https://staging.operionerp.xyz -e API_URL=https://api.operionerp.xyz
```

The auth scenarios hit `/api/v1/auth/token` with synthetic `loadtest-<VU>@operion.dev`
users, so the API must accept those test accounts (or supply a real `TOKEN` for the
authenticated scenarios: dashboard-load, notification-polling, api-endpoints).

## Scenarios

| Scenario                     | File                             | Load profile                          |
| ---------------------------- | -------------------------------- | ------------------------------------- |
| Login                        | `stress/k6-login.js`             | ramp 0→50 VU / 30s, hold 1m, ramp down |
| Dashboard load               | `stress/k6-dashboard-load.js`    | 30 constant VUs for 2m                |
| Notification polling         | `stress/k6-notification-polling.js` | 200 constant VUs for 3m            |
| Spike test                   | `stress/k6-spike-test.js`        | 0→200 VU / 5s, hold 1m, ramp down     |
| Static pages                 | `stress/k6-static-pages.js`      | ramp 0→50 VU / 30s, hold 2m, ramp down |
| Sustained browsing           | `stress/k6-sustained-browsing.js`| 50 constant VUs for 5m                |
| API endpoints                | `stress/k6-api-endpoints.js`     | ramp 0→30 VU / 30s, hold 1m, ramp down |

### Login — `stress/k6-login.js`

50 VUs hammering the token endpoint. Pass threshold: p95 < 800 ms with < 1% errors.

```bash
k6 run stress/k6-login.js -e API_URL=https://api.operionerp.xyz
```

Thresholds (from the file):

- `http_req_duration` `p(95)<800`
- `http_req_failed` `rate<0.01`
- `http_req_duration{scenario:login_token}` `p(95)<800`

### Dashboard load — `stress/k6-dashboard-load.js`

30 concurrent users loading the dashboard; the four initial-load endpoints
(`/api/v1/auth/me`, `/company`, `/mobile/devices`, `/licenses`) are batched in parallel
per session. Pass thresholds: p95 < 1.5 s, zero 5xx responses.

```bash
k6 run stress/k6-dashboard-load.js -e API_URL=https://api.operionerp.xyz -e TOKEN=...
```

Thresholds:

- `http_req_duration` `p(95)<1500`
- `http_req_failed` `rate<0.01`
- per-endpoint `http_req_duration{scenario:dashboard_me|dashboard_company|dashboard_devices|dashboard_licenses}` `p(95)<1500`
- check-based "no 5xx responses" per batch

### Notification polling — `stress/k6-notification-polling.js`

200 concurrent polling sessions against `/api/v1/notifications` (frontend polls every
30 s via `usePortalNotifications`). Pass threshold: no backend degradation at scale.

```bash
k6 run stress/k6-notification-polling.js -e API_URL=https://api.operionerp.xyz -e TOKEN=...
```

Thresholds:

- `http_req_duration` `p(95)<2000`, `avg<800`
- `http_req_failed` `rate<0.001`
- `http_req_duration{scenario:notifications}` `p(95)<2000`

### Spike test — `stress/k6-spike-test.js`

Sudden ramp 0→200 VUs in 5 s against `/`, `/features`, `/pricing`. Pass threshold: the
site stays responsive under the shock load.

```bash
k6 run stress/k6-spike-test.js -e BASE_URL=https://staging.operionerp.xyz
```

Thresholds:

- `http_req_duration` `p(95)<5000`
- `http_req_failed` `rate<0.05`
- `http_reqs` `rate>100` (throughput floor)

### Static pages — `stress/k6-static-pages.js`

50 VUs cycling through the 24 public pages plus the 8 v2 pages (`/blog`, `/changelog`,
`/roadmap`, `/status`, `/security`, `/developers`, `/developers/toolkit`, `/tutorials`)
with body-content spot checks. Pass threshold: p95 < 3 s, < 1% errors.

```bash
k6 run stress/k6-static-pages.js -e BASE_URL=https://staging.operionerp.xyz
```

Thresholds:

- `http_req_duration` `p(95)<3000`
- `http_req_failed` `rate<0.01`

### Sustained browsing — `stress/k6-sustained-browsing.js`

50 VUs for 5 minutes simulating realistic browse sessions (batched page hits with
think time). Pass threshold: p95 < 4 s, avg < 1.5 s, < 2% errors.

```bash
k6 run stress/k6-sustained-browsing.js -e BASE_URL=https://staging.operionerp.xyz
```

Thresholds:

- `http_req_duration` `p(95)<4000`, `avg<1500`
- `http_req_failed` `rate<0.02`

### API endpoints — `stress/k6-api-endpoints.js`

30 VUs exercising the public API surface (auth, company, subscriptions, support, blog,
organizations, licenses, changelog, roadmap, status, tutorials, developers,
integrations, search, newsletter, announcements, customer stories, careers, press,
partners, security, onboarding — ~30 endpoints). Pass threshold: p95 < 3 s, < 5% errors.

```bash
k6 run stress/k6-api-endpoints.js -e API_URL=https://api.operionerp.xyz
```

Thresholds:

- `http_req_duration` `p(95)<3000`
- `http_req_failed` `rate<0.05`

## Running via npm (from `website/`)

| Command                  | Runs                                             |
| ------------------------ | ------------------------------------------------ |
| `npm run stress`         | all 7 scenarios sequentially                     |
| `npm run stress:login`   | `k6 run stress/k6-login.js`                      |
| `npm run stress:dashboard` | `k6 run stress/k6-dashboard-load.js`           |
| `npm run stress:notifications` | `k6 run stress/k6-notification-polling.js`  |
| `npm run stress:spike`   | `k6 run stress/k6-spike-test.js`                 |
| `npm run stress:static`  | `k6 run stress/k6-static-pages.js`               |
| `npm run stress:sustained` | `k6 run stress/k6-sustained-browsing.js`       |
| `npm run stress:endpoints` | `k6 run stress/k6-api-endpoints.js`            |
| `npm run stress:watch`   | k6 web dashboard on the login scenario           |

### Live web dashboard

`stress:watch` runs the login scenario with k6's built-in web dashboard
(`K6_WEB_DASHBOARD=true`). Open the printed dashboard URL (default `http://127.0.0.1:5665`)
in a browser while the test runs.

POSIX equivalent:

```bash
K6_WEB_DASHBOARD=true k6 run stress/k6-login.js
```