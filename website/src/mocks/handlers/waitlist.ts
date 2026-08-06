import { http, HttpResponse } from "msw"

export const waitlistHandlers = [
  http.get("*/api/v1/waitlist/count", () => {
    return HttpResponse.json({
      count: 513,
      cached_at: new Date().toISOString(),
    })
  }),
]
