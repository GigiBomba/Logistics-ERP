import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor, act } from "@testing-library/react"
import { QueryClientProvider, QueryClient } from "@tanstack/react-query"
import { type ReactNode } from "react"
import {
  authApi, subscriptionApi, companyApi, supportApi, devicesApi, blogApi, adminBlogApi,
  organizationsApi, licensesApi, changelogApi, roadmapApi, statusApi, tutorialsApi,
  developersApi, securityApi, announcementsApi, customerStoriesApi, careersApi, pressApi,
  partnersApi, newsletterApi, searchApi, notificationsApi, integrationsApi, onboardingApi, invoicesApi,
  waitlistApi, mfaApi, avatarApi, downloadApi, adminApi, sessionsApi, referralApi, auditLogApi,
  analyticsApi, opsApi,
} from "@/api/endpoints"
import apiClient from "@/api/client"
import {
  useProfile, useUpdateProfile, useChangePassword,
  useSubscription, usePlans,
  useCompany, useUpdateCompany,
  useCreateTicket, useTickets,
  useDevices, useDeactivateDevice,
  useBlogPosts, useBlogPost, useBlogAuthor, useBlogCategories,
  useChangelog, useRoadmap, useServiceStatus,
  useTutorials, useTutorial,
  useDevResources, useToolkitVersions,
  useSecurityReports, useSubmitSecurityReport,
  useAnnouncements, useInvoices,
  useCreateBlogPost, useUpdateBlogPost, useDeleteBlogPost,
  useOrganizations, useOrganization, useCreateOrganization, useUpdateOrganization,
  useOrganizationMembers, useInviteMember, useRemoveMember,
  useOrganizationInvitations, useAcceptInvitation,
  useLicenses, useLicense, useLicenseDevices, useRemoveLicenseDevice,
  useOnboardingChecklist, useCompleteOnboardingStep,
  useIntegrations, useJobs, useJob,
  useCustomerStories, useCustomerStory,
  usePressReleases, usePressKit,
  usePartners, useSubscribeNewsletter,
  useGlobalSearch,
  usePortalNotifications, useMarkNotificationRead, useMarkAllRead, useNotificationPreferences,
  useUpdateNotificationPreferences,
  useMfaEnroll, useMfaConfirm, useMfaDisable, useMfaStatus,
  useUpdateBillingTerm, useCancelSubscription, useReactivateSubscription,
  useAddTruck, useRemoveTruck, useCreateCheckoutSession, useCreatePortalSession, useToggleAddon,
  useWaitlistCount, useWaitlistEntries, useAvatarUpload,
  useSendSupportMessage,
  useLatestDownload, useDownloadVersions,
  useAdminCompanyRowCounts,
  useSessions, useRevokeSession,
  useReferrals, useReferralStats, useCreateReferral,
  useWriteAuditLog, useAuditLog,
  useFinancialAnalytics,
  useOpsTickets, useOpsTicket, useOpsApprovals, useOpsHandleApproval,
  useOpsGuardrails, useOpsResolveGuardrail, useOpsDashboard,
  useOpsKnowledgeDrafts, useOpsApproveKnowledgeDoc, useOpsRejectKnowledgeDoc,
} from "@/services/queries"

vi.mock("@/api/client", () => ({
  default: { post: vi.fn(), get: vi.fn() },
}))

vi.mock("@/api/endpoints", () => ({
  authApi: { getMe: vi.fn(), updateProfile: vi.fn(), changePassword: vi.fn(), updateNotificationPreferences: vi.fn(), getNotificationPreferences: vi.fn() },
  subscriptionApi: { getCurrent: vi.fn(), getPlans: vi.fn(), billingTerm: vi.fn(), cancel: vi.fn(), reactivate: vi.fn(), addTruck: vi.fn(), removeTruck: vi.fn(), createCheckoutSession: vi.fn(), createPortalSession: vi.fn(), toggleAddon: vi.fn() },
  companyApi: { get: vi.fn(), update: vi.fn() },
  supportApi: { createTicket: vi.fn(), getTickets: vi.fn(), sendMessage: vi.fn() },
  devicesApi: { getDevices: vi.fn(), deactivateDevice: vi.fn() },
  blogApi: { getPosts: vi.fn(), getPost: vi.fn(), getAuthor: vi.fn(), getCategories: vi.fn() },
  adminBlogApi: { createPost: vi.fn(), updatePost: vi.fn(), deletePost: vi.fn() },
  organizationsApi: { getAll: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), getMembers: vi.fn(), inviteMember: vi.fn(), removeMember: vi.fn(), getInvitations: vi.fn(), acceptInvitation: vi.fn() },
  licensesApi: { getLicenses: vi.fn(), getLicense: vi.fn(), getDevices: vi.fn(), removeDevice: vi.fn() },
  changelogApi: { getEntries: vi.fn() },
  roadmapApi: { getItems: vi.fn() },
  statusApi: { getStatus: vi.fn() },
  tutorialsApi: { getTutorials: vi.fn(), getTutorial: vi.fn() },
  developersApi: { getResources: vi.fn(), getToolkitVersions: vi.fn() },
  securityApi: { getReports: vi.fn(), submitReport: vi.fn() },
  announcementsApi: { getAnnouncements: vi.fn() },
  customerStoriesApi: { getStories: vi.fn(), getStory: vi.fn() },
  careersApi: { getJobs: vi.fn(), getJob: vi.fn() },
  pressApi: { getReleases: vi.fn(), getKit: vi.fn() },
  partnersApi: { getPartners: vi.fn() },
  newsletterApi: { subscribe: vi.fn() },
  searchApi: { search: vi.fn() },
  notificationsApi: { getNotifications: vi.fn(), markRead: vi.fn(), markAllRead: vi.fn(), updatePreferences: vi.fn() },
  integrationsApi: { getIntegrations: vi.fn() },
  onboardingApi: { getChecklist: vi.fn(), completeStep: vi.fn() },
  invoicesApi: { getInvoices: vi.fn() },
  waitlistApi: { getCount: vi.fn(), listEntries: vi.fn() },
  mfaApi: { enroll: vi.fn(), confirm: vi.fn(), disable: vi.fn(), status: vi.fn() },
  avatarApi: { upload: vi.fn() },
  downloadApi: { getLatest: vi.fn(), getVersions: vi.fn() },
  adminApi: { getCompanyRowCounts: vi.fn() },
  sessionsApi: { getSessions: vi.fn(), revokeSession: vi.fn() },
  referralApi: { getMyReferrals: vi.fn(), getReferralStats: vi.fn(), createReferral: vi.fn() },
  auditLogApi: { list: vi.fn() },
  analyticsApi: { getFinancial: vi.fn() },
  opsApi: {
    getTickets: vi.fn(), getTicket: vi.fn(), getApprovals: vi.fn(), handleApproval: vi.fn(),
    getGuardrails: vi.fn(), resolveGuardrail: vi.fn(), getDashboard: vi.fn(),
    getKnowledgeDrafts: vi.fn(), approveKnowledgeDoc: vi.fn(), rejectKnowledgeDoc: vi.fn(),
  },
}))

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )
  }

  return { wrapper: Wrapper, queryClient }
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

// ─── Auth Hooks ─────────────────────────────────────────────────

describe("useProfile", () => {
  it("fetches profile", async () => {
    vi.mocked(authApi.getMe).mockResolvedValueOnce({ data: { user: { id: "1", name: "User" } } } as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useProfile(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(authApi.getMe).toHaveBeenCalled()
    expect(result.current.data).toEqual({ id: "1", name: "User" })
  })

  it("starts fetching on mount (no enabled guard)", () => {
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useProfile(), { wrapper })
    expect(result.current.isLoading).toBe(true)
    expect(authApi.getMe).toHaveBeenCalled()
  })
})

describe("useUpdateProfile", () => {
  it("calls updateProfile on mutate", async () => {
    vi.mocked(authApi.updateProfile).mockResolvedValueOnce({ data: { id: "1", name: "New" } } as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useUpdateProfile(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ name: "New", email: "n@c.com" })
    })

    expect(authApi.updateProfile).toHaveBeenCalledWith({ name: "New", email: "n@c.com" })
  })

  it("invalidates profile query on success", async () => {
    vi.mocked(authApi.updateProfile).mockResolvedValueOnce({} as any)

    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useUpdateProfile(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ name: "Test" })
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["profile"] })
  })
})

describe("useChangePassword", () => {
  it("calls changePassword on mutate", async () => {
    vi.mocked(authApi.changePassword).mockResolvedValueOnce({} as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useChangePassword(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ current_password: "old", new_password: "new" })
    })

    expect(authApi.changePassword).toHaveBeenCalledWith({ current_password: "old", new_password: "new" })
  })
})

// ─── Subscription Hooks ────────────────────────────────────────

describe("useSubscription", () => {
  it("returns stub data while backend endpoint is pending", async () => {
    vi.mocked(subscriptionApi.getCurrent).mockResolvedValueOnce({ data: { plan: "starter" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useSubscription(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual({ plan: "starter" })
    expect(result.current.isError).toBe(false)
  })
})

describe("usePlans", () => {
  it("returns stub data while backend endpoint is pending", async () => {
    vi.mocked(subscriptionApi.getPlans).mockResolvedValueOnce({ data: [{ id: "plan-1", name: "Starter" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePlans(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([{ id: "plan-1", name: "Starter" }])
    expect(result.current.isError).toBe(false)
  })
})

// ─── Company Hooks ─────────────────────────────────────────────

describe("useCompany", () => {
  it("fetches company", async () => {
    vi.mocked(companyApi.get).mockResolvedValueOnce({ data: { name: "My Co" } } as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCompany(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(companyApi.get).toHaveBeenCalled()
    expect(result.current.data).toEqual({ name: "My Co" })
  })
})

describe("useUpdateCompany", () => {
  it("calls company update on mutate", async () => {
    vi.mocked(companyApi.update).mockResolvedValueOnce({} as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useUpdateCompany(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ company_name: "New Co" })
    })

    expect(companyApi.update).toHaveBeenCalledWith({ company_name: "New Co" })
  })

  it("invalidates company query on success", async () => {
    vi.mocked(companyApi.update).mockResolvedValueOnce({} as any)

    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useUpdateCompany(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ company_name: "Updated" })
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["company"] })
  })
})

// ─── Support Hooks ─────────────────────────────────────────────

describe("useCreateTicket", () => {
  it("calls createTicket on mutate", async () => {
    vi.mocked(supportApi.createTicket).mockResolvedValueOnce({} as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCreateTicket(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ subject: "[Bug] Crash", description: "Details" })
    })

    expect(supportApi.createTicket).toHaveBeenCalledWith({ subject: "[Bug] Crash", description: "Details" })
  })

  it("invalidates tickets query on success", async () => {
    vi.mocked(supportApi.createTicket).mockResolvedValueOnce({} as any)

    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useCreateTicket(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ subject: "Test", description: "Test" })
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["tickets"] })
  })
})

describe("useTickets", () => {
  it("fetches tickets", async () => {
    vi.mocked(supportApi.getTickets).mockResolvedValueOnce({ data: [{ id: 1, subject: "Issue" }] } as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useTickets(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(supportApi.getTickets).toHaveBeenCalled()
  })
})

// ─── Blog Hooks ─────────────────────────────────────────────────

describe("useBlogPosts", () => {
  it("fetches blog posts with params", async () => {
    vi.mocked(blogApi.getPosts).mockResolvedValueOnce({ data: { items: [], total: 0, page: 1, page_size: 10 } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useBlogPosts({ page: 1 }), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(blogApi.getPosts).toHaveBeenCalledWith({ page: 1 })
  })

  it("fetches blog posts without params", async () => {
    vi.mocked(blogApi.getPosts).mockResolvedValueOnce({ data: { items: [] } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useBlogPosts(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(blogApi.getPosts).toHaveBeenCalledWith(undefined)
  })
})

describe("useBlogPost", () => {
  it("fetches blog post by slug", async () => {
    vi.mocked(blogApi.getPost).mockResolvedValueOnce({ data: { slug: "hello", title: "Hello" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useBlogPost("hello"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(blogApi.getPost).toHaveBeenCalledWith("hello")
  })

  it("does not fetch when slug is empty", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useBlogPost(""), { wrapper })
    expect(blogApi.getPost).not.toHaveBeenCalled()
  })
})

describe("useBlogCategories", () => {
  it("fetches blog categories", async () => {
    vi.mocked(blogApi.getCategories).mockResolvedValueOnce({ data: [{ id: 1, name: "Tech" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useBlogCategories(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(blogApi.getCategories).toHaveBeenCalled()
  })
})

// ─── Admin Blog Hooks ───────────────────────────────────────────

describe("useCreateBlogPost", () => {
  it("calls createPost on mutate", async () => {
    vi.mocked(adminBlogApi.createPost).mockResolvedValueOnce({ data: { id: "1" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCreateBlogPost(), { wrapper })
    const postData = { title: "New Post", content: "Content", slug: "new-post", excerpt: "Excerpt", category_id: "cat-1", published: true }
    await act(async () => {
      await result.current.mutateAsync(postData)
    })
    expect(adminBlogApi.createPost).toHaveBeenCalledWith(postData)
  })

  it("invalidates blog-posts query on success", async () => {
    vi.mocked(adminBlogApi.createPost).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useCreateBlogPost(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ title: "T", content: "C", excerpt: "E", category_id: "cat-1" })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["blog-posts"] })
  })
})

describe("useUpdateBlogPost", () => {
  it("calls updatePost on mutate", async () => {
    vi.mocked(adminBlogApi.updatePost).mockResolvedValueOnce({ data: { id: "1" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useUpdateBlogPost(), { wrapper })
    const slug = "my-post"
    const updateData = { title: "Updated Title", content: "Updated content" }
    await act(async () => {
      await result.current.mutateAsync({ slug, data: updateData })
    })
    expect(adminBlogApi.updatePost).toHaveBeenCalledWith(slug, updateData)
  })

  it("invalidates blog-posts query on success", async () => {
    vi.mocked(adminBlogApi.updatePost).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useUpdateBlogPost(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ slug: "p", data: { title: "T" } })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["blog-posts"] })
  })
})

describe("useDeleteBlogPost", () => {
  it("calls deletePost on mutate", async () => {
    vi.mocked(adminBlogApi.deletePost).mockResolvedValueOnce({} as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useDeleteBlogPost(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("post-to-delete")
    })
    expect(adminBlogApi.deletePost).toHaveBeenCalledWith("post-to-delete")
  })

  it("invalidates blog-posts query on success", async () => {
    vi.mocked(adminBlogApi.deletePost).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useDeleteBlogPost(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("slug")
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["blog-posts"] })
  })
})

// ─── Content Hooks ──────────────────────────────────────────────

describe("useChangelog", () => {
  it("fetches changelog entries", async () => {
    vi.mocked(changelogApi.getEntries).mockResolvedValueOnce({ data: [{ id: 1, title: "v2.0", date: "2026-01-01" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useChangelog(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(changelogApi.getEntries).toHaveBeenCalled()
  })
})

describe("useRoadmap", () => {
  it("fetches roadmap items with status filter", async () => {
    vi.mocked(roadmapApi.getItems).mockResolvedValueOnce({ data: [{ id: 1, title: "Feature", status: "planned" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useRoadmap("planned"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(roadmapApi.getItems).toHaveBeenCalledWith("planned")
  })

  it("fetches roadmap items without status", async () => {
    vi.mocked(roadmapApi.getItems).mockResolvedValueOnce({ data: [] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useRoadmap(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(roadmapApi.getItems).toHaveBeenCalledWith(undefined)
  })
})

describe("useServiceStatus", () => {
  it("fetches service status", async () => {
    vi.mocked(statusApi.getStatus).mockResolvedValueOnce({ data: { status: "operational", uptime: "99.9%" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useServiceStatus(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(statusApi.getStatus).toHaveBeenCalled()
  })
})

describe("useAnnouncements", () => {
  it("fetches announcements", async () => {
    vi.mocked(announcementsApi.getAnnouncements).mockResolvedValueOnce({ data: [{ id: 1, title: "Welcome", body: "Hello" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useAnnouncements(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(announcementsApi.getAnnouncements).toHaveBeenCalled()
  })
})

// ─── Invoices Stub ───────────────────────────────────────────────

describe("useInvoices", () => {
  it("returns stub data while backend endpoint is pending", async () => {
    vi.mocked(invoicesApi.getInvoices).mockResolvedValueOnce({ data: [{ id: 1, amount: 100 }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useInvoices(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([{ id: 1, amount: 100 }])
    expect(result.current.isError).toBe(false)
  })
})

// ─── Tutorial Hooks ─────────────────────────────────────────────

describe("useTutorials", () => {
  it("fetches tutorials with params", async () => {
    vi.mocked(tutorialsApi.getTutorials).mockResolvedValueOnce({ data: [{ id: 1, title: "Getting Started", slug: "getting-started" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useTutorials({ category: "getting-started" }), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(tutorialsApi.getTutorials).toHaveBeenCalledWith({ category: "getting-started" })
  })

  it("fetches tutorials without params", async () => {
    vi.mocked(tutorialsApi.getTutorials).mockResolvedValueOnce({ data: [] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useTutorials(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(tutorialsApi.getTutorials).toHaveBeenCalledWith(undefined)
  })
})

describe("useTutorial", () => {
  it("fetches tutorial by slug", async () => {
    vi.mocked(tutorialsApi.getTutorial).mockResolvedValueOnce({ data: { slug: "intro", title: "Intro Tutorial" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useTutorial("intro"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(tutorialsApi.getTutorial).toHaveBeenCalledWith("intro")
  })

  it("does not fetch when slug is empty", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useTutorial(""), { wrapper })
    expect(tutorialsApi.getTutorial).not.toHaveBeenCalled()
  })
})

// ─── Developer Resources Hooks ────────────────────────────────────

describe("useDevResources", () => {
  it("fetches developer resources", async () => {
    vi.mocked(developersApi.getResources).mockResolvedValueOnce({ data: [{ id: 1, title: "API Reference", type: "doc" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useDevResources(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(developersApi.getResources).toHaveBeenCalled()
  })
})

describe("useToolkitVersions", () => {
  it("fetches toolkit versions", async () => {
    vi.mocked(developersApi.getToolkitVersions).mockResolvedValueOnce({ data: [{ version: "1.0.0", release_date: "2026-01-01" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useToolkitVersions(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(developersApi.getToolkitVersions).toHaveBeenCalled()
  })
})

// ─── Security Hooks ────────────────────────────────────────────

describe("useSecurityReports", () => {
  it("fetches security reports", async () => {
    vi.mocked(securityApi.getReports).mockResolvedValueOnce({ data: [{ id: 1, title: "Audit Q1", severity: "low" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useSecurityReports(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(securityApi.getReports).toHaveBeenCalled()
  })
})

describe("useSubmitSecurityReport", () => {
  it("calls submitReport on mutate", async () => {
    vi.mocked(securityApi.submitReport).mockResolvedValueOnce({ data: { id: "report-1" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useSubmitSecurityReport(), { wrapper })
    const payload = { title: "XSS Vulnerability", description: "Found in login form", severity: "high" }
    await act(async () => {
      await result.current.mutateAsync(payload)
    })
    expect(securityApi.submitReport).toHaveBeenCalledWith(payload)
  })
})

// ─── Organization Hooks ─────────────────────────────────────────

describe("useOrganizations", () => {
  it("fetches organizations", async () => {
    vi.mocked(organizationsApi.getAll).mockResolvedValueOnce({ data: [{ slug: "org1", name: "Org 1" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useOrganizations(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(organizationsApi.getAll).toHaveBeenCalled()
  })
})

describe("useOrganization", () => {
  it("fetches organization by slug", async () => {
    vi.mocked(organizationsApi.get).mockResolvedValueOnce({ data: { slug: "my-org", name: "My Org" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useOrganization("my-org"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(organizationsApi.get).toHaveBeenCalledWith("my-org")
  })

  it("does not fetch when slug is empty", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useOrganization(""), { wrapper })
    expect(organizationsApi.get).not.toHaveBeenCalled()
  })
})

describe("useCreateOrganization", () => {
  it("calls create on mutate", async () => {
    vi.mocked(organizationsApi.create).mockResolvedValueOnce({ data: { slug: "new-org", id: 1 } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCreateOrganization(), { wrapper })
    const payload = { name: "New Org", slug: "new-org" }
    await act(async () => {
      await result.current.mutateAsync(payload)
    })
    expect(organizationsApi.create).toHaveBeenCalledWith(payload)
  })

  it("invalidates organizations query on success", async () => {
    vi.mocked(organizationsApi.create).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useCreateOrganization(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ name: "X", slug: "x" })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["organizations"] })
  })
})

describe("useUpdateOrganization", () => {
  it("calls update on mutate", async () => {
    vi.mocked(organizationsApi.update).mockResolvedValueOnce({} as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useUpdateOrganization(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ slug: "my-org", data: { name: "Updated Org" } })
    })
    expect(organizationsApi.update).toHaveBeenCalledWith("my-org", { name: "Updated Org" })
  })

  it("invalidates organizations query on success", async () => {
    vi.mocked(organizationsApi.update).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useUpdateOrganization(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ slug: "o", data: { name: "N" } })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["organizations"] })
  })
})

describe("useOrganizationMembers", () => {
  it("fetches organization members", async () => {
    vi.mocked(organizationsApi.getMembers).mockResolvedValueOnce({ data: [{ id: "user-1", name: "Alice", role: "admin" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useOrganizationMembers("my-org"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(organizationsApi.getMembers).toHaveBeenCalledWith("my-org")
  })

  it("does not fetch when slug is empty", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useOrganizationMembers(""), { wrapper })
    expect(organizationsApi.getMembers).not.toHaveBeenCalled()
  })
})

describe("useInviteMember", () => {
  it("calls inviteMember on mutate", async () => {
    vi.mocked(organizationsApi.inviteMember).mockResolvedValueOnce({} as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useInviteMember(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ slug: "my-org", data: { email: "user@example.com", role: "member" } })
    })
    expect(organizationsApi.inviteMember).toHaveBeenCalledWith("my-org", { email: "user@example.com", role: "member" })
  })

  it("invalidates invitations and members queries on success", async () => {
    vi.mocked(organizationsApi.inviteMember).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useInviteMember(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ slug: "o", data: { email: "a@b.com", role: "member" } })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["org-invitations"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["org-members"] })
  })
})

describe("useRemoveMember", () => {
  it("calls removeMember on mutate", async () => {
    vi.mocked(organizationsApi.removeMember).mockResolvedValueOnce({} as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useRemoveMember(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ slug: "my-org", memberId: "user-1" })
    })
    expect(organizationsApi.removeMember).toHaveBeenCalledWith("my-org", "user-1")
  })

  it("invalidates org-members query on success", async () => {
    vi.mocked(organizationsApi.removeMember).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useRemoveMember(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ slug: "o", memberId: "u" })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["org-members"] })
  })
})

describe("useOrganizationInvitations", () => {
  it("fetches organization invitations", async () => {
    vi.mocked(organizationsApi.getInvitations).mockResolvedValueOnce({ data: [{ id: "inv-1", email: "user@example.com", status: "pending" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useOrganizationInvitations("my-org"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(organizationsApi.getInvitations).toHaveBeenCalledWith("my-org")
  })

  it("does not fetch when slug is empty", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useOrganizationInvitations(""), { wrapper })
    expect(organizationsApi.getInvitations).not.toHaveBeenCalled()
  })
})

describe("useAcceptInvitation", () => {
  it("calls acceptInvitation on mutate", async () => {
    vi.mocked(organizationsApi.acceptInvitation).mockResolvedValueOnce({} as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useAcceptInvitation(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("token-abc-123")
    })
    expect(organizationsApi.acceptInvitation).toHaveBeenCalledWith("token-abc-123")
  })

  it("invalidates organizations query on success", async () => {
    vi.mocked(organizationsApi.acceptInvitation).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useAcceptInvitation(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("token")
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["organizations"] })
  })
})

// ─── Device Hooks ──────────────────────────────────────────────

describe("useDevices", () => {
  it("fetches devices", async () => {
    vi.mocked(devicesApi.getDevices).mockResolvedValueOnce({ data: [{ id: "dev-1", name: "Device 1", status: "active" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useDevices(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(devicesApi.getDevices).toHaveBeenCalled()
  })
})

describe("useDeactivateDevice", () => {
  it("calls deactivateDevice on mutate", async () => {
    vi.mocked(devicesApi.deactivateDevice).mockResolvedValueOnce({} as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useDeactivateDevice(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("dev-1")
    })
    expect(devicesApi.deactivateDevice).toHaveBeenCalledWith("dev-1")
  })

  it("invalidates devices query on success", async () => {
    vi.mocked(devicesApi.deactivateDevice).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useDeactivateDevice(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("dev-1")
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["devices"] })
  })
})

// ─── License Hooks ──────────────────────────────────────────────

describe("useLicenses", () => {
  it("fetches licenses", async () => {
    vi.mocked(licensesApi.getLicenses).mockResolvedValueOnce({ data: [{ id: 1, key: "LIC-001", status: "active" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useLicenses(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(licensesApi.getLicenses).toHaveBeenCalled()
  })
})

describe("useLicense", () => {
  it("fetches license by id", async () => {
    vi.mocked(licensesApi.getLicense).mockResolvedValueOnce({ data: { id: 1, key: "LIC-001", status: "active" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useLicense(1), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(licensesApi.getLicense).toHaveBeenCalledWith(1)
  })

  it("does not fetch when id is falsy", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useLicense(0 as any), { wrapper })
    expect(licensesApi.getLicense).not.toHaveBeenCalled()
  })
})

describe("useLicenseDevices", () => {
  it("fetches license devices", async () => {
    vi.mocked(licensesApi.getDevices).mockResolvedValueOnce({ data: [{ id: "dev-1", name: "Device 1" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useLicenseDevices(1), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(licensesApi.getDevices).toHaveBeenCalledWith(1)
  })

  it("does not fetch when licenseId is falsy", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useLicenseDevices(0 as any), { wrapper })
    expect(licensesApi.getDevices).not.toHaveBeenCalled()
  })
})

describe("useRemoveLicenseDevice", () => {
  it("calls removeDevice on mutate", async () => {
    vi.mocked(licensesApi.removeDevice).mockResolvedValueOnce({} as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useRemoveLicenseDevice(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ licenseId: 1, deviceId: "dev-1" })
    })
    expect(licensesApi.removeDevice).toHaveBeenCalledWith(1, "dev-1")
  })

  it("invalidates license-devices query on success", async () => {
    vi.mocked(licensesApi.removeDevice).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useRemoveLicenseDevice(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ licenseId: 1, deviceId: "d" })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["license-devices"] })
  })
})

// ─── Onboarding Hooks ──────────────────────────────────────────

describe("useOnboardingChecklist", () => {
  it("fetches onboarding checklist", async () => {
    vi.mocked(onboardingApi.getChecklist).mockResolvedValueOnce({ data: [{ id: "step-1", title: "Welcome", completed: false }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useOnboardingChecklist(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(onboardingApi.getChecklist).toHaveBeenCalled()
  })
})

describe("useCompleteOnboardingStep", () => {
  it("calls completeStep on mutate", async () => {
    vi.mocked(onboardingApi.completeStep).mockResolvedValueOnce({} as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCompleteOnboardingStep(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("step-1")
    })
    expect(onboardingApi.completeStep).toHaveBeenCalledWith("step-1")
  })

  it("invalidates onboarding query on success", async () => {
    vi.mocked(onboardingApi.completeStep).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useCompleteOnboardingStep(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("step-1")
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["onboarding"] })
  })
})

// ─── Integration Hooks ─────────────────────────────────────────

describe("useIntegrations", () => {
  it("fetches integrations with category filter", async () => {
    vi.mocked(integrationsApi.getIntegrations).mockResolvedValueOnce({ data: [{ id: 1, name: "Slack", category: "messaging" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useIntegrations("messaging"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(integrationsApi.getIntegrations).toHaveBeenCalledWith("messaging")
  })

  it("fetches integrations without category", async () => {
    vi.mocked(integrationsApi.getIntegrations).mockResolvedValueOnce({ data: [] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useIntegrations(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(integrationsApi.getIntegrations).toHaveBeenCalledWith(undefined)
  })
})

// ─── Career Hooks ──────────────────────────────────────────────

describe("useJobs", () => {
  it("fetches jobs", async () => {
    vi.mocked(careersApi.getJobs).mockResolvedValueOnce({ data: [{ id: "job-1", title: "Software Engineer", department: "Engineering" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useJobs(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(careersApi.getJobs).toHaveBeenCalled()
  })
})

describe("useJob", () => {
  it("fetches job by id", async () => {
    vi.mocked(careersApi.getJob).mockResolvedValueOnce({ data: { id: "job-1", title: "Engineer", description: "Role" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useJob("job-1"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(careersApi.getJob).toHaveBeenCalledWith("job-1")
  })

  it("does not fetch when id is empty", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useJob(""), { wrapper })
    expect(careersApi.getJob).not.toHaveBeenCalled()
  })
})

// ─── Customer Stories Hooks ─────────────────────────────────────

describe("useCustomerStories", () => {
  it("fetches customer stories with params", async () => {
    vi.mocked(customerStoriesApi.getStories).mockResolvedValueOnce({ data: [{ slug: "story-1", title: "Customer Story", company: "Acme" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCustomerStories({ featured: true }), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(customerStoriesApi.getStories).toHaveBeenCalledWith({ featured: true })
  })

  it("fetches customer stories without params", async () => {
    vi.mocked(customerStoriesApi.getStories).mockResolvedValueOnce({ data: [] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCustomerStories(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(customerStoriesApi.getStories).toHaveBeenCalledWith(undefined)
  })
})

describe("useCustomerStory", () => {
  it("fetches customer story by slug", async () => {
    vi.mocked(customerStoriesApi.getStory).mockResolvedValueOnce({ data: { slug: "acme-corp", title: "Acme Corp Story", company: "Acme" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCustomerStory("acme-corp"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(customerStoriesApi.getStory).toHaveBeenCalledWith("acme-corp")
  })

  it("does not fetch when slug is empty", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useCustomerStory(""), { wrapper })
    expect(customerStoriesApi.getStory).not.toHaveBeenCalled()
  })
})

// ─── Press Hooks ────────────────────────────────────────────────

describe("usePressReleases", () => {
  it("fetches press releases", async () => {
    vi.mocked(pressApi.getReleases).mockResolvedValueOnce({ data: [{ id: 1, title: "Product Launch", date: "2026-06-01" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePressReleases(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(pressApi.getReleases).toHaveBeenCalled()
  })
})

describe("usePressKit", () => {
  it("fetches press kit", async () => {
    vi.mocked(pressApi.getKit).mockResolvedValueOnce({ data: { logo_url: "https://example.com/logo.png", brand_guidelines: "..." } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePressKit(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(pressApi.getKit).toHaveBeenCalled()
  })
})

// ─── Partners Hooks ─────────────────────────────────────────────

describe("usePartners", () => {
  it("fetches partners with type filter", async () => {
    vi.mocked(partnersApi.getPartners).mockResolvedValueOnce({ data: [{ id: 1, name: "Tech Partner", type: "technology" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePartners("technology"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(partnersApi.getPartners).toHaveBeenCalledWith("technology")
  })

  it("fetches partners without type", async () => {
    vi.mocked(partnersApi.getPartners).mockResolvedValueOnce({ data: [] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePartners(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(partnersApi.getPartners).toHaveBeenCalledWith(undefined)
  })
})

// ─── Newsletter Hook ─────────────────────────────────────────────

describe("useSubscribeNewsletter", () => {
  it("calls subscribe on mutate", async () => {
    vi.mocked(newsletterApi.subscribe).mockResolvedValueOnce({ data: { id: "sub-1" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useSubscribeNewsletter(), { wrapper })
    const payload = { email: "test@example.com", name: "Test User", preferences: ["updates"] }
    await act(async () => {
      await result.current.mutateAsync(payload)
    })
    expect(newsletterApi.subscribe).toHaveBeenCalledWith(payload)
  })
})

// ─── Search Hook ─────────────────────────────────────────────────

describe("useGlobalSearch", () => {
  it("fetches search results", async () => {
    vi.mocked(searchApi.search).mockResolvedValueOnce({ data: { results: [{ id: 1, title: "Result 1", type: "page" }], total: 1 } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useGlobalSearch("query", "pages"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(searchApi.search).toHaveBeenCalledWith("query", "pages")
  })

  it("does not fetch when query is empty", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useGlobalSearch("", "pages"), { wrapper })
    expect(searchApi.search).not.toHaveBeenCalled()
  })
})

// ─── Notification Hooks ─────────────────────────────────────────

describe("usePortalNotifications", () => {
  it("fetches portal notifications", async () => {
    vi.mocked(notificationsApi.getNotifications).mockResolvedValueOnce({ data: [{ id: "n-1", message: "New feature available", read: false }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePortalNotifications(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(notificationsApi.getNotifications).toHaveBeenCalled()
  })
})

describe("useMarkNotificationRead", () => {
  it("calls markRead on mutate", async () => {
    vi.mocked(notificationsApi.markRead).mockResolvedValueOnce({} as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useMarkNotificationRead(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("n-1")
    })
    expect(notificationsApi.markRead).toHaveBeenCalledWith("n-1")
  })

  it("invalidates notifications query on success", async () => {
    vi.mocked(notificationsApi.markRead).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useMarkNotificationRead(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("n-1")
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["notifications"] })
  })
})

describe("useUpdateNotificationPreferences", () => {
  it("calls updatePreferences on mutate", async () => {
    vi.mocked(authApi.updateNotificationPreferences).mockResolvedValueOnce({} as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useUpdateNotificationPreferences(), { wrapper })
    const prefs = { email_notifications: true, push_enabled: false }
    await act(async () => {
      await result.current.mutateAsync(prefs)
    })
    expect(authApi.updateNotificationPreferences).toHaveBeenCalledWith(prefs)
  })
})

// ─── MFA Hooks ─────────────────────────────────────────────────

describe("useMfaEnroll", () => {
  it("calls mfaApi.enroll on mutate", async () => {
    vi.mocked(mfaApi.enroll).mockResolvedValueOnce({
      data: { secret: "JBSWY3DP", otpauth_uri: "otpauth://totp/Operion:test", qr_payload: "https://qr" },
    } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useMfaEnroll(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync()
    })
    expect(mfaApi.enroll).toHaveBeenCalled()
  })
})

describe("useMfaConfirm", () => {
  it("calls mfaApi.confirm with code and invalidates mfa-status", async () => {
    vi.mocked(mfaApi.confirm).mockResolvedValueOnce({
      data: { mfa_enabled: true, backup_codes: ["ABCD-1234", "EFGH-5678"] },
    } as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useMfaConfirm(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("123456")
    })
    expect(mfaApi.confirm).toHaveBeenCalledWith("123456")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["mfa-status"] })
  })
})

describe("useMfaDisable", () => {
  it("calls mfaApi.disable with password and invalidates mfa-status", async () => {
    vi.mocked(mfaApi.disable).mockResolvedValueOnce({ data: { mfa_enabled: false } } as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useMfaDisable(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("hunter2")
    })
    expect(mfaApi.disable).toHaveBeenCalledWith("hunter2")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["mfa-status"] })
  })
})

describe("useMfaStatus", () => {
  it("fetches mfa status", async () => {
    vi.mocked(mfaApi.status).mockResolvedValueOnce({ data: { mfa_enabled: false } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useMfaStatus(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mfaApi.status).toHaveBeenCalled()
    expect(result.current.data).toEqual({ mfa_enabled: false })
  })
})

// ─── Subscription lifecycle hooks ──────────────────────────────

describe("useUpdateBillingTerm", () => {
  it("calls subscriptionApi.billingTerm with term and invalidates subscription", async () => {
    vi.mocked(subscriptionApi.billingTerm).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useUpdateBillingTerm(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("annual")
    })
    expect(subscriptionApi.billingTerm).toHaveBeenCalledWith("annual")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["subscription"] })
  })
})

describe("useCancelSubscription", () => {
  it("calls subscriptionApi.cancel and invalidates subscription", async () => {
    vi.mocked(subscriptionApi.cancel).mockResolvedValueOnce({ data: { usable_until: "2026-09-01" } } as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useCancelSubscription(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync()
    })
    expect(subscriptionApi.cancel).toHaveBeenCalled()
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["subscription"] })
  })
})

describe("useReactivateSubscription", () => {
  it("calls subscriptionApi.reactivate and invalidates subscription", async () => {
    vi.mocked(subscriptionApi.reactivate).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useReactivateSubscription(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync()
    })
    expect(subscriptionApi.reactivate).toHaveBeenCalled()
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["subscription"] })
  })
})

describe("useAddTruck", () => {
  it("calls subscriptionApi.addTruck with truck_id and invalidates subscription", async () => {
    vi.mocked(subscriptionApi.addTruck).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useAddTruck(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ truckId: "truck-1", source: "desktop" })
    })
    expect(subscriptionApi.addTruck).toHaveBeenCalledWith("truck-1", "desktop")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["subscription"] })
  })
})

describe("useRemoveTruck", () => {
  it("calls subscriptionApi.removeTruck with truck_id and invalidates subscription", async () => {
    vi.mocked(subscriptionApi.removeTruck).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useRemoveTruck(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ truckId: "truck-1" })
    })
    expect(subscriptionApi.removeTruck).toHaveBeenCalledWith("truck-1", undefined)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["subscription"] })
  })
})

// ─── Waitlist count + avatar upload ───────────────────────────

describe("useWaitlistCount", () => {
  it("fetches the waitlist count", async () => {
    vi.mocked(waitlistApi.getCount).mockResolvedValueOnce({
      data: { count: 513, cached_at: "2026-08-02T00:00:00Z" },
    } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useWaitlistCount(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(waitlistApi.getCount).toHaveBeenCalled()
    expect(result.current.data).toEqual({ count: 513, cached_at: "2026-08-02T00:00:00Z" })
  })
})

describe("useAvatarUpload", () => {
  it("calls avatarApi.upload with the file and invalidates profile", async () => {
    vi.mocked(avatarApi.upload).mockResolvedValueOnce({
      data: { avatar_url: "https://cdn.operion.dev/avatars/u.png" },
    } as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useAvatarUpload(), { wrapper })
    const file = new File(["binary"], "avatar.png", { type: "image/png" })
    await act(async () => {
      await result.current.mutateAsync(file)
    })
    expect(avatarApi.upload).toHaveBeenCalledWith(file)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["profile"] })
  })

  it("propagates upload errors", async () => {
    vi.mocked(avatarApi.upload).mockRejectedValueOnce(new Error("upload failed"))

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useAvatarUpload(), { wrapper })

    await act(async () => {
      await expect(result.current.mutateAsync(new File(["x"], "x.png"))).rejects.toThrow("upload failed")
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

// ─── Support message ─────────────────────────────────────────

describe("useSendSupportMessage", () => {
  it("calls sendMessage on mutate", async () => {
    vi.mocked(supportApi.sendMessage).mockResolvedValueOnce({
      data: { conversation_id: "conv-1", reply: "Got it", requires_action: false, escalated: false },
    } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useSendSupportMessage(), { wrapper })
    const payload = { conversation_id: "conv-1", message: "Hello", channel: "chat" as const }
    await act(async () => {
      await result.current.mutateAsync(payload)
    })
    expect(supportApi.sendMessage).toHaveBeenCalledWith(payload)
    await waitFor(() => {
      expect(result.current.data).toEqual({ conversation_id: "conv-1", reply: "Got it", requires_action: false, escalated: false })
    })
  })
})

// ─── Blog author ─────────────────────────────────────────────

describe("useBlogAuthor", () => {
  it("fetches blog author by id", async () => {
    vi.mocked(blogApi.getAuthor).mockResolvedValueOnce({ data: { id: 5, name: "Jane Doe", role: "Editor" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useBlogAuthor(5), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(blogApi.getAuthor).toHaveBeenCalledWith(5)
    expect(result.current.data).toEqual({ id: 5, name: "Jane Doe", role: "Editor" })
  })

  it("does not fetch when id is undefined", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useBlogAuthor(undefined), { wrapper })
    expect(blogApi.getAuthor).not.toHaveBeenCalled()
  })
})

// ─── Stripe checkout ─────────────────────────────────────────

describe("useCreateCheckoutSession", () => {
  it("calls createCheckoutSession on mutate", async () => {
    vi.mocked(subscriptionApi.createCheckoutSession).mockResolvedValueOnce({
      data: { url: "https://checkout.example.com/s/1", session_id: "cs_1" },
    } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCreateCheckoutSession(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync()
    })
    expect(subscriptionApi.createCheckoutSession).toHaveBeenCalled()
    await waitFor(() => {
      expect(result.current.data).toEqual({ data: { url: "https://checkout.example.com/s/1", session_id: "cs_1" } })
    })
  })

  it("propagates checkout errors", async () => {
    vi.mocked(subscriptionApi.createCheckoutSession).mockRejectedValueOnce(new Error("checkout failed"))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCreateCheckoutSession(), { wrapper })
    await act(async () => {
      await expect(result.current.mutateAsync()).rejects.toThrow("checkout failed")
    })
  })
})

describe("useCreatePortalSession", () => {
  it("calls createPortalSession on mutate", async () => {
    vi.mocked(subscriptionApi.createPortalSession).mockResolvedValueOnce({ data: { url: "https://billing.example.com/p" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCreatePortalSession(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync()
    })
    expect(subscriptionApi.createPortalSession).toHaveBeenCalled()
  })
})

describe("useToggleAddon", () => {
  it("calls toggleAddon on mutate", async () => {
    vi.mocked(subscriptionApi.toggleAddon).mockResolvedValueOnce({ data: { plan: "pro" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useToggleAddon(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ addon: "ai_copilot", enabled: true })
    })
    expect(subscriptionApi.toggleAddon).toHaveBeenCalledWith({ addon: "ai_copilot", enabled: true })
  })

  it("invalidates subscription query on success", async () => {
    vi.mocked(subscriptionApi.toggleAddon).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useToggleAddon(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ addon: "priority_support", enabled: false })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["subscription"] })
  })

  it("propagates toggle errors", async () => {
    vi.mocked(subscriptionApi.toggleAddon).mockRejectedValueOnce(new Error("toggle failed"))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useToggleAddon(), { wrapper })
    await act(async () => {
      await expect(result.current.mutateAsync({ addon: "api_access", enabled: true })).rejects.toThrow("toggle failed")
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

// ─── Downloads ───────────────────────────────────────────────

describe("useLatestDownload", () => {
  it("fetches the latest desktop release", async () => {
    vi.mocked(downloadApi.getLatest).mockResolvedValueOnce({ data: { version: "2.4.1", url: "https://dl" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useLatestDownload(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(downloadApi.getLatest).toHaveBeenCalled()
    expect(result.current.data).toEqual({ version: "2.4.1", url: "https://dl" })
  })
})

describe("useDownloadVersions", () => {
  it("fetches all download versions", async () => {
    vi.mocked(downloadApi.getVersions).mockResolvedValueOnce({ data: [{ version: "2.4.1" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useDownloadVersions(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(downloadApi.getVersions).toHaveBeenCalled()
  })
})

// ─── Admin row counts ────────────────────────────────────────

describe("useAdminCompanyRowCounts", () => {
  it("fetches company row counts", async () => {
    vi.mocked(adminApi.getCompanyRowCounts).mockResolvedValueOnce({ users: 120, companies: 30 })
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useAdminCompanyRowCounts(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(adminApi.getCompanyRowCounts).toHaveBeenCalled()
    expect(result.current.data).toEqual({ users: 120, companies: 30 })
  })
})

// ─── Auth sessions ───────────────────────────────────────────

describe("useSessions", () => {
  it("fetches auth sessions", async () => {
    vi.mocked(sessionsApi.getSessions).mockResolvedValueOnce({ data: { sessions: [{ id: 1, device: "Desktop" }] } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useSessions(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(sessionsApi.getSessions).toHaveBeenCalled()
    expect(result.current.data).toEqual([{ id: 1, device: "Desktop" }])
  })
})

describe("useRevokeSession", () => {
  it("calls revokeSession on mutate", async () => {
    vi.mocked(sessionsApi.revokeSession).mockResolvedValueOnce({} as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useRevokeSession(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync(42)
    })
    expect(sessionsApi.revokeSession).toHaveBeenCalledWith(42)
  })

  it("invalidates auth-sessions query on success", async () => {
    vi.mocked(sessionsApi.revokeSession).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useRevokeSession(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync(1)
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["auth-sessions"] })
  })
})

// ─── Referrals ───────────────────────────────────────────────

describe("useReferrals", () => {
  it("fetches my referrals", async () => {
    vi.mocked(referralApi.getMyReferrals).mockResolvedValueOnce({ data: [{ code: "REF-1" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useReferrals(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(referralApi.getMyReferrals).toHaveBeenCalled()
  })
})

describe("useReferralStats", () => {
  it("fetches referral stats", async () => {
    vi.mocked(referralApi.getReferralStats).mockResolvedValueOnce({ data: { total_referrals: 3, completed_referrals: 1, pending_referrals: 2, rewards_earned: 10 } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useReferralStats(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(referralApi.getReferralStats).toHaveBeenCalled()
  })
})

describe("useCreateReferral", () => {
  it("calls createReferral on mutate", async () => {
    vi.mocked(referralApi.createReferral).mockResolvedValueOnce({ data: { status: "created" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCreateReferral(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ referred_email: "friend@example.com" })
    })
    expect(referralApi.createReferral).toHaveBeenCalledWith({ referred_email: "friend@example.com" })
  })

  it("invalidates referrals query on success", async () => {
    vi.mocked(referralApi.createReferral).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useCreateReferral(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ referred_email: "x@example.com" })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["referrals"] })
  })
})

// ─── Audit log ───────────────────────────────────────────────

describe("useWriteAuditLog", () => {
  it("posts to the audit log endpoint on mutate", async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: { status: "ok" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useWriteAuditLog(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ action: "export.csv", target_type: "company", target_id: "c-1", metadata: { rows: "42" } })
    })
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/audit-log", {
      action: "export.csv",
      target_type: "company",
      target_id: "c-1",
      metadata: { rows: "42" },
    })
  })
})

describe("useAuditLog", () => {
  it("fetches audit log entries with filters", async () => {
    vi.mocked(auditLogApi.list).mockResolvedValueOnce({ entries: [{ id: 1, action: "login" }], total: 1, page: 1, per_page: 25 } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useAuditLog({ page: 1, per_page: 25 }), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(auditLogApi.list).toHaveBeenCalledWith({ page: 1, per_page: 25 })
    expect(result.current.data).toEqual({ entries: [{ id: 1, action: "login" }], total: 1, page: 1, per_page: 25 })
  })
})

// ─── Waitlist entries ────────────────────────────────────────

describe("useWaitlistEntries", () => {
  it("fetches waitlist entries with params", async () => {
    vi.mocked(waitlistApi.listEntries).mockResolvedValueOnce({ data: { entries: [{ id: 1, email: "a@b.com" }], total: 1 } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useWaitlistEntries({ status: "pending", page: 2 }), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(waitlistApi.listEntries).toHaveBeenCalledWith({ status: "pending", page: 2 })
  })

  it("fetches waitlist entries without params", async () => {
    vi.mocked(waitlistApi.listEntries).mockResolvedValueOnce({ data: { entries: [], total: 0 } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useWaitlistEntries(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(waitlistApi.listEntries).toHaveBeenCalledWith(undefined)
  })
})

// ─── Financial analytics ─────────────────────────────────────

describe("useFinancialAnalytics", () => {
  it("fetches financial analytics with date range", async () => {
    vi.mocked(analyticsApi.getFinancial).mockResolvedValueOnce({ revenue: 1000, costs: 400 })
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useFinancialAnalytics("2026-01-01", "2026-02-01"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(analyticsApi.getFinancial).toHaveBeenCalledWith({ date_from: "2026-01-01", date_to: "2026-02-01" })
    expect(result.current.data).toEqual({ revenue: 1000, costs: 400 })
  })
})

// ─── Notification prefs + mark all ───────────────────────────

describe("useMarkAllRead", () => {
  it("calls markAllRead on mutate", async () => {
    vi.mocked(notificationsApi.markAllRead).mockResolvedValueOnce({ data: { status: "ok" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useMarkAllRead(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync()
    })
    expect(notificationsApi.markAllRead).toHaveBeenCalled()
  })

  it("invalidates notifications query on success", async () => {
    vi.mocked(notificationsApi.markAllRead).mockResolvedValueOnce({} as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useMarkAllRead(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync()
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["notifications"] })
  })
})

describe("useNotificationPreferences", () => {
  it("fetches notification preferences", async () => {
    vi.mocked(authApi.getNotificationPreferences).mockResolvedValueOnce({ data: { email_notifications: true, push_enabled: false } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useNotificationPreferences(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(authApi.getNotificationPreferences).toHaveBeenCalled()
    expect(result.current.data).toEqual({ data: { email_notifications: true, push_enabled: false } })
  })
})

// ─── Portal notification mapping + error path ────────────────

describe("usePortalNotifications edge cases", () => {
  it("maps every API type to a portal type and falls back to system for unknown", async () => {
    vi.mocked(notificationsApi.getNotifications).mockResolvedValueOnce({
      data: [
        { id: "1", type: "info", title: "T", message: "M", is_read: false, created_at: "2026-01-01T00:00:00Z" },
        { id: "2", type: "warning", title: "T", message: "M", is_read: true, link_url: "https://x", created_at: "2026-01-01T00:00:00Z" },
        { id: "3", type: "success", title: "T", message: "M", is_read: false, created_at: "2026-01-01T00:00:00Z" },
        { id: "4", type: "error", title: "T", message: "M", is_read: false, created_at: "2026-01-01T00:00:00Z" },
        { id: "5", type: "info", title: "T", message: "M", is_read: false, created_at: "2026-01-01T00:00:00Z" },
      ],
    } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePortalNotifications(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([
      { id: "1", type: "system", title: "T", message: "M", read: false, link: undefined, created_at: "2026-01-01T00:00:00Z" },
      { id: "2", type: "security", title: "T", message: "M", read: true, link: "https://x", created_at: "2026-01-01T00:00:00Z" },
      { id: "3", type: "release", title: "T", message: "M", read: false, link: undefined, created_at: "2026-01-01T00:00:00Z" },
      { id: "4", type: "support", title: "T", message: "M", read: false, link: undefined, created_at: "2026-01-01T00:00:00Z" },
      { id: "5", type: "system", title: "T", message: "M", read: false, link: undefined, created_at: "2026-01-01T00:00:00Z" },
    ])
  })

  it("returns an empty list when the API responds with null", async () => {
    vi.mocked(notificationsApi.getNotifications).mockResolvedValueOnce({ data: null } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePortalNotifications(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([])
  })

  it("surfaces API errors", async () => {
    vi.mocked(notificationsApi.getNotifications).mockRejectedValueOnce(new Error("notifications down"))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePortalNotifications(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

// ─── Mutation + query error paths ────────────────────────────

describe("mutation error paths", () => {
  it("useUpdateBillingTerm propagates failures", async () => {
    vi.mocked(subscriptionApi.billingTerm).mockRejectedValueOnce(new Error("billing term failed"))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useUpdateBillingTerm(), { wrapper })
    await act(async () => {
      await expect(result.current.mutateAsync("annual")).rejects.toThrow("billing term failed")
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it("useCancelSubscription propagates failures", async () => {
    vi.mocked(subscriptionApi.cancel).mockRejectedValueOnce(new Error("cancel failed"))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCancelSubscription(), { wrapper })
    await act(async () => {
      await expect(result.current.mutateAsync()).rejects.toThrow("cancel failed")
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it("useMfaEnroll propagates failures", async () => {
    vi.mocked(mfaApi.enroll).mockRejectedValueOnce(new Error("enroll failed"))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useMfaEnroll(), { wrapper })
    await act(async () => {
      await expect(result.current.mutateAsync()).rejects.toThrow("enroll failed")
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it("useMfaConfirm propagates failures", async () => {
    vi.mocked(mfaApi.confirm).mockRejectedValueOnce(new Error("invalid code"))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useMfaConfirm(), { wrapper })
    await act(async () => {
      await expect(result.current.mutateAsync("000000")).rejects.toThrow("invalid code")
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it("useMfaDisable propagates failures", async () => {
    vi.mocked(mfaApi.disable).mockRejectedValueOnce(new Error("wrong password"))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useMfaDisable(), { wrapper })
    await act(async () => {
      await expect(result.current.mutateAsync("nope")).rejects.toThrow("wrong password")
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it("useWaitlistCount surfaces API errors", async () => {
    vi.mocked(waitlistApi.getCount).mockRejectedValueOnce(new Error("count endpoint down"))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useWaitlistCount(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeInstanceOf(Error)
  })
})

// ─── Ops console hooks ───────────────────────────────────────

describe("useOpsTickets", () => {
  it("fetches ops tickets with filters", async () => {
    vi.mocked(opsApi.getTickets).mockResolvedValueOnce({ data: [{ id: "t1", subject: "Risk", risk_tier: "high" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useOpsTickets({ risk_tier: "high", status: "open" }), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(opsApi.getTickets).toHaveBeenCalledWith({ risk_tier: "high", status: "open" })
  })
})

describe("useOpsTicket", () => {
  it("fetches a single ops ticket", async () => {
    vi.mocked(opsApi.getTicket).mockResolvedValueOnce({ data: { id: "t1", subject: "Risk" } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useOpsTicket("t1"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(opsApi.getTicket).toHaveBeenCalledWith("t1")
  })

  it("does not fetch when id is empty", () => {
    const { wrapper } = createWrapper()
    renderHook(() => useOpsTicket(""), { wrapper })
    expect(opsApi.getTicket).not.toHaveBeenCalled()
  })
})

describe("useOpsApprovals", () => {
  it("fetches ops approvals", async () => {
    vi.mocked(opsApi.getApprovals).mockResolvedValueOnce({ data: [{ id: "a1", status: "pending" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useOpsApprovals(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(opsApi.getApprovals).toHaveBeenCalled()
  })
})

describe("useOpsHandleApproval", () => {
  it("calls handleApproval and invalidates ops-approvals", async () => {
    vi.mocked(opsApi.handleApproval).mockResolvedValueOnce({ data: { status: "ok", new_status: "approved" } } as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useOpsHandleApproval(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ id: "a1", action: "approve" })
    })
    expect(opsApi.handleApproval).toHaveBeenCalledWith("a1", "approve")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["ops-approvals"] })
  })
})

describe("useOpsGuardrails", () => {
  it("fetches guardrail violations", async () => {
    vi.mocked(opsApi.getGuardrails).mockResolvedValueOnce({ data: [{ id: 1, rule: "max-load" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useOpsGuardrails(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(opsApi.getGuardrails).toHaveBeenCalled()
  })
})

describe("useOpsResolveGuardrail", () => {
  it("calls resolveGuardrail and invalidates ops-guardrails", async () => {
    vi.mocked(opsApi.resolveGuardrail).mockResolvedValueOnce({ data: { status: "ok" } } as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useOpsResolveGuardrail(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync(7)
    })
    expect(opsApi.resolveGuardrail).toHaveBeenCalledWith(7)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["ops-guardrails"] })
  })
})

describe("useOpsDashboard", () => {
  it("fetches the ops dashboard summary", async () => {
    vi.mocked(opsApi.getDashboard).mockResolvedValueOnce({ data: { open_tickets: 3 } } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useOpsDashboard(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(opsApi.getDashboard).toHaveBeenCalled()
  })
})

describe("useOpsKnowledgeDrafts", () => {
  it("fetches knowledge doc drafts", async () => {
    vi.mocked(opsApi.getKnowledgeDrafts).mockResolvedValueOnce({ data: [{ id: "d1", title: "Draft" }] } as any)
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useOpsKnowledgeDrafts(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(opsApi.getKnowledgeDrafts).toHaveBeenCalled()
  })
})

describe("useOpsApproveKnowledgeDoc", () => {
  it("calls approveKnowledgeDoc and invalidates drafts", async () => {
    vi.mocked(opsApi.approveKnowledgeDoc).mockResolvedValueOnce({ data: { status: "ok" } } as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useOpsApproveKnowledgeDoc(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("d1")
    })
    expect(opsApi.approveKnowledgeDoc).toHaveBeenCalledWith("d1")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["ops-knowledge-drafts"] })
  })
})

describe("useOpsRejectKnowledgeDoc", () => {
  it("calls rejectKnowledgeDoc and invalidates drafts", async () => {
    vi.mocked(opsApi.rejectKnowledgeDoc).mockResolvedValueOnce({ data: { status: "ok" } } as any)
    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useOpsRejectKnowledgeDoc(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync("d2")
    })
    expect(opsApi.rejectKnowledgeDoc).toHaveBeenCalledWith("d2")
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["ops-knowledge-drafts"] })
  })
})
