import { describe, it, expect, vi, beforeEach } from "vitest"
import { authApi, subscriptionApi, companyApi, supportApi, downloadApi } from "@/api/endpoints"
import apiClient from "@/api/client"

vi.mock("@/api/client", { default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } })

describe("authApi", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("login calls POST /api/v1/auth/token with form-urlencoded data", () => {
    const username = "a@b.com"
    authApi.login({ username, password: "secret" })
    expect(apiClient.post).toHaveBeenCalledWith(
      "/api/v1/auth/token",
      new URLSearchParams({ username, password: "secret", grant_type: "password" }),
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
    )
  })

  it("register calls POST /api/v1/auth/register", () => {
    authApi.register({ email: "a@b.com", password: "secret123", name: "John" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/registration/register", {
      email: "a@b.com",
      password: "secret123",
      display_name: "John",
      company_name: "My Company",
    })
  })

  it("logout calls POST /api/v1/auth/logout", () => {
    authApi.logout()
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/logout")
  })

  it("refreshToken calls POST /api/v1/auth/refresh", () => {
    authApi.refreshToken("rtoken")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/refresh", { refresh_token: "rtoken" })
  })

  it("forgotPassword calls POST with email", () => {
    authApi.forgotPassword("a@b.com")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/forgot-password", { email: "a@b.com" })
  })

  it("resetPassword calls POST with token and password", () => {
    authApi.resetPassword("tok", "newpass")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/reset-password", { token: "tok", new_password: "newpass" })
  })

  it("verifyEmail calls POST with token", () => {
    authApi.verifyEmail("vtoken")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/verify-email", { token: "vtoken" })
  })

  it("getMe calls GET /api/v1/auth/me", () => {
    authApi.getMe()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/auth/me")
  })

  it("updateProfile calls PATCH /api/v1/auth/me", () => {
    authApi.updateProfile({ name: "New Name" })
    expect(apiClient.patch).toHaveBeenCalledWith("/api/v1/auth/me", { name: "New Name" })
  })

  it("changePassword calls POST /api/v1/auth/change-password", () => {
    authApi.changePassword({ current_password: "old", new_password: "new" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/change-password", { current_password: "old", new_password: "new" })
  })
})

describe("subscriptionApi", () => {
  it("getCurrent calls GET /api/v1/subscriptions/current", () => {
    subscriptionApi.getCurrent()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/subscriptions/current")
  })

  it("getPlans calls GET /api/v1/subscriptions/plans", () => {
    subscriptionApi.getPlans()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/subscriptions/plans")
  })
})

describe("companyApi", () => {
  it("get calls GET /api/v1/company", () => {
    companyApi.get()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/company")
  })

  it("update calls PATCH with typed data", () => {
    companyApi.update({ name: "New Co", vat_number: "RO123" })
    expect(apiClient.patch).toHaveBeenCalledWith("/api/v1/company", { name: "New Co", vat_number: "RO123" })
  })
})

describe("supportApi", () => {
  it("createTicket calls POST with subject and description", () => {
    supportApi.createTicket({ subject: "[Bug] Crash", description: "Details" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/support/tickets", { subject: "[Bug] Crash", description: "Details" })
  })

  it("createTicket accepts optional priority", () => {
    supportApi.createTicket({ subject: "Urgent", description: "Help", priority: "high" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/support/tickets", { subject: "Urgent", description: "Help", priority: "high" })
  })

  it("getTickets calls GET /api/v1/support/tickets", () => {
    supportApi.getTickets()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/support/tickets")
  })

  it("getTicket calls GET with id", () => {
    supportApi.getTicket("ticket-1")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/support/tickets/ticket-1")
  })
})

describe("downloadApi", () => {
  it("getLatest calls GET /api/v1/downloads/latest", () => {
    downloadApi.getLatest()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/downloads/latest")
  })

  it("getVersions calls GET /api/v1/downloads/versions", () => {
    downloadApi.getVersions()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/downloads/versions")
  })
})
