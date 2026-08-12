import { describe, it, expect, vi, beforeEach } from "vitest"
import apiClient from "@/api/client"
import {
  authApi,
  companyApi,
  supportApi,
  blogApi,
  adminBlogApi,
  changelogApi,
  roadmapApi,
  statusApi,
  tutorialsApi,
  developersApi,
  securityApi,
  announcementsApi,
  customerStoriesApi,
  careersApi,
  pressApi,
  partnersApi,
  newsletterApi,
  searchApi,
  notificationsApi,
  integrationsApi,
  onboardingApi,
  waitlistApi,
  referralApi,
  devicesApi,
  organizationsApi,
  licensesApi,
} from "@/api/endpoints"

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
})

// ─────────────────────────────────────────────────────────────
// authApi
// ─────────────────────────────────────────────────────────────
describe("authApi", () => {
  it("login posts to /api/v1/auth/token with URLSearchParams", () => {
    authApi.login({ username: "test@c.com", password: "pass" })
    expect(apiClient.post).toHaveBeenCalledWith(
      "/api/v1/auth/token",
      expect.any(URLSearchParams),
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
    )
  })

  it("login passes correct URLSearchParams", () => {
    authApi.login({ username: "user@op.com", password: "s3cret" })
    const args = vi.mocked(apiClient.post).mock.calls[0]
    const params = args[1] as URLSearchParams
    expect(params.get("username")).toBe("user@op.com")
    expect(params.get("password")).toBe("s3cret")
    expect(params.get("grant_type")).toBe("password")
  })

  it("register posts to /api/v1/registration/register with all fields", () => {
    authApi.register({ email: "test@c.com", password: "pass", name: "Tester", company_name: "ACME", referral_code: "REF123" })
    expect(apiClient.post).toHaveBeenCalledWith(
      "/api/v1/registration/register",
      {
        email: "test@c.com",
        password: "pass",
        display_name: "Tester",
        company_name: "ACME",
        referral_code: "REF123",
      }
    )
  })

  it("register uses default company_name when not provided", () => {
    authApi.register({ email: "a@b.com", password: "x", name: "A" })
    expect(apiClient.post).toHaveBeenCalledWith(
      "/api/v1/registration/register",
      expect.objectContaining({ company_name: "My Company", referral_code: undefined })
    )
  })

  it("logout posts to /api/v1/auth/logout", () => {
    authApi.logout()
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/logout")
  })

  it("refreshToken posts to /api/v1/auth/refresh", () => {
    authApi.refreshToken("my-refresh-token")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/refresh", { refresh_token: "my-refresh-token" })
  })

  it("forgotPassword posts email to /api/v1/auth/forgot-password", () => {
    authApi.forgotPassword("user@op.com")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/forgot-password", { email: "user@op.com" })
  })

  it("resetPassword posts token and new_password to /api/v1/auth/reset-password", () => {
    authApi.resetPassword("tok123", "newp4ss")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/reset-password", { token: "tok123", new_password: "newp4ss" })
  })

  it("verifyEmail posts token to /api/v1/auth/verify-email", () => {
    authApi.verifyEmail("vtoken")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/verify-email", { token: "vtoken" })
  })

  it("getMe gets /api/v1/auth/me", () => {
    authApi.getMe()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/auth/me")
  })

  it("updateProfile patches /api/v1/auth/me with data", () => {
    authApi.updateProfile({ name: "NewName", email: "n@c.com" })
    expect(apiClient.patch).toHaveBeenCalledWith("/api/v1/auth/me", { name: "NewName", email: "n@c.com" })
  })

  it("changePassword posts to /api/v1/auth/change-password with data", () => {
    authApi.changePassword({ current_password: "old", new_password: "new" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/auth/change-password", { current_password: "old", new_password: "new" })
  })
})

// ─────────────────────────────────────────────────────────────
// companyApi
// ─────────────────────────────────────────────────────────────
describe("companyApi", () => {
  it("get fetches /api/v1/company", () => {
    companyApi.get()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/company")
  })

  it("update patches /api/v1/company with data", () => {
    companyApi.update({ company_name: "Op Inc", website: "https://op.com" })
    expect(apiClient.patch).toHaveBeenCalledWith("/api/v1/company", { company_name: "Op Inc", website: "https://op.com" })
  })
})

// ─────────────────────────────────────────────────────────────
// supportApi
// ─────────────────────────────────────────────────────────────
describe("supportApi", () => {
  it("createTicket posts to /api/v1/support/tickets with data", () => {
    supportApi.createTicket({ subject: "Bug", description: "It broke", priority: "high" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/support/tickets", {
      subject: "Bug",
      description: "It broke",
      priority: "high",
    })
  })

  it("createTicket works without optional priority", () => {
    supportApi.createTicket({ subject: "Q", description: "Help" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/support/tickets", {
      subject: "Q",
      description: "Help",
    })
  })

  it("getTickets fetches /api/v1/support/tickets", () => {
    supportApi.getTickets()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/support/tickets")
  })

  it("getTicket fetches /api/v1/support/tickets/:id", () => {
    supportApi.getTicket(42)
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/support/tickets/42")
  })

  it("getTicket works with string id", () => {
    supportApi.getTicket("TKT-123")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/support/tickets/TKT-123")
  })
})

// ─────────────────────────────────────────────────────────────
// blogApi
// ─────────────────────────────────────────────────────────────
describe("blogApi", () => {
  it("getPosts fetches /api/v1/blog/posts without params", () => {
    blogApi.getPosts()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/blog/posts", { params: undefined })
  })

  it("getPosts fetches /api/v1/blog/posts with params", () => {
    blogApi.getPosts({ page: 2, category: "ops", tag: "tutorial", search: "test" })
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/blog/posts", {
      params: { page: 2, category: "ops", tag: "tutorial", search: "test" },
    })
  })

  it("getPost fetches /api/v1/blog/posts/:slug", () => {
    blogApi.getPost("hello-world")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/blog/posts/hello-world")
  })

  it("getCategories fetches /api/v1/blog/categories", () => {
    blogApi.getCategories()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/blog/categories")
  })

  it("getAuthor fetches /api/v1/blog/authors/:id", () => {
    blogApi.getAuthor(1)
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/blog/authors/1")
  })

  it("getAuthor works with string id", () => {
    blogApi.getAuthor("author-slug")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/blog/authors/author-slug")
  })
})

// ─────────────────────────────────────────────────────────────
// adminBlogApi
// ─────────────────────────────────────────────────────────────
describe("adminBlogApi", () => {
  it("createPost posts to /api/v1/blog/admin/posts", () => {
    adminBlogApi.createPost({ title: "New Post", excerpt: "...", content: "# Hello", category_id: "cat1" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/blog/admin/posts", {
      title: "New Post",
      excerpt: "...",
      content: "# Hello",
      category_id: "cat1",
    })
  })

  it("updatePost patches /api/v1/blog/admin/posts/:slug", () => {
    adminBlogApi.updatePost("my-post", { title: "Updated", published: true })
    expect(apiClient.patch).toHaveBeenCalledWith("/api/v1/blog/admin/posts/my-post", {
      title: "Updated",
      published: true,
    })
  })

  it("deletePost deletes /api/v1/blog/admin/posts/:slug", () => {
    adminBlogApi.deletePost("my-post")
    expect(apiClient.delete).toHaveBeenCalledWith("/api/v1/blog/admin/posts/my-post")
  })
})

// ─────────────────────────────────────────────────────────────
// changelogApi
// ─────────────────────────────────────────────────────────────
describe("changelogApi", () => {
  it("getEntries fetches /api/v1/changelog", () => {
    changelogApi.getEntries()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/changelog")
  })
})

// ─────────────────────────────────────────────────────────────
// roadmapApi
// ─────────────────────────────────────────────────────────────
describe("roadmapApi", () => {
  it("getItems fetches /api/v1/roadmap without status", () => {
    roadmapApi.getItems()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/roadmap", { params: { status: undefined } })
  })

  it("getItems fetches /api/v1/roadmap with status", () => {
    roadmapApi.getItems("in-progress")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/roadmap", { params: { status: "in-progress" } })
  })
})

// ─────────────────────────────────────────────────────────────
// statusApi
// ─────────────────────────────────────────────────────────────
describe("statusApi", () => {
  it("getStatus fetches /api/v1/status", () => {
    statusApi.getStatus()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/status")
  })
})

// ─────────────────────────────────────────────────────────────
// tutorialsApi
// ─────────────────────────────────────────────────────────────
describe("tutorialsApi", () => {
  it("getTutorials fetches /api/v1/tutorials without params", () => {
    tutorialsApi.getTutorials()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/tutorials", { params: undefined })
  })

  it("getTutorials fetches /api/v1/tutorials with category", () => {
    tutorialsApi.getTutorials({ category: "getting-started", search: "setup" })
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/tutorials", {
      params: { category: "getting-started", search: "setup" },
    })
  })

  it("getTutorial fetches /api/v1/tutorials/:slug", () => {
    tutorialsApi.getTutorial("how-to-setup")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/tutorials/how-to-setup")
  })
})

// ─────────────────────────────────────────────────────────────
// developersApi
// ─────────────────────────────────────────────────────────────
describe("developersApi", () => {
  it("getResources fetches /api/v1/developers/resources", () => {
    developersApi.getResources()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/developers/resources")
  })

  it("getToolkitVersions fetches /api/v1/developers/toolkit/versions", () => {
    developersApi.getToolkitVersions()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/developers/toolkit/versions")
  })
})

// ─────────────────────────────────────────────────────────────
// securityApi
// ─────────────────────────────────────────────────────────────
describe("securityApi", () => {
  it("getReports fetches /api/v1/security/reports", () => {
    securityApi.getReports()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/security/reports")
  })

  it("submitReport posts to /api/v1/security/reports with data", () => {
    securityApi.submitReport({ title: "XSS", description: "Found in login", severity: "high" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/security/reports", {
      title: "XSS",
      description: "Found in login",
      severity: "high",
    })
  })
})

// ─────────────────────────────────────────────────────────────
// announcementsApi
// ─────────────────────────────────────────────────────────────
describe("announcementsApi", () => {
  it("getAnnouncements fetches /api/v1/announcements", () => {
    announcementsApi.getAnnouncements()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/announcements")
  })
})

// ─────────────────────────────────────────────────────────────
// customerStoriesApi
// ─────────────────────────────────────────────────────────────
describe("customerStoriesApi", () => {
  it("getStories fetches /api/v1/customer-stories without params", () => {
    customerStoriesApi.getStories()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/customer-stories", { params: undefined })
  })

  it("getStories fetches /api/v1/customer-stories with params", () => {
    customerStoriesApi.getStories({ page: 1, industry: "logistics", search: "warehouse" })
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/customer-stories", {
      params: { page: 1, industry: "logistics", search: "warehouse" },
    })
  })

  it("getStory fetches /api/v1/customer-stories/:slug", () => {
    customerStoriesApi.getStory("acme-logistics")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/customer-stories/acme-logistics")
  })
})

// ─────────────────────────────────────────────────────────────
// careersApi
// ─────────────────────────────────────────────────────────────
describe("careersApi", () => {
  it("getJobs fetches /api/v1/careers/jobs", () => {
    careersApi.getJobs()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/careers/jobs")
  })

  it("getJob fetches /api/v1/careers/jobs/:id", () => {
    careersApi.getJob("job-123")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/careers/jobs/job-123")
  })
})

// ─────────────────────────────────────────────────────────────
// pressApi
// ─────────────────────────────────────────────────────────────
describe("pressApi", () => {
  it("getReleases fetches /api/v1/press/releases", () => {
    pressApi.getReleases()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/press/releases")
  })

  it("getRelease fetches /api/v1/press/releases/:slug", () => {
    pressApi.getRelease("v2-launch")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/press/releases/v2-launch")
  })

  it("getKit fetches /api/v1/press/kit", () => {
    pressApi.getKit()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/press/kit")
  })
})

// ─────────────────────────────────────────────────────────────
// partnersApi
// ─────────────────────────────────────────────────────────────
describe("partnersApi", () => {
  it("getPartners fetches /api/v1/partners without type", () => {
    partnersApi.getPartners()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/partners", { params: { type: undefined } })
  })

  it("getPartners fetches /api/v1/partners with type", () => {
    partnersApi.getPartners("gold")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/partners", { params: { type: "gold" } })
  })

  it("getPartner fetches /api/v1/partners/:id", () => {
    partnersApi.getPartner("partner-1")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/partners/partner-1")
  })
})

// ─────────────────────────────────────────────────────────────
// newsletterApi
// ─────────────────────────────────────────────────────────────
describe("newsletterApi", () => {
  it("subscribe posts to /api/v1/newsletter/subscribe with data", () => {
    newsletterApi.subscribe({ email: "a@b.com", name: "Alice", preferences: ["updates"] })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/newsletter/subscribe", {
      email: "a@b.com",
      name: "Alice",
      preferences: ["updates"],
    })
  })

  it("subscribe works with minimal data", () => {
    newsletterApi.subscribe({ email: "a@b.com" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/newsletter/subscribe", { email: "a@b.com" })
  })

  it("unsubscribe posts email to /api/v1/newsletter/unsubscribe", () => {
    newsletterApi.unsubscribe("a@b.com")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/newsletter/unsubscribe", { email: "a@b.com" })
  })
})

// ─────────────────────────────────────────────────────────────
// searchApi
// ─────────────────────────────────────────────────────────────
describe("searchApi", () => {
  it("search fetches /api/v1/search with query and type", () => {
    searchApi.search("operion", "docs")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/search", {
      params: { q: "operion", type: "docs" },
    })
  })

  it("search fetches /api/v1/search with query only", () => {
    searchApi.search("operion")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/search", {
      params: { q: "operion", type: undefined },
    })
  })
})

// ─────────────────────────────────────────────────────────────
// notificationsApi
// ─────────────────────────────────────────────────────────────
describe("notificationsApi", () => {
  it("getNotifications fetches /api/v1/notifications", () => {
    notificationsApi.getNotifications()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/notifications")
  })

  it("markRead posts to /api/v1/notifications/:id/read", () => {
    notificationsApi.markRead("notif-1")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/notifications/notif-1/read")
  })

  it("markAllRead posts to /api/v1/notifications/read-all", () => {
    notificationsApi.markAllRead()
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/notifications/read-all")
  })

  it("getPreferences fetches /api/v1/notifications/preferences", () => {
    notificationsApi.getPreferences()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/notifications/preferences")
  })

  it("updatePreferences patches /api/v1/notifications/preferences with data", () => {
    notificationsApi.updatePreferences({ email_notifications: false })
    expect(apiClient.patch).toHaveBeenCalledWith("/api/v1/notifications/preferences", { email_notifications: false })
  })
})

// ─────────────────────────────────────────────────────────────
// integrationsApi
// ─────────────────────────────────────────────────────────────
describe("integrationsApi", () => {
  it("getIntegrations fetches /api/v1/integrations without category", () => {
    integrationsApi.getIntegrations()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/integrations", { params: { category: undefined } })
  })

  it("getIntegrations fetches /api/v1/integrations with category", () => {
    integrationsApi.getIntegrations("analytics")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/integrations", { params: { category: "analytics" } })
  })

  it("getIntegration fetches /api/v1/integrations/:id", () => {
    integrationsApi.getIntegration("int-1")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/integrations/int-1")
  })
})

// ─────────────────────────────────────────────────────────────
// onboardingApi
// ─────────────────────────────────────────────────────────────
describe("onboardingApi", () => {
  it("getChecklist fetches /api/v1/onboarding/checklist", () => {
    onboardingApi.getChecklist()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/onboarding/checklist")
  })

  it("completeStep posts to /api/v1/onboarding/steps/:stepId/complete", () => {
    onboardingApi.completeStep("step-1")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/onboarding/steps/step-1/complete")
  })
})

// ─────────────────────────────────────────────────────────────
// waitlistApi
// ─────────────────────────────────────────────────────────────
describe("waitlistApi", () => {
  it("join posts to /api/v1/waitlist/join with data", () => {
    waitlistApi.join({ company_name: "ACME", email: "a@b.com", source: "web" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/waitlist/join", {
      company_name: "ACME",
      email: "a@b.com",
      source: "web",
    })
  })

  it("listEntries fetches /api/v1/waitlist/admin/entries without params", () => {
    waitlistApi.listEntries()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/waitlist/admin/entries", { params: undefined })
  })

  it("listEntries fetches /api/v1/waitlist/admin/entries with params", () => {
    waitlistApi.listEntries({ page: 1, page_size: 50, status: "pending" })
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/waitlist/admin/entries", {
      params: { page: 1, page_size: 50, status: "pending" },
    })
  })

  it("updateEntry patches /api/v1/waitlist/admin/entries/:id", () => {
    waitlistApi.updateEntry(42, { status: "approved", notes: "OK" })
    expect(apiClient.patch).toHaveBeenCalledWith("/api/v1/waitlist/admin/entries/42", {
      status: "approved",
      notes: "OK",
    })
  })

  it("deleteEntry deletes /api/v1/waitlist/admin/entries/:id", () => {
    waitlistApi.deleteEntry(99)
    expect(apiClient.delete).toHaveBeenCalledWith("/api/v1/waitlist/admin/entries/99")
  })

  it("exportCsv fetches /api/v1/waitlist/admin/export.csv with params and responseType blob", () => {
    waitlistApi.exportCsv({ status: "approved" })
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/waitlist/admin/export.csv", {
      params: { status: "approved" },
      responseType: "blob",
    })
  })

  it("exportCsv works without params", () => {
    waitlistApi.exportCsv()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/waitlist/admin/export.csv", {
      params: undefined,
      responseType: "blob",
    })
  })

  it("getStats fetches /api/v1/waitlist/admin/stats", () => {
    waitlistApi.getStats()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/waitlist/admin/stats")
  })

  it("sendCampaign posts to /api/v1/waitlist/admin/campaign", () => {
    waitlistApi.sendCampaign({ subject: "Welcome", body: "<h1>Hi</h1>", segment: "all" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/waitlist/admin/campaign", {
      subject: "Welcome",
      body: "<h1>Hi</h1>",
      segment: "all",
    })
  })

  it("sendCampaign works without segment", () => {
    waitlistApi.sendCampaign({ subject: "Hi", body: "Test" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/waitlist/admin/campaign", {
      subject: "Hi",
      body: "Test",
    })
  })

  it("unsubscribe fetches /api/v1/waitlist/unsubscribe/:token", () => {
    waitlistApi.unsubscribe("unsub-token")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/waitlist/unsubscribe/unsub-token")
  })
})

// ─────────────────────────────────────────────────────────────
// referralApi
// ─────────────────────────────────────────────────────────────
describe("referralApi", () => {
  it("getMyReferrals fetches /api/v1/referrals/my", () => {
    referralApi.getMyReferrals()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/referrals/my")
  })

  it("trackReferral posts to /api/v1/referrals/track with data", () => {
    referralApi.trackReferral({ referral_code: "REF123" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/referrals/track", { referral_code: "REF123" })
  })

  it("listReferrals fetches /api/v1/referrals/admin/list without params", () => {
    referralApi.listReferrals()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/referrals/admin/list", { params: undefined })
  })

  it("listReferrals fetches /api/v1/referrals/admin/list with params", () => {
    referralApi.listReferrals({ page: 1, page_size: 20, status: "completed" })
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/referrals/admin/list", {
      params: { page: 1, page_size: 20, status: "completed" },
    })
  })

  it("getReferralStats fetches /api/v1/referrals/admin/stats", () => {
    referralApi.getReferralStats()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/referrals/admin/stats")
  })
})

// ─────────────────────────────────────────────────────────────
// devicesApi
// ─────────────────────────────────────────────────────────────
describe("devicesApi", () => {
  it("getDevices fetches /api/v1/mobile/devices", () => {
    devicesApi.getDevices()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/mobile/devices")
  })

  it("deactivateDevice deletes /api/v1/mobile/devices/:deviceId", () => {
    devicesApi.deactivateDevice("dev-abc")
    expect(apiClient.delete).toHaveBeenCalledWith("/api/v1/mobile/devices/dev-abc")
  })
})

// ─────────────────────────────────────────────────────────────
// organizationsApi
// ─────────────────────────────────────────────────────────────
describe("organizationsApi", () => {
  it("getAll fetches /api/v1/organizations", () => {
    organizationsApi.getAll()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/organizations")
  })

  it("get fetches /api/v1/organizations/:slug", () => {
    organizationsApi.get("my-org")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/organizations/my-org")
  })

  it("create posts to /api/v1/organizations with data", () => {
    organizationsApi.create({ name: "New Org", website: "https://neworg.com" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/organizations", {
      name: "New Org",
      website: "https://neworg.com",
    })
  })

  it("update patches /api/v1/organizations/:slug with data", () => {
    organizationsApi.update("my-org", { name: "Updated Org" })
    expect(apiClient.patch).toHaveBeenCalledWith("/api/v1/organizations/my-org", { name: "Updated Org" })
  })

  it("getMembers fetches /api/v1/organizations/:slug/members", () => {
    organizationsApi.getMembers("my-org")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/organizations/my-org/members")
  })

  it("inviteMember posts to /api/v1/organizations/:slug/invitations", () => {
    organizationsApi.inviteMember("my-org", { email: "user@c.com", role: "admin" })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/organizations/my-org/invitations", {
      email: "user@c.com",
      role: "admin",
    })
  })

  it("removeMember deletes /api/v1/organizations/:slug/members/:memberId", () => {
    organizationsApi.removeMember("my-org", "member-1")
    expect(apiClient.delete).toHaveBeenCalledWith("/api/v1/organizations/my-org/members/member-1")
  })

  it("getInvitations fetches /api/v1/organizations/:slug/invitations", () => {
    organizationsApi.getInvitations("my-org")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/organizations/my-org/invitations")
  })

  it("acceptInvitation posts to /api/v1/organizations/invitations/:token/accept", () => {
    organizationsApi.acceptInvitation("invite-token-xyz")
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/organizations/invitations/invite-token-xyz/accept")
  })
})

// ─────────────────────────────────────────────────────────────
// licensesApi
// ─────────────────────────────────────────────────────────────
describe("licensesApi", () => {
  it("getLicenses fetches /api/v1/licenses", () => {
    licensesApi.getLicenses()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/licenses")
  })

  it("getLicense fetches /api/v1/licenses/:id", () => {
    licensesApi.getLicense("lic-1")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/licenses/lic-1")
  })

  it("getLicense works with numeric id", () => {
    licensesApi.getLicense(42)
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/licenses/42")
  })

  it("getDevices fetches /api/v1/licenses/:licenseId/devices", () => {
    licensesApi.getDevices("lic-1")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/licenses/lic-1/devices")
  })

  it("getDevices works with numeric licenseId", () => {
    licensesApi.getDevices(42)
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/licenses/42/devices")
  })

  it("removeDevice deletes /api/v1/licenses/:licenseId/devices/:deviceId", () => {
    licensesApi.removeDevice("lic-1", "dev-9")
    expect(apiClient.delete).toHaveBeenCalledWith("/api/v1/licenses/lic-1/devices/dev-9")
  })

  it("removeDevice works with numeric ids", () => {
    licensesApi.removeDevice(42, 7)
    expect(apiClient.delete).toHaveBeenCalledWith("/api/v1/licenses/42/devices/7")
  })
})
