// k6 scenario — Dashboard initial load (blueprint §16.7)
//
// Simulates 30 concurrent users loading the dashboard: the initial-load endpoints
// (auth/me + company + devices + licenses) are fetched in parallel per session.
// Pass thresholds: p95 < 1.5s, zero 5xx responses.
//
// Run:
//   k6 run stress/k6-dashboard-load.js
//   k6 run stress/k6-dashboard-load.js -e API_URL=https://api.operionerp.xyz
import http from "k6/http"
import { check } from "k6"

export const options = {
  scenarios: {
    dashboard_load: {
      executor: "constant-vus",
      vus: 30,                 // 30 concurrent users
      duration: "2m",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<1500"],   // p95 < 1.5s
    http_req_failed: ["rate<0.01"],
    // Zero 5xx responses — count checks per request below
    "http_req_duration{scenario:dashboard_me}": ["p(95)<1500"],
    "http_req_duration{scenario:dashboard_company}": ["p(95)<1500"],
    "http_req_duration{scenario:dashboard_devices}": ["p(95)<1500"],
    "http_req_duration{scenario:dashboard_licenses}": ["p(95)<1500"],
  },
}

const API_URL = __ENV.API_URL || "http://localhost:8000"
const TOKEN = __ENV.TOKEN || "loadtest-dashboard-token"

// Dashboard initial-load endpoints — fetched in parallel per session
const dashboardEndpoints = [
  { name: "auth me", path: "/api/v1/auth/me", tag: "dashboard_me" },
  { name: "company", path: "/api/v1/company", tag: "dashboard_company" },
  { name: "devices", path: "/api/v1/mobile/devices", tag: "dashboard_devices" },
  { name: "licenses", path: "/api/v1/licenses", tag: "dashboard_licenses" },
]

export default function () {
  const requests = dashboardEndpoints.map((ep) => ({
    method: "GET",
    url: `${API_URL}${ep.path}`,
    params: {
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        "Content-Type": "application/json",
      },
      tags: { scenario: ep.tag },
    },
  }))

  const responses = http.batch(requests)

  let saw5xx = false
  responses.forEach((res, i) => {
    const ep = dashboardEndpoints[i]
    check(res, {
      [`${ep.name} status is 2xx`]: (r) => r.status >= 200 && r.status < 300,
      [`${ep.name} response time < 1.5s`]: (r) => r.timings.duration < 1500,
    })
    if (res.status >= 500) saw5xx = true
  })

  check(saw5xx, {
    "no 5xx responses": (v) => v === false,
  })
}
