import http from "k6/http"
import { check, sleep } from "k6"

export const options = {
  scenarios: {
    spike: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "5s", target: 200 },
        { duration: "1m", target: 200 },
        { duration: "30s", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<5000"],
    http_req_failed: ["rate<0.05"],
    http_reqs: ["rate>100"],
  },
}

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000"

export default function () {
  const res = http.get(`${BASE_URL}/`)
  check(res, {
    "status 200": (r) => r.status === 200,
    "response < 5s": (r) => r.timings.duration < 5000,
  })

  const res2 = http.get(`${BASE_URL}/features`)
  check(res2, {
    "features status 200": (r) => r.status === 200,
  })

  const res3 = http.get(`${BASE_URL}/pricing`)
  check(res3, {
    "pricing status 200": (r) => r.status === 200,
  })

  sleep(0.3)
}
