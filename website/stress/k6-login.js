// k6 scenario — Login endpoint under load (blueprint §16.7)
//
// Load profile: ramp 0 → 50 virtual users over 30s, hold 1 minute, ramp down.
// Pass thresholds: p95 response time < 800ms, error rate < 1% on /auth/token.
//
// Run:
//   k6 run stress/k6-login.js
//   k6 run stress/k6-login.js -e BASE_URL=https://staging.operionerp.xyz \
//                              -e API_URL=https://api.operionerp.xyz
import http from "k6/http"
import { check, sleep } from "k6"

export const options = {
  stages: [
    { duration: "30s", target: 50 },  // ramp 0 → 50 VUs
    { duration: "1m", target: 50 },   // hold at 50 VUs
    { duration: "30s", target: 0 },   // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<800"],        // p95 < 800ms
    http_req_failed: ["rate<0.01"],          // error rate < 1%
    // Per-request tag for the token endpoint
    "http_req_duration{scenario:login_token}": ["p(95)<800"],
  },
}

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000"
const API_URL = __ENV.API_URL || "http://localhost:8000"

export default function () {
  const payload = {
    username: `loadtest-${__VU}@operion.dev`,
    password: "TestPass123!",
    grant_type: "password",
  }
  const res = http.post(
    `${API_URL}/api/v1/auth/token`,
    new URLSearchParams(payload).toString(),
    {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      tags: { scenario: "login_token" },
    }
  )

  check(res, {
    "login status is 2xx": (r) => r.status >= 200 && r.status < 300,
    "login response time < 800ms": (r) => r.timings.duration < 800,
  })

  sleep(1)
}
