import { describe, it, expect, vi, beforeEach } from "vitest"
import { opsApi, adminApi, referralApi } from "@/api/endpoints"
import apiClient from "@/api/client"

vi.mock("@/api/client", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

describe("opsApi (V2)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("has all methods", () => {
    expect(typeof opsApi.getTickets).toBe("function")
    expect(typeof opsApi.getTicket).toBe("function")
    expect(typeof opsApi.getApprovals).toBe("function")
    expect(typeof opsApi.handleApproval).toBe("function")
    expect(typeof opsApi.getGuardrails).toBe("function")
    expect(typeof opsApi.resolveGuardrail).toBe("function")
    expect(typeof opsApi.getDashboard).toBe("function")
    expect(typeof opsApi.getKnowledgeDrafts).toBe("function")
    expect(typeof opsApi.approveKnowledgeDoc).toBe("function")
    expect(typeof opsApi.rejectKnowledgeDoc).toBe("function")
  })

  it("getTickets calls GET /api/v1/ops/tickets with params", () => {
    opsApi.getTickets({ risk_tier: "high" })
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/ops/tickets", { params: { risk_tier: "high" } })
  })

  it("getTickets works without params", () => {
    opsApi.getTickets()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/ops/tickets", { params: undefined })
  })

  it("getTicket calls GET /api/v1/ops/tickets/:id", () => {
    opsApi.getTicket("t-1")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/ops/tickets/t-1")
  })

  it("getApprovals calls GET /api/v1/ops/approvals", () => {
    opsApi.getApprovals()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/ops/approvals")
  })

  it("handleApproval posts action to /api/v1/ops/approvals/:id/:action", () => {
    opsApi.handleApproval("a-1", "approve")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/ops/approvals/a-1/approve")
  })

  it("getGuardrails calls GET /api/v1/ops/guardrails", () => {
    opsApi.getGuardrails()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/ops/guardrails")
  })

  it("resolveGuardrail posts to /api/v1/ops/guardrails/:id/resolve", () => {
    opsApi.resolveGuardrail(42)
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/ops/guardrails/42/resolve")
  })

  it("getDashboard calls GET /api/v1/ops/dashboard", () => {
    opsApi.getDashboard()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/ops/dashboard")
  })

  it("getKnowledgeDrafts calls GET /api/v1/ops/knowledge/drafts", () => {
    opsApi.getKnowledgeDrafts()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/ops/knowledge/drafts")
  })

  it("approveKnowledgeDoc posts to /api/v1/ops/knowledge/:docId/approve", () => {
    opsApi.approveKnowledgeDoc("doc-1")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/ops/knowledge/doc-1/approve")
  })

  it("rejectKnowledgeDoc posts to /api/v1/ops/knowledge/:docId/reject", () => {
    opsApi.rejectKnowledgeDoc("doc-1")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/ops/knowledge/doc-1/reject")
  })
})

describe("adminApi (V2 diagnostics)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("getCompanyRowCounts resolves with the row-count payload", async () => {
    const payload = { companies: 3, trucks: 12 }
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: payload })
    await expect(adminApi.getCompanyRowCounts()).resolves.toEqual(payload)
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/admin/db/company-row-counts")
  })

  it("getSystemInfo resolves with the system info payload", async () => {
    const payload = { version: "1.2.3", python: "3.11" }
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: payload })
    await expect(adminApi.getSystemInfo()).resolves.toEqual(payload)
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/admin/system/info")
  })

  it("getDiagnostics resolves with the diagnostics payload", async () => {
    const payload = { checks: ["ok"] }
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: payload })
    await expect(adminApi.getDiagnostics()).resolves.toEqual(payload)
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/admin/diagnostics")
  })
})

describe("referralApi (V2)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("getMyReferrals calls GET /api/v1/referrals/my", () => {
    referralApi.getMyReferrals()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/referrals/my")
  })

  it("createReferral posts the invited email", () => {
    referralApi.createReferral({ referred_email: "friend@example.com" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/referrals/create", {
      referred_email: "friend@example.com",
    })
  })

  it("trackReferral posts the referral code", () => {
    referralApi.trackReferral({ referral_code: "RID-123" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/referrals/track", {
      referral_code: "RID-123",
    })
  })

  it("listReferrals calls GET with params and without", () => {
    referralApi.listReferrals({ page: 2, page_size: 10, status: "completed" })
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/referrals/admin/list", {
      params: { page: 2, page_size: 10, status: "completed" },
    })
    referralApi.listReferrals()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/referrals/admin/list", { params: undefined })
  })

  it("getReferralStats calls GET /api/v1/referrals/admin/stats", () => {
    referralApi.getReferralStats()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/referrals/admin/stats")
  })
})
