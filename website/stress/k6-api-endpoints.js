import http from "k6/http"
import { check, sleep, group } from "k6"

export const options = {
  stages: [
    { duration: "30s", target: 30 },
    { duration: "1m", target: 30 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<3000"],
    http_req_failed: ["rate<0.05"],
  },
}

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000"
const API_URL = __ENV.API_URL || "http://localhost:8000"

const endpoints = [
  { name: "auth me", path: "/api/auth/me", auth: true },
  { name: "subscription plans", path: "/api/subscriptions/plans" },
  { name: "blog posts", path: "/api/blog/posts" },
  { name: "changelog", path: "/api/changelog" },
  { name: "roadmap", path: "/api/roadmap" },
  { name: "status", path: "/api/status" },
  { name: "tutorials", path: "/api/tutorials" },
  { name: "developers resources", path: "/api/developers/resources" },
]

export default function () {
  group("API endpoints", () => {
    for (const ep of endpoints) {
      const params = {
        headers: {
          "Content-Type": "application/json",
        },
      }

      if (ep.auth) {
        params.headers["Authorization"] = "Bearer test-token"
      }

      const res = http.get(`${API_URL}${ep.path}`, params)
      check(res, {
        [`${ep.name} status is 200`]: (r) => r.status === 200,
        [`${ep.name} response time < 3s`]: (r) => r.timings.duration < 3000,
      })
      sleep(0.5)
    }
  })
}
