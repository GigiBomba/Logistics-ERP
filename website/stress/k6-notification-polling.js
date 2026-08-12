// k6 scenario — Notification polling (blueprint §16.7)
//
// Simulates 200 concurrent polling sessions on the notifications endpoint
// (frontend polls every 30s — see usePortalNotifications refetchInterval).
// Pass threshold: no backend degradation — p95 latency should stay bounded and
// the error rate must remain at zero/negligible at expected launch scale.
//
// Run:
//   k6 run stress/k6-notification-polling.js
//   k6 run stress/k6-notification-polling.js -e API_URL=https://api.operionerp.xyz
import http from "k6/http"
import { check, sleep } from "k6"

export const options = {
  scenarios: {
    notification_polling: {
      executor: "constant-vus",
      vus: 200,                // 200 concurrent polling sessions
      duration: "3m",          // multiple poll cycles (30s interval)
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<2000", "avg<800"],  // no degradation at scale
    http_req_failed: ["rate<0.001"],
    "http_req_duration{scenario:notifications}": ["p(95)<2000"],
  },
}

const API_URL = __ENV.API_URL || "http://localhost:8000"
const TOKEN = __ENV.TOKEN || "loadtest-notifications-token"

export default function () {
  const res = http.get(`${API_URL}/api/v1/notifications`, {
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      "Content-Type": "application/json",
    },
    tags: { scenario: "notifications" },
  })

  check(res, {
    "notifications status is 2xx": (r) => r.status >= 200 && r.status < 300,
    "notifications response time < 2s": (r) => r.timings.duration < 2000,
  })

  // Frontend polls every 30s; simulate one poll per iteration
  sleep(30)
}
