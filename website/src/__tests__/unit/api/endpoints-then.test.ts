import { describe, it, expect, vi, beforeEach } from "vitest"

const { apiClientMock } = vi.hoisted(() => ({
  apiClientMock: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock("@/api/client", () => ({
  default: apiClientMock,
}))

import {
  authApi,
  auditLogApi,
  analyticsApi,
  adminApi,
  opsApi,
  contactApi,
  notificationsApi,
  waitlistApi,
  supportApi,
  referralApi,
} from "@/api/endpoints"

describe("endpoints — promise unwrapping (.then((r) => r.data))", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("authApi.verifyMfa unwraps the AuthResponse", async () => {
    apiClientMock.post.mockResolvedValueOnce({ data: { access_token: "at", user: {} } })
    const res = await authApi.verifyMfa("sess-1", "123456")
    expect(apiClientMock.post).toHaveBeenCalledWith("/api/v1/auth/mfa/verify", {
      mfa_session_token: "sess-1",
      code: "123456",
    })
    expect(res).toEqual({ access_token: "at", user: {} })
  })

  it("auditLogApi.list unwraps entries", async () => {
    apiClientMock.get.mockResolvedValueOnce({
      data: { entries: [], total: 0, page: 1, per_page: 10 },
    })
    const res = await auditLogApi.list({ page: 2 })
    expect(apiClientMock.get).toHaveBeenCalledWith("/api/v1/audit-log", {
      params: { page: 2 },
    })
    expect(res).toEqual({ entries: [], total: 0, page: 1, per_page: 10 })
  })

  it("analyticsApi.getFinancial unwraps the payload", async () => {
    apiClientMock.get.mockResolvedValueOnce({ data: { revenue: 100 } })
    const res = await analyticsApi.getFinancial({ date_from: "2026-01-01" })
    expect(apiClientMock.get).toHaveBeenCalledWith("/api/v1/analytics/financial", {
      params: { date_from: "2026-01-01" },
    })
    expect(res).toEqual({ revenue: 100 })
  })

  it("adminApi helpers unwrap the payload", async () => {
    apiClientMock.get.mockResolvedValueOnce({ data: { count: 3 } })
    await expect(adminApi.getCompanyRowCounts()).resolves.toEqual({ count: 3 })

    apiClientMock.get.mockResolvedValueOnce({ data: { version: "1.0" } })
    await expect(adminApi.getSystemInfo()).resolves.toEqual({ version: "1.0" })

    apiClientMock.get.mockResolvedValueOnce({ data: { ok: true } })
    await expect(adminApi.getDiagnostics()).resolves.toEqual({ ok: true })
  })
})

describe("endpoints — opsApi", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("getTickets passes optional params", () => {
    opsApi.getTickets({ risk_tier: "high", status: "open" })
    expect(apiClientMock.get).toHaveBeenCalledWith("/api/v1/ops/tickets", {
      params: { risk_tier: "high", status: "open" },
    })
  })

  it("getTickets works without params", () => {
    opsApi.getTickets()
    expect(apiClientMock.get).toHaveBeenCalledWith("/api/v1/ops/tickets", { params: undefined })
  })

  it("getTicket fetches a single ticket", () => {
    opsApi.getTicket("t-1")
    expect(apiClientMock.get).toHaveBeenCalledWith("/api/v1/ops/tickets/t-1")
  })

  it("getApprovals fetches approvals", () => {
    opsApi.getApprovals()
    expect(apiClientMock.get).toHaveBeenCalledWith("/api/v1/ops/approvals")
  })

  it("handleApproval posts the action", () => {
    opsApi.handleApproval("a-1", "approve")
    expect(apiClientMock.post).toHaveBeenCalledWith("/api/v1/ops/approvals/a-1/approve")
  })

  it("getGuardrails fetches guardrail violations", () => {
    opsApi.getGuardrails()
    expect(apiClientMock.get).toHaveBeenCalledWith("/api/v1/ops/guardrails")
  })

  it("resolveGuardrail posts the resolve action", () => {
    opsApi.resolveGuardrail(7)
    expect(apiClientMock.post).toHaveBeenCalledWith("/api/v1/ops/guardrails/7/resolve")
  })

  it("getDashboard fetches the ops summary", () => {
    opsApi.getDashboard()
    expect(apiClientMock.get).toHaveBeenCalledWith("/api/v1/ops/dashboard")
  })

  it("getKnowledgeDrafts fetches drafts", () => {
    opsApi.getKnowledgeDrafts()
    expect(apiClientMock.get).toHaveBeenCalledWith("/api/v1/ops/knowledge/drafts")
  })

  it("approveKnowledgeDoc posts the approve action", () => {
    opsApi.approveKnowledgeDoc("doc-1")
    expect(apiClientMock.post).toHaveBeenCalledWith("/api/v1/ops/knowledge/doc-1/approve")
  })

  it("rejectKnowledgeDoc posts the reject action", () => {
    opsApi.rejectKnowledgeDoc("doc-1")
    expect(apiClientMock.post).toHaveBeenCalledWith("/api/v1/ops/knowledge/doc-1/reject")
  })
})

describe("endpoints — remaining APIs", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("contactApi.send posts the contact request", () => {
    const data = { name: "A", email: "a@b.com", subject: "Hi", message: "Body" }
    contactApi.send(data)
    expect(apiClientMock.post).toHaveBeenCalledWith("/api/v1/contact", data)
  })

  it("notificationsApi updatePreferences patches preferences", () => {
    notificationsApi.updatePreferences({ email_notifications: false })
    expect(apiClientMock.patch).toHaveBeenCalledWith("/api/v1/notifications/preferences", {
      email_notifications: false,
    })
  })

  it("waitlistApi.unsubscribe GETs the unsubscribe link", () => {
    waitlistApi.unsubscribe("tok-123")
    expect(apiClientMock.get).toHaveBeenCalledWith("/api/v1/waitlist/unsubscribe/tok-123")
  })

  it("supportApi.sendMessage posts a chat message", () => {
    supportApi.sendMessage({
      conversation_id: "c-1",
      message: "hello",
      channel: "chat",
    })
    expect(apiClientMock.post).toHaveBeenCalledWith("/api/v1/support/messages", {
      conversation_id: "c-1",
      message: "hello",
      channel: "chat",
    })
  })

  it("referralApi.createReferral posts the invitation", () => {
    referralApi.createReferral({ referred_email: "x@y.com" })
    expect(apiClientMock.post).toHaveBeenCalledWith("/api/v1/referrals/create", {
      referred_email: "x@y.com",
    })
  })
})
