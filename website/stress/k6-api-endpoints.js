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
  // Auth
  { name: "auth me", path: "/api/v1/auth/me", method: "GET", auth: true },
  { name: "auth token", path: "/api/v1/auth/token", method: "POST", body: { email: "test@example.com", password: "test123" } },
  { name: "auth refresh", path: "/api/v1/auth/refresh", method: "POST", body: { refreshToken: "test-refresh-token" } },
  // Company
  { name: "company info", path: "/api/v1/company", method: "GET" },
  // Subscriptions
  { name: "subscription plans", path: "/api/v1/subscriptions/plans", method: "GET" },
  { name: "subscription current", path: "/api/v1/subscriptions/current", method: "GET", auth: true },
  // Support
  { name: "support tickets GET", path: "/api/v1/support/tickets", method: "GET", auth: true },
  { name: "support tickets POST", path: "/api/v1/support/tickets", method: "POST", auth: true, body: { subject: "Test", message: "Test message" } },
  // Blog
  { name: "blog posts", path: "/api/v1/blog/posts", method: "GET" },
  { name: "blog categories", path: "/api/v1/blog/categories", method: "GET" },
  // Organizations
  { name: "organizations", path: "/api/v1/organizations", method: "GET", auth: true },
  // Licenses
  { name: "licenses", path: "/api/v1/licenses", method: "GET", auth: true },
  // Changelog
  { name: "changelog", path: "/api/v1/changelog", method: "GET" },
  // Roadmap
  { name: "roadmap", path: "/api/v1/roadmap", method: "GET" },
  // Status
  { name: "status", path: "/api/v1/status", method: "GET" },
  // Tutorials
  { name: "tutorials", path: "/api/v1/tutorials", method: "GET" },
  // Developers
  { name: "developers resources", path: "/api/v1/developers/resources", method: "GET" },
  // Integrations
  { name: "integrations", path: "/api/v1/integrations", method: "GET" },
  // Search
  { name: "search", path: "/api/v1/search?q=test", method: "GET" },
  // Newsletter
  { name: "newsletter subscribe", path: "/api/v1/newsletter/subscribe", method: "POST", body: { email: "test@example.com" } },
  // Announcements
  { name: "announcements", path: "/api/v1/announcements", method: "GET" },
  // Customer Stories
  { name: "customer stories", path: "/api/v1/customer-stories", method: "GET" },
  // Careers
  { name: "careers jobs", path: "/api/v1/careers/jobs", method: "GET" },
  // Press
  { name: "press releases", path: "/api/v1/press/releases", method: "GET" },
  // Partners
  { name: "partners", path: "/api/v1/partners", method: "GET" },
  // Security
  { name: "security reports", path: "/api/v1/security/reports", method: "GET" },
  // Onboarding
  { name: "onboarding checklist", path: "/api/v1/onboarding/checklist", method: "GET", auth: true },
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

      const method = ep.method || "GET"
      const body = ep.body ? JSON.stringify(ep.body) : null

      const res = http.request(method, `${API_URL}${ep.path}`, body, params)
      check(res, {
        [`${ep.name} status is 2xx`]: (r) => r.status >= 200 && r.status < 300,
        [`${ep.name} response time < 3s`]: (r) => r.timings.duration < 3000,
      })
      sleep(0.5)
    }
  })
}
