import { http, HttpResponse } from "msw"

export const authHandlers = [
  http.post("*/api/v1/auth/token", () => {
    return HttpResponse.json({
      access_token: "test-access-token",
      refresh_token: "test-refresh-token",
      token_type: "bearer",
      expires_in: 3600,
      user: {
        id: "user-1",
        email: "test@operion.dev",
        full_name: "Test User",
        role: "owner",
        is_admin: true,
        company_name: "Test Company",
      },
    })
  }),

  http.post("*/api/v1/auth/refresh", () => {
    return HttpResponse.json({
      access_token: "refreshed-access-token",
      token_type: "bearer",
      expires_in: 3600,
    })
  }),

  http.get("*/api/v1/auth/me", () => {
    return HttpResponse.json({
      id: "user-1",
      email: "test@operion.dev",
      full_name: "Test User",
      role: "owner",
      is_admin: true,
      company_name: "Test Company",
    })
  }),

  http.post("*/api/v1/auth/me/avatar", () => {
    return HttpResponse.json({
      avatar_url: "https://cdn.operion.dev/avatars/test-user-1.png",
    })
  }),
]
