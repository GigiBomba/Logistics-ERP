import http from "k6/http"
import { check, sleep, group } from "k6"

export const options = {
  scenarios: {
    constant_load: {
      executor: "constant-vus",
      vus: 50,
      duration: "5m",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<4000", "avg<1500"],
    http_req_failed: ["rate<0.02"],
  },
}

const BASE_URL = __ENV.BASE_URL || "http://localhost:3000"

export default function () {
  group("browsing session", () => {
    http.batch([
      ["GET", `${BASE_URL}/`],
      ["GET", `${BASE_URL}/features`],
      ["GET", `${BASE_URL}/pricing`],
    ])
    sleep(2)

    http.batch([
      ["GET", `${BASE_URL}/download`],
      ["GET", `${BASE_URL}/about`],
      ["GET", `${BASE_URL}/docs`],
    ])
    sleep(1)

    const res = http.get(`${BASE_URL}/faq`)
    check(res, {
      "faq page loads": (r) => r.status === 200,
    })
  })
}
