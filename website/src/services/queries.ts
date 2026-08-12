import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import apiClient from "@/api/client"
import { authApi, companyApi, devicesApi, sessionsApi, supportApi, blogApi, adminBlogApi, organizationsApi, licensesApi,
  changelogApi, roadmapApi, statusApi, tutorialsApi, developersApi, securityApi, announcementsApi,
  customerStoriesApi, careersApi, pressApi, partnersApi, newsletterApi, searchApi, notificationsApi,
  integrationsApi, onboardingApi, opsApi, referralApi, waitlistApi, auditLogApi, adminApi,
  subscriptionApi, downloadApi, invoicesApi, analyticsApi, mfaApi, avatarApi } from "@/api/endpoints"
import type { CompanyUpdateRequest, NotificationPreference, PortalNotification } from "@/types"
import type { CreateTicketRequest, CreateBlogPostRequest, UpdateBlogPostRequest, CreateOrganizationRequest, UpdateOrganizationRequest, InviteMemberRequest, SupportMessageRequest, AppNotification } from "@/api/endpoints"

// ─── Auth ────────────────────────────────────────────────────

export function useProfile() {
  return useQuery({
    queryKey: ['profile'],
    queryFn: async () => {
      const { data } = await authApi.getMe()
      return data.user
    },
    staleTime: 5 * 60 * 1000, // 5 min
  })
}

export function useUpdateProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { name?: string; email?: string }) => authApi.updateProfile(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['profile'] }),
  })
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: { current_password: string; new_password: string }) =>
      authApi.changePassword(data),
  })
}

// ─── MFA (Two-Factor Authentication) ────────────────────────

export function useMfaEnroll() {
  return useMutation({
    mutationFn: () => mfaApi.enroll(),
  })
}

export function useMfaConfirm() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (code: string) => mfaApi.confirm(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mfa-status"] })
    },
  })
}

export function useMfaDisable() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (password: string) => mfaApi.disable(password),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mfa-status"] })
    },
  })
}

export function useMfaStatus() {
  return useQuery({
    queryKey: ["mfa-status"],
    queryFn: () => mfaApi.status().then((r) => r.data),
    staleTime: 60 * 1000,
  })
}

// ─── Avatar ─────────────────────────────────────────────────

export function useAvatarUpload() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => avatarApi.upload(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] })
    },
  })
}

// ─── Subscription ────────────────────────────────────────────

export function useSubscription() {
  return useQuery({
    queryKey: ["subscription"],
    queryFn: () => subscriptionApi.getCurrent().then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  })
}

export function usePlans() {
  return useQuery({
    queryKey: ["plans"],
    queryFn: () => subscriptionApi.getPlans().then((r) => r.data),
    staleTime: 30 * 60 * 1000,
  })
}

// ─── Company ─────────────────────────────────────────────────

export function useCompany() {
  return useQuery({
    queryKey: ['company'],
    queryFn: async () => {
      const { data } = await companyApi.get()
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

export function useUpdateCompany() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CompanyUpdateRequest) => companyApi.update(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['company'] }),
  })
}

// ─── Support ─────────────────────────────────────────────────

export function useCreateTicket() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateTicketRequest) => supportApi.createTicket(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tickets'] }),
  })
}

export function useSendSupportMessage() {
  return useMutation({
    mutationFn: (data: SupportMessageRequest) =>
      supportApi.sendMessage(data).then((r) => r.data),
  })
}

export function useTickets() {
  return useQuery({
    queryKey: ['tickets'],
    queryFn: async () => {
      const { data } = await supportApi.getTickets()
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

// ─── Blog ────────────────────────────────────────────────────

export function useBlogPosts(params?: Record<string, unknown>) {
  return useQuery({
    queryKey: ['blog-posts', params],
    queryFn: async () => {
      const { data } = await blogApi.getPosts(params as any)
      return data
    },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}

export function useBlogPost(slug: string) {
  return useQuery({
    queryKey: ['blog-post', slug],
    queryFn: async () => {
      const { data } = await blogApi.getPost(slug)
      return data
    },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
    enabled: !!slug,
  })
}

export function useBlogAuthor(id: string | number | undefined) {
  return useQuery({
    queryKey: ['blog-author', id],
    queryFn: async () => {
      const { data } = await blogApi.getAuthor(id!)
      return data
    },
    enabled: !!id,
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}

export function useBlogCategories() {
  return useQuery({
    queryKey: ['blog-categories'],
    queryFn: async () => {
      const { data } = await blogApi.getCategories()
      return data
    },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}

// ─── Changelog ──────────────────────────────────────────────

export function useChangelog() {
  return useQuery({
    queryKey: ['changelog'],
    queryFn: async () => { const { data } = await changelogApi.getEntries(); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}

// ─── Roadmap ────────────────────────────────────────────────

export function useRoadmap(status?: string) {
  return useQuery({
    queryKey: ['roadmap', status],
    queryFn: async () => { const { data } = await roadmapApi.getItems(status); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}

// ─── Service Status ─────────────────────────────────────────

export function useServiceStatus() {
  return useQuery({
    queryKey: ['service-status'],
    queryFn: async () => { const { data } = await statusApi.getStatus(); return data },
    staleTime: 30 * 1000,
  })
}

// ─── Tutorials ──────────────────────────────────────────────

export function useTutorials(params?: Record<string, unknown>) {
  return useQuery({
    queryKey: ['tutorials', params],
    queryFn: async () => { const { data } = await tutorialsApi.getTutorials(params as any); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
export function useTutorial(slug: string) {
  return useQuery({
    queryKey: ['tutorial', slug],
    queryFn: async () => { const { data } = await tutorialsApi.getTutorial(slug); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
    enabled: !!slug,
  })
}

// ─── Developer Resources ────────────────────────────────────

export function useDevResources() {
  return useQuery({
    queryKey: ['dev-resources'],
    queryFn: async () => { const { data } = await developersApi.getResources(); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
export function useToolkitVersions() {
  return useQuery({
    queryKey: ['toolkit-versions'],
    queryFn: async () => { const { data } = await developersApi.getToolkitVersions(); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}

// ─── Security Reports ──────────────────────────────────────

export function useSecurityReports() {
  return useQuery({
    queryKey: ['security-reports'],
    queryFn: async () => { const { data } = await securityApi.getReports(); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
export function useSubmitSecurityReport() {
  return useMutation({ mutationFn: (data: { title: string; description: string; severity: string }) => securityApi.submitReport(data) })
}

// ─── Announcements ──────────────────────────────────────────

export function useAnnouncements() {
  return useQuery({
    queryKey: ['announcements'],
    queryFn: async () => { const { data } = await announcementsApi.getAnnouncements(); return data },
    staleTime: 5 * 60 * 1000,
  })
}

// ─── Stripe Checkout ───────────────────────────────────────

export function useCreateCheckoutSession() {
  return useMutation({
    mutationFn: () => subscriptionApi.createCheckoutSession(),
  })
}

export function useCreatePortalSession() {
  return useMutation({
    mutationFn: () => subscriptionApi.createPortalSession(),
  })
}

export function useToggleAddon() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { addon: "ai_copilot" | "priority_support" | "api_access"; enabled: boolean }) =>
      subscriptionApi.toggleAddon(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription"] })
    },
  })
}

// ─── Subscription lifecycle (billing term / cancel / trucks) ──

export function useUpdateBillingTerm() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (term: "monthly" | "annual") => subscriptionApi.billingTerm(term),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription"] })
      queryClient.invalidateQueries({ queryKey: ["invoices"] })
    },
  })
}

export function useCancelSubscription() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => subscriptionApi.cancel(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription"] })
    },
  })
}

export function useReactivateSubscription() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => subscriptionApi.reactivate(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription"] })
    },
  })
}

export function useAddTruck() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ truckId, source }: { truckId: string; source?: string }) =>
      subscriptionApi.addTruck(truckId, source),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription"] })
    },
  })
}

export function useRemoveTruck() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ truckId, source }: { truckId: string; source?: string }) =>
      subscriptionApi.removeTruck(truckId, source),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription"] })
    },
  })
}

// ─── Invoices ──────────────────────────────────────────────

export function useInvoices() {
  return useQuery({
    queryKey: ["invoices"],
    queryFn: () => invoicesApi.getInvoices().then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  })
}

// ─── Downloads ─────────────────────────────────────────────

export function useLatestDownload() {
  return useQuery({
    queryKey: ["latest-download"],
    queryFn: () => downloadApi.getLatest().then((r) => r.data),
    staleTime: 30 * 60 * 1000,
  })
}

export function useDownloadVersions() {
  return useQuery({
    queryKey: ["download-versions"],
    queryFn: () => downloadApi.getVersions().then((r) => r.data),
    staleTime: 30 * 60 * 1000,
  })
}

// ─── Admin Blog ────────────────────────────────────────────

export function useCreateBlogPost() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateBlogPostRequest) => adminBlogApi.createPost(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['blog-posts'] })
    },
  })
}

export function useUpdateBlogPost() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ slug, data }: { slug: string; data: UpdateBlogPostRequest }) =>
      adminBlogApi.updatePost(slug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['blog-posts'] })
    },
  })
}

export function useDeleteBlogPost() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (slug: string) => adminBlogApi.deletePost(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['blog-posts'] })
    },
  })
}

// ─── Admin ───────────────────────────────────────────────────

export function useAdminCompanyRowCounts() {
  return useQuery({
    queryKey: ["admin-company-row-counts"],
    queryFn: () => adminApi.getCompanyRowCounts(),
    staleTime: 5 * 60 * 1000,
  })
}

// ─── Organizations ────────────────────────────────────────────

export function useOrganizations() {
  return useQuery({
    queryKey: ['organizations'],
    queryFn: async () => {
      const { data } = await organizationsApi.getAll()
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

export function useOrganization(slug: string) {
  return useQuery({
    queryKey: ['organization', slug],
    queryFn: async () => {
      const { data } = await organizationsApi.get(slug)
      return data
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!slug,
  })
}

export function useCreateOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateOrganizationRequest) => organizationsApi.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['organizations'] }),
  })
}

export function useUpdateOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ slug, data }: { slug: string; data: UpdateOrganizationRequest }) =>
      organizationsApi.update(slug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] })
    },
  })
}

export function useOrganizationMembers(slug: string) {
  return useQuery({
    queryKey: ['org-members', slug],
    queryFn: async () => {
      const { data } = await organizationsApi.getMembers(slug)
      return data
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!slug,
  })
}

export function useInviteMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ slug, data }: { slug: string; data: InviteMemberRequest }) =>
      organizationsApi.inviteMember(slug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-invitations'] })
      queryClient.invalidateQueries({ queryKey: ['org-members'] })
    },
  })
}

export function useRemoveMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ slug, memberId }: { slug: string; memberId: string }) =>
      organizationsApi.removeMember(slug, memberId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['org-members'] }),
  })
}

export function useOrganizationInvitations(slug: string) {
  return useQuery({
    queryKey: ['org-invitations', slug],
    queryFn: async () => {
      const { data } = await organizationsApi.getInvitations(slug)
      return data
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!slug,
  })
}

export function useAcceptInvitation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (token: string) => organizationsApi.acceptInvitation(token),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['organizations'] }),
  })
}

// ─── Devices ────────────────────────────────────────────────────

export function useDevices() {
  return useQuery({
    queryKey: ['devices'],
    queryFn: () => devicesApi.getDevices().then(res => res.data),
    staleTime: 30 * 1000,
  })
}

export function useDeactivateDevice() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (deviceId: string) => devicesApi.deactivateDevice(deviceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['devices'] }),
  })
}

// ─── Auth Sessions (desktop app login tracking) ─────────────
export function useSessions() {
  return useQuery({
    queryKey: ["auth-sessions"],
    queryFn: async () => {
      const res = await sessionsApi.getSessions()
      return res.data.sessions
    },
    staleTime: 30 * 1000,
  })
}

export function useRevokeSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: number) => sessionsApi.revokeSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth-sessions"] })
    },
  })
}

// ─── Licensing ────────────────────────────────────────────────

export function useLicenses() {
  return useQuery({
    queryKey: ['licenses'],
    queryFn: async () => {
      const { data } = await licensesApi.getLicenses()
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

export function useLicense(id: string | number) {
  return useQuery({
    queryKey: ['license', id],
    queryFn: async () => {
      const { data } = await licensesApi.getLicense(id)
      return data
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!id,
  })
}

export function useLicenseDevices(licenseId: string | number) {
  return useQuery({
    queryKey: ['license-devices', licenseId],
    queryFn: async () => {
      const { data } = await licensesApi.getDevices(licenseId)
      return data
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!licenseId,
  })
}

export function useRemoveLicenseDevice() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ licenseId, deviceId }: { licenseId: string | number; deviceId: string | number }) =>
      licensesApi.removeDevice(licenseId, deviceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['license-devices'] }),
  })
}

// ─── Onboarding ───────────────────────────────────────────────

export function useOnboardingChecklist() {
  return useQuery({
    queryKey: ['onboarding'],
    queryFn: async () => { const { data } = await onboardingApi.getChecklist(); return data },
    staleTime: 30 * 1000,
  })
}
export function useCompleteOnboardingStep() {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (stepId: string) => onboardingApi.completeStep(stepId), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['onboarding'] }) })
}

// ─── Integrations ─────────────────────────────────────────────

export function useIntegrations(category?: string) {
  return useQuery({
    queryKey: ['integrations', category],
    queryFn: async () => { const { data } = await integrationsApi.getIntegrations(category); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}

// ─── Careers ───────────────────────────────────────────────────

export function useJobs() {
  return useQuery({
    queryKey: ['jobs'],
    queryFn: async () => { const { data } = await careersApi.getJobs(); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
export function useJob(id: string) {
  return useQuery({
    queryKey: ['job', id],
    queryFn: async () => { const { data } = await careersApi.getJob(id); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
    enabled: !!id,
  })
}

// ─── Customer Stories ─────────────────────────────────────────

export function useCustomerStories(params?: Record<string, unknown>) {
  return useQuery({
    queryKey: ['customer-stories', params],
    queryFn: async () => { const { data } = await customerStoriesApi.getStories(params as any); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
export function useCustomerStory(slug: string) {
  return useQuery({
    queryKey: ['customer-story', slug],
    queryFn: async () => { const { data } = await customerStoriesApi.getStory(slug); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
    enabled: !!slug,
  })
}

// ─── Press ────────────────────────────────────────────────────

export function usePressReleases() {
  return useQuery({
    queryKey: ['press-releases'],
    queryFn: async () => { const { data } = await pressApi.getReleases(); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}
export function usePressKit() {
  return useQuery({
    queryKey: ['press-kit'],
    queryFn: async () => { const { data } = await pressApi.getKit(); return data },
    staleTime: 30 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  })
}

// ─── Partners ─────────────────────────────────────────────────

export function usePartners(type?: string) {
  return useQuery({
    queryKey: ['partners', type],
    queryFn: async () => { const { data } = await partnersApi.getPartners(type); return data },
    staleTime: 10 * 60 * 1000,
  })
}

// ─── Newsletter ───────────────────────────────────────────────

export function useSubscribeNewsletter() {
  return useMutation({ mutationFn: (data: { email: string; name?: string; preferences?: string[] }) => newsletterApi.subscribe(data) })
}

// ─── Global Search ────────────────────────────────────────────

export function useGlobalSearch(query: string, type?: string) {
  return useQuery({
    queryKey: ['search', query, type],
    queryFn: async () => { const { data } = await searchApi.search(query, type); return data },
    staleTime: 30 * 1000,
    enabled: !!query,
  })
}

// ─── Referrals ────────────────────────────────────────────────

export function useReferrals() {
  return useQuery({
    queryKey: ["referrals"],
    queryFn: async () => {
      const { data } = await referralApi.getMyReferrals()
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

export function useReferralStats() {
  return useQuery({
    queryKey: ["referral-stats"],
    queryFn: async () => {
      const { data } = await referralApi.getReferralStats()
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

export function useCreateReferral() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { referred_email: string }) => referralApi.createReferral(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["referrals"] })
    },
  })
}

// ─── Audit Log ─────────────────────────────────────────────────

export function useWriteAuditLog() {
  return useMutation({
    mutationFn: (data: {
      action: string
      target_type?: string
      target_id?: string
      metadata?: Record<string, string>
    }) =>
      apiClient.post("/api/v1/audit-log", data),
  })
}

// ─── Audit Log ─────────────────────────────────────────────────

export function useAuditLog(params?: { company_id?: string; actor?: string; action?: string; page?: number; per_page?: number }) {
  return useQuery({
    queryKey: ["audit-log", params],
    queryFn: () => auditLogApi.list(params),
    staleTime: 30 * 1000,
  })
}

// ─── Waitlist ─────────────────────────────────────────────────

export function useWaitlistEntries(params?: Record<string, unknown>) {
  return useQuery({
    queryKey: ["waitlist-entries", params],
    queryFn: async () => {
      const { data } = await waitlistApi.listEntries(params as any)
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

/** Public waitlist signup count (backend-cached ~60s) */
export function useWaitlistCount() {
  return useQuery({
    queryKey: ["waitlist-count"],
    queryFn: () => waitlistApi.getCount().then((r) => r.data),
    staleTime: 60 * 1000,
  })
}

// ─── Analytics ──────────────────────────────────────────────────

export function useFinancialAnalytics(dateFrom?: string, dateTo?: string) {
  return useQuery({
    queryKey: ["analytics-financial", dateFrom, dateTo],
    queryFn: () => analyticsApi.getFinancial({ date_from: dateFrom, date_to: dateTo }),
    staleTime: 5 * 60 * 1000,
  })
}

// ─── Helpers ──────────────────────────────────────────────────

const API_TYPE_TO_PORTAL: Record<string, PortalNotification["type"]> = {
  info: "system",
  warning: "security",
  success: "release",
  error: "support",
} as const

function mapAppNotificationToPortal(n: AppNotification): PortalNotification {
  return {
    id: n.id,
    type: API_TYPE_TO_PORTAL[n.type] ?? "system",
    title: n.title,
    message: n.message,
    read: n.is_read,
    link: n.link_url,
    created_at: n.created_at,
  }
}

// ─── Portal Notifications ─────────────────────────────────────

export function usePortalNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: async () => {
      const { data } = await notificationsApi.getNotifications()
      return (data ?? []).map(mapAppNotificationToPortal)
    },
    staleTime: 5 * 60 * 1000,
    refetchInterval: 30_000,
  })
}
export function useMarkNotificationRead() {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (id: string) => notificationsApi.markRead(id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }) })
}
export function useMarkAllRead() {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: () => notificationsApi.markAllRead(), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }) })
}
export function useNotificationPreferences() {
  return useQuery({
    queryKey: ["notification-preferences"],
    queryFn: () => authApi.getNotificationPreferences(),
    staleTime: 5 * 60 * 1000,
  })
}

export function useUpdateNotificationPreferences() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<NotificationPreference>) =>
      authApi.updateNotificationPreferences(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-preferences"] })
    },
  })
}

// ─── Ops Console ─────────────────────────────────────────────

export function useOpsTickets(params?: { risk_tier?: string; status?: string; sort?: string; order?: string }) {
  return useQuery({
    queryKey: ['ops-tickets', params],
    queryFn: async () => {
      const { data } = await opsApi.getTickets(params)
      return data
    },
    staleTime: 30 * 1000,
  })
}

export function useOpsTicket(id: string) {
  return useQuery({
    queryKey: ['ops-ticket', id],
    queryFn: async () => {
      const { data } = await opsApi.getTicket(id)
      return data
    },
    staleTime: 30 * 1000,
    enabled: !!id,
  })
}

export function useOpsApprovals() {
  return useQuery({
    queryKey: ['ops-approvals'],
    queryFn: async () => {
      const { data } = await opsApi.getApprovals()
      return data
    },
    staleTime: 30 * 1000,
  })
}

export function useOpsHandleApproval() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" | "ask_question" }) =>
      opsApi.handleApproval(id, action),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ops-approvals'] }),
  })
}

export function useOpsGuardrails() {
  return useQuery({
    queryKey: ['ops-guardrails'],
    queryFn: async () => {
      const { data } = await opsApi.getGuardrails()
      return data
    },
    staleTime: 30 * 1000,
  })
}

export function useOpsResolveGuardrail() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => opsApi.resolveGuardrail(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ops-guardrails'] }),
  })
}

export function useOpsDashboard() {
  return useQuery({
    queryKey: ['ops-dashboard'],
    queryFn: async () => {
      const { data } = await opsApi.getDashboard()
      return data
    },
    staleTime: 30 * 1000,
  })
}

export function useOpsKnowledgeDrafts() {
  return useQuery({
    queryKey: ['ops-knowledge-drafts'],
    queryFn: async () => {
      const { data } = await opsApi.getKnowledgeDrafts()
      return data
    },
    staleTime: 30 * 1000,
  })
}

export function useOpsApproveKnowledgeDoc() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (docId: string) => opsApi.approveKnowledgeDoc(docId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ops-knowledge-drafts'] }),
  })
}

export function useOpsRejectKnowledgeDoc() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (docId: string) => opsApi.rejectKnowledgeDoc(docId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ops-knowledge-drafts'] }),
  })
}
