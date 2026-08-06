import { describe, it, expect, vi, beforeEach } from "vitest"
import { waitlistApi, referralApi } from "@/api/endpoints"
import apiClient from "@/api/client"

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe("waitlistApi", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe("join", () => {
    it("calls POST /api/v1/waitlist/join with company_name, email, source", () => {
      waitlistApi.join({ company_name: "Acme", email: "a@b.com", source: "landing_page" })
      expect(apiClient.post).toHaveBeenCalledWith(
        "/api/v1/waitlist/join",
        { company_name: "Acme", email: "a@b.com", source: "landing_page" }
      )
    })

    it("includes optional fields when provided", () => {
      waitlistApi.join({
        company_name: "Acme",
        email: "a@b.com",
        contact_name: "John",
        company_size: "11-50",
        country: "DE",
        fleet_size: "6-20",
        source: "google_ads",
      })
      expect(apiClient.post).toHaveBeenCalledWith(
        "/api/v1/waitlist/join",
        {
          company_name: "Acme",
          email: "a@b.com",
          contact_name: "John",
          company_size: "11-50",
          country: "DE",
          fleet_size: "6-20",
          source: "google_ads",
        }
      )
    })
  })

  describe("listEntries", () => {
    it("calls GET /api/v1/waitlist/admin/entries with no params", () => {
      waitlistApi.listEntries()
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/v1/waitlist/admin/entries",
        { params: undefined }
      )
    })

    it("calls GET with search and status filters", () => {
      waitlistApi.listEntries({ search: "test", status: "joined", page: 2, page_size: 50 })
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/v1/waitlist/admin/entries",
        { params: { search: "test", status: "joined", page: 2, page_size: 50 } }
      )
    })
  })

  describe("updateEntry", () => {
    it("calls PATCH /api/v1/waitlist/admin/entries/{id}", () => {
      waitlistApi.updateEntry(42, { status: "invited", notes: "Contacted" })
      expect(apiClient.patch).toHaveBeenCalledWith(
        "/api/v1/waitlist/admin/entries/42",
        { status: "invited", notes: "Contacted" }
      )
    })
  })

  describe("deleteEntry", () => {
    it("calls DELETE /api/v1/waitlist/admin/entries/{id}", () => {
      waitlistApi.deleteEntry(7)
      expect(apiClient.delete).toHaveBeenCalledWith("/api/v1/waitlist/admin/entries/7")
    })
  })

  describe("exportCsv", () => {
    it("calls GET /api/v1/waitlist/admin/export.csv with blob response", () => {
      waitlistApi.exportCsv({ status: "joined" })
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/v1/waitlist/admin/export.csv",
        { params: { status: "joined" }, responseType: "blob" }
      )
    })
  })

  describe("getStats", () => {
    it("calls GET /api/v1/waitlist/admin/stats", () => {
      waitlistApi.getStats()
      expect(apiClient.get).toHaveBeenCalledWith("/api/v1/waitlist/admin/stats")
    })
  })

  describe("sendCampaign", () => {
    it("calls POST /api/v1/waitlist/admin/campaign with subject, body, segment", () => {
      waitlistApi.sendCampaign({
        subject: "Welcome",
        body: "Hello!",
        segment: "all",
      })
      expect(apiClient.post).toHaveBeenCalledWith(
        "/api/v1/waitlist/admin/campaign",
        { subject: "Welcome", body: "Hello!", segment: "all" }
      )
    })

    it("defaults segment to all when not provided", () => {
      waitlistApi.sendCampaign({ subject: "Hi", body: "There" })
      expect(apiClient.post).toHaveBeenCalledWith(
        "/api/v1/waitlist/admin/campaign",
        { subject: "Hi", body: "There", segment: undefined }
      )
    })
  })

  describe("unsubscribe", () => {
    it("calls GET /api/v1/waitlist/unsubscribe/{token}", () => {
      waitlistApi.unsubscribe("tok_abc")
      expect(apiClient.get).toHaveBeenCalledWith("/api/v1/waitlist/unsubscribe/tok_abc")
    })
  })
})

describe("referralApi", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("getMyReferrals calls GET /api/v1/referrals/my", () => {
    referralApi.getMyReferrals()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/referrals/my")
  })

  it("trackReferral calls POST /api/v1/referrals/track", () => {
    referralApi.trackReferral({ referral_code: "ABC123" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/referrals/track", { referral_code: "ABC123" })
  })

  it("listReferrals calls GET with params", () => {
    referralApi.listReferrals({ page: 1, page_size: 50, status: "completed" })
    expect(apiClient.get).toHaveBeenCalledWith(
      "/api/v1/referrals/admin/list",
      { params: { page: 1, page_size: 50, status: "completed" } }
    )
  })

  it("getReferralStats calls GET /api/v1/referrals/admin/stats", () => {
    referralApi.getReferralStats()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/referrals/admin/stats")
  })
})
