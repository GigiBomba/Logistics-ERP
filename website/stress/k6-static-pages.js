import http from "k6/http"
import { check, sleep, group } from "k6"

export const options = {
  stages: [
    { duration: "30s", target: 50 },
    { duration: "2m", target: 50 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<3000"],
    http_req_failed: ["rate<0.01"],
  },
}

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000"

const pages = ["/", "/features", "/pricing", "/download", "/about", "/mission", "/faq", "/contact", "/privacy", "/terms", "/login", "/register", "/docs", "/products", "/integrations", "/community", "/customers", "/careers", "/press", "/brand", "/enterprise", "/partners", "/trust", "/newsletter"]

const v2Pages = ["/blog", "/changelog", "/roadmap", "/status", "/security", "/developers", "/developers/toolkit", "/tutorials"]

export default function () {
  group("static pages", () => {
    for (const path of pages) {
      const res = http.get(`${BASE_URL}${path}`)
      check(res, {
        "status is 200": (r) => r.status === 200,
        "response time < 2s": (r) => r.timings.duration < 2000,
      })
      sleep(1)
    }
  })

  group("V2 pages", () => {
    for (const path of v2Pages) {
      const res = http.get(`${BASE_URL}${path}`)
      check(res, {
        "v2 status is 200": (r) => r.status === 200,
        "v2 response time < 2s": (r) => r.timings.duration < 2000,
      })
      sleep(0.5)
    }
  })

  group("V2 body content checks", () => {
    const blogRes = http.get(`${BASE_URL}/blog`)
    check(blogRes, {
      "blog page loads": (r) => r.status === 200,
      "blog body contains Blog": (r) => r.body.includes("Blog"),
    })

    const statusRes = http.get(`${BASE_URL}/status`)
    check(statusRes, {
      "status page loads": (r) => r.status === 200,
      "status body contains Operational": (r) => r.body.includes("Operational"),
    })

    const roadmapRes = http.get(`${BASE_URL}/roadmap`)
    check(roadmapRes, {
      "roadmap page loads": (r) => r.status === 200,
      "roadmap body contains Roadmap": (r) => r.body.includes("Roadmap"),
    })
  })

  group("home page detail", () => {
    const res = http.get(`${BASE_URL}/`)
    check(res, {
      "home page loads": (r) => r.status === 200,
      "body contains hero": (r) => r.body.includes("Enterprise Logistics"),
    })
  })
}
