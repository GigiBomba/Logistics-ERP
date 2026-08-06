import apiClient from "@/api/client"
import type {
  Announcement,
  AuditLogEntry,
  AuthResponse,
  BillingTerm,
  BlogAuthor,
  BlogCategory,
  BlogPost,
  ChangelogEntry,
  Company,
  CompanyUpdateRequest,
  DesktopRelease,
  DeviceInfo,
  DevResource,
  GuardrailViolation,
  Invoice,
  KnowledgeDraft,
  LoginRequest,
  NotificationPreference,
  OnboardingChecklist,
  OnboardingStep,
  OpsApproval,
  OpsSummary,
  OpsTicket,
  OpsTicketDetail,
  PaginatedResponse,
  SubscriptionPlan,
  RegisterRequest,
  RoadmapItem,
  SecurityReport,
  ServiceStatusGroup,
  Subscription,
  SupportTicket,
  Tutorial,
  User,
} from "@/types"

export const authApi = {
  login: (data: LoginRequest) => {
    const params = new URLSearchParams({
      username: data.username,
      password: data.password,
      grant_type: "password",
    })
    if (data.turnstile_token) {
      params.append("turnstile_token", data.turnstile_token)
    }
    return apiClient.post<AuthResponse>(
      "/api/v1/auth/token",
      params,
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
    )
  },

  register: (data: RegisterRequest) =>
    apiClient.post<AuthResponse>("/api/v1/registration/register", {
      email: data.email,
      password: data.password,
      display_name: data.name,
      company_name: data.company_name || "My Company",
      referral_code: data.referral_code || undefined,
      turnstile_token: data.turnstile_token || undefined,
    }),

  logout: () => apiClient.post("/api/v1/auth/logout"),

  /** @deprecated Cookie-based refresh — kept for desktop ERP transitional compatibility */
  refreshToken: (refreshToken: string) =>
    apiClient.post<AuthResponse>("/api/v1/auth/refresh", { refresh_token: refreshToken }),

  forgotPassword: (email: string) =>
    apiClient.post("/api/v1/auth/forgot-password", { email }),

  resetPassword: (token: string, newPassword: string) =>
    apiClient.post("/api/v1/auth/reset-password", { token, new_password: newPassword }),

  verifyEmail: (token: string) =>
    apiClient.post<{ status: string }>("/api/v1/auth/verify-email", { token }),

  getMe: () => apiClient.get<{ user: User }>("/api/v1/auth/me"),

  updateProfile: (data: { name?: string; email?: string }) =>
    apiClient.patch<{ user: User }>("/api/v1/auth/me", data),

  changePassword: (data: { current_password: string; new_password: string }) =>
    apiClient.post<{ status: string }>("/api/v1/auth/change-password", data),

  verifyMfa: (mfaSessionToken: string, code: string) =>
    apiClient.post<AuthResponse>("/api/v1/auth/mfa/verify", { mfa_session_token: mfaSessionToken, code }).then((r) => r.data),

  getNotificationPreferences: () =>
    apiClient.get<NotificationPreference>("/api/v1/auth/me/notification-preferences"),
  updateNotificationPreferences: (data: Partial<NotificationPreference>) =>
    apiClient.patch<NotificationPreference>("/api/v1/auth/me/notification-preferences", data),
}

// ─── MFA (Two-Factor Authentication) ────────────────────────────
export interface MfaEnrollResponse {
  secret: string
  otpauth_uri: string
  qr_payload: string
}

export interface MfaConfirmResponse {
  mfa_enabled: boolean
  backup_codes: string[]
}

export interface MfaStatusResponse {
  mfa_enabled: boolean
}

export const mfaApi = {
  /** Begin MFA enrollment — returns the TOTP secret + otpauth URI + QR payload */
  enroll: () =>
    apiClient.post<MfaEnrollResponse>("/api/v1/auth/mfa/enroll", {}),

  /** Confirm enrollment with a 6-digit code — returns 10 single-use backup codes */
  confirm: (code: string) =>
    apiClient.post<MfaConfirmResponse>("/api/v1/auth/mfa/confirm", { code }),

  /** Disable MFA — requires the account password */
  disable: (password: string) =>
    apiClient.post<MfaStatusResponse>("/api/v1/auth/mfa/disable", { password }),

  /** Sign in with a backup code after being prompted for MFA */
  backupCode: (mfaSessionToken: string, backupCode: string) =>
    apiClient.post<AuthResponse>("/api/v1/auth/mfa/backup-code", {
      mfa_session_token: mfaSessionToken,
      backup_code: backupCode,
    }),

  /** Current MFA status for the signed-in user */
  status: () =>
    apiClient.get<MfaStatusResponse>("/api/v1/auth/me/mfa-status"),
}

// ─── Avatar (multipart upload) ─────────────────────────────────
export interface AvatarUploadResponse {
  avatar_url: string
}

export const avatarApi = {
  /** Upload a profile picture (multipart/form-data). PNG/JPEG/WebP ≤ 5MB. */
  upload: (file: File) => {
    const formData = new FormData()
    formData.append("file", file)
    return apiClient.post<AvatarUploadResponse>("/api/v1/auth/me/avatar", formData, {
      // Override the instance-level `application/json` default so axios passes
      // the FormData through and lets the browser set the multipart boundary.
      headers: { "Content-Type": undefined },
    })
  },
}

export const subscriptionApi = {
  getCurrent: () => apiClient.get<Subscription>("/api/v1/subscriptions/current"),
  getPlans: () => apiClient.get<SubscriptionPlan[]>("/api/v1/subscriptions/plans"),
  createCheckoutSession: (options?: { price_id?: string; trial_period_days?: number }) =>
    apiClient.post<{ url: string; session_id: string }>("/api/v1/subscriptions/checkout", options || {}),
  createPortalSession: () =>
    apiClient.post<{ url: string }>("/api/v1/subscriptions/portal"),
  toggleAddon: (data: { addon: "ai_copilot" | "priority_support" | "api_access"; enabled: boolean }) =>
    apiClient.post<Subscription>("/api/v1/subscriptions/toggle-addon", data),

  // ─── Billing / plan lifecycle (backend live) ──────────────────
  /** Switch the billing term between monthly and annual */
  billingTerm: (term: BillingTerm) =>
    apiClient.post<Subscription>("/api/v1/subscriptions/billing-term", { term }),

  /** Cancel the subscription — keeps access until `usable_until` */
  cancel: () =>
    apiClient.post<{ usable_until: string }>("/api/v1/subscriptions/cancel", {}),

  /** Reactivate a canceled subscription */
  reactivate: () =>
    apiClient.post<Subscription>("/api/v1/subscriptions/reactivate", {}),

  /** Register a licensed truck (also used by the desktop ERP) */
  addTruck: (truckId: string, source?: string) =>
    apiClient.post<Subscription>("/api/v1/subscriptions/trucks/add", {
      truck_id: truckId,
      source,
    }),

  /** Remove a licensed truck (also used by the desktop ERP) */
  removeTruck: (truckId: string, source?: string) =>
    apiClient.post<Subscription>("/api/v1/subscriptions/trucks/remove", {
      truck_id: truckId,
      source,
    }),
}

export const companyApi = {
  get: () => apiClient.get<Company>("/api/v1/company"),
  update: (data: CompanyUpdateRequest) => apiClient.patch<Company>("/api/v1/company", data),
}

export interface CreateTicketRequest {
  subject: string
  description: string
  priority?: "low" | "medium" | "high" | "urgent"
}

export const supportApi = {
  createTicket: (data: CreateTicketRequest) =>
    apiClient.post<SupportTicket>("/api/v1/support/tickets", data),
  getTickets: () => apiClient.get<SupportTicket[]>("/api/v1/support/tickets"),
  getTicket: (id: number | string) =>
    apiClient.get<SupportTicket>(`/api/v1/support/tickets/${id}`),
  /** Send a support message and get ARGO's reply (live conversational loop) */
  sendMessage: (data: SupportMessageRequest) =>
    apiClient.post<SupportMessageResponse>("/api/v1/support/messages", data),
}

export const downloadApi = {
  getLatest: () => apiClient.get<DesktopRelease>("/api/v1/downloads/latest"),
  getVersions: () => apiClient.get<DesktopRelease[]>("/api/v1/downloads/versions"),
}

// ─── Blog ───────────────────────────────────────────────────
export const blogApi = {
  getPosts: (params?: { page?: number; category?: string; tag?: string; search?: string }) =>
    apiClient.get<PaginatedResponse<BlogPost>>("/api/v1/blog/posts", { params }),

  getPost: (slug: string) =>
    apiClient.get<BlogPost>(`/api/v1/blog/posts/${slug}`),

  getCategories: () =>
    apiClient.get<BlogCategory[]>("/api/v1/blog/categories"),

  getAuthor: (id: number | string) =>
    apiClient.get<BlogAuthor>(`/api/v1/blog/authors/${id}`),
}

// ─── Admin Blog ─────────────────────────────────────────────
export interface CreateBlogPostRequest {
  title: string
  slug?: string
  excerpt: string
  content: string
  category_id: string
  tags?: string[]
  featured_image?: string
  seo_title?: string
  seo_description?: string
  published?: boolean
}

export interface UpdateBlogPostRequest {
  title?: string
  slug?: string
  excerpt?: string
  content?: string
  category_id?: string
  tags?: string[]
  featured_image?: string
  seo_title?: string
  seo_description?: string
  published?: boolean
}

export const adminBlogApi = {
  createPost: (data: CreateBlogPostRequest) =>
    apiClient.post<BlogPost>("/api/v1/blog/admin/posts", data),

  updatePost: (slug: string, data: UpdateBlogPostRequest) =>
    apiClient.patch<BlogPost>(`/api/v1/blog/admin/posts/${slug}`, data),

  deletePost: (slug: string) =>
    apiClient.delete(`/api/v1/blog/admin/posts/${slug}`),
}

// ─── Changelog ──────────────────────────────────────────────
export const changelogApi = {
  getEntries: () =>
    apiClient.get<ChangelogEntry[]>("/api/v1/changelog"),
}

// ─── Roadmap ────────────────────────────────────────────────
export const roadmapApi = {
  getItems: (status?: string) =>
    apiClient.get<RoadmapItem[]>("/api/v1/roadmap", { params: { status } }),
}

// ─── Service Status ─────────────────────────────────────────
export const statusApi = {
  getStatus: () =>
    apiClient.get<ServiceStatusGroup[]>("/api/v1/status"),
}

// ─── Tutorials ──────────────────────────────────────────────
export const tutorialsApi = {
  getTutorials: (params?: { category?: string; search?: string }) =>
    apiClient.get<Tutorial[]>("/api/v1/tutorials", { params }),

  getTutorial: (slug: string) =>
    apiClient.get<Tutorial>(`/api/v1/tutorials/${slug}`),
}

// ─── Developer Resources ────────────────────────────────────
export const developersApi = {
  getResources: () =>
    apiClient.get<DevResource[]>("/api/v1/developers/resources"),

  getToolkitVersions: () =>
    apiClient.get<DesktopRelease[]>("/api/v1/developers/toolkit/versions"),
}

// ─── Security Reports ───────────────────────────────────────
export const securityApi = {
  getReports: () =>
    apiClient.get<SecurityReport[]>("/api/v1/security/reports"),

  submitReport: (data: { title: string; description: string; severity: string }) =>
    apiClient.post<SecurityReport>("/api/v1/security/reports", data),
}

// ─── Announcements ──────────────────────────────────────────
export const announcementsApi = {
  getAnnouncements: () =>
    apiClient.get<Announcement[]>("/api/v1/announcements"),
}

// ─── Invoices (Subscription domain) ─────────────────────────
export const invoicesApi = {
  getInvoices: () =>
    apiClient.get<Invoice[]>("/api/v1/subscriptions/invoices"),
}

// ─────────────────── V3 API Endpoint Groups ───────────────────

// ─── Organizations ──────────────────────────────────────────
export interface Organization {
  id: string | number
  name: string
  slug: string
  logo_url?: string
  website?: string
  industry?: string
  size?: string
  address?: string
  city?: string
  country?: string
  postal_code?: string
  phone?: string
  vat_number?: string
  subscription_tier?: string
  is_active?: boolean
  created_at?: string
  updated_at?: string
  member_count?: number
  user_role?: "owner" | "admin" | "member"
}

export interface OrganizationMember {
  id: string | number
  org_id: string | number
  user_id: string | number
  role: "owner" | "admin" | "member"
  status: "active" | "pending" | "suspended"
  name?: string
  email?: string
  joined_at?: string
  invited_at?: string
}

export interface OrganizationInvitation {
  id: string | number
  org_id: string | number
  email: string
  role: string
  token: string
  invited_by?: string | number
  invited_by_name?: string
  status: "pending" | "accepted" | "expired"
  created_at?: string
  expires_at?: string
}

export interface CreateOrganizationRequest {
  name: string
  slug?: string
  logo_url?: string
  website?: string
}

export interface UpdateOrganizationRequest {
  name?: string
  slug?: string
  logo_url?: string
  website?: string
}

export interface InviteMemberRequest {
  email: string
  role: "admin" | "member"
}

export const organizationsApi = {
  getAll: () =>
    apiClient.get<Organization[]>("/api/v1/organizations"),

  get: (slug: string) =>
    apiClient.get<Organization>(`/api/v1/organizations/${slug}`),

  create: (data: CreateOrganizationRequest) =>
    apiClient.post<Organization>("/api/v1/organizations", data),

  update: (slug: string, data: UpdateOrganizationRequest) =>
    apiClient.patch<Organization>(`/api/v1/organizations/${slug}`, data),

  getMembers: (slug: string) =>
    apiClient.get<OrganizationMember[]>(`/api/v1/organizations/${slug}/members`),

  inviteMember: (slug: string, data: InviteMemberRequest) =>
    apiClient.post<OrganizationInvitation>(`/api/v1/organizations/${slug}/invitations`, data),

  removeMember: (slug: string, memberId: string) =>
    apiClient.delete(`/api/v1/organizations/${slug}/members/${memberId}`),

  getInvitations: (slug: string) =>
    apiClient.get<OrganizationInvitation[]>(`/api/v1/organizations/${slug}/invitations`),

  acceptInvitation: (token: string) =>
    apiClient.post<OrganizationMember>(`/api/v1/organizations/invitations/${token}/accept`),
}

// ─── Licenses ────────────────────────────────────────────────
export interface License {
  id: string
  license_key: string
  plan_tier: string
  status: "active" | "suspended" | "expired" | "revoked"
  seats: number
  seats_used: number
  issued_at: string
  expires_at?: string
}

export interface LicenseDevice {
  id: string
  name: string
  os: string
  ip?: string
  last_seen: string
  activated_at: string
}

export const licensesApi = {
  getLicenses: () =>
    apiClient.get<License[]>("/api/v1/licenses"),

  getLicense: (id: string | number) =>
    apiClient.get<License>(`/api/v1/licenses/${id}`),

  getDevices: (licenseId: string | number) =>
    apiClient.get<LicenseDevice[]>(`/api/v1/licenses/${licenseId}/devices`),

  removeDevice: (licenseId: string | number, deviceId: string | number) =>
    apiClient.delete(`/api/v1/licenses/${licenseId}/devices/${deviceId}`),
}

export const devicesApi = {
  getDevices: () => apiClient.get<DeviceInfo[]>("/api/v1/mobile/devices"),
  deactivateDevice: (deviceId: string) => apiClient.delete(`/api/v1/mobile/devices/${deviceId}`),
}

// ─── Auth Sessions (desktop app login tracking) ─────────────
export interface SessionInfo {
  id: number
  user_email: string
  device_name: string
  device_platform: string
  ip_address: string
  created_at: string
  expires_at: string
  last_active_at: string
}

export const sessionsApi = {
  getSessions: () => apiClient.get<{ sessions: SessionInfo[] }>("/api/v1/auth/sessions"),
  revokeSession: (sessionId: number) => apiClient.delete(`/api/v1/auth/sessions/${sessionId}`),
}

// ─── Onboarding ──────────────────────────────────────────────
export const onboardingApi = {
  getChecklist: () =>
    apiClient.get<OnboardingChecklist>("/api/v1/onboarding/checklist"),

  completeStep: (stepId: string) =>
    apiClient.post<OnboardingStep>(`/api/v1/onboarding/steps/${stepId}/complete`),
}

// ─── Integrations ────────────────────────────────────────────
export interface Integration {
  id: string
  name: string
  description: string
  icon: string
  category: string
  is_connected: boolean
  docs_url?: string
}

export const integrationsApi = {
  getIntegrations: (category?: string) =>
    apiClient.get<Integration[]>("/api/v1/integrations", { params: { category } }),

  getIntegration: (id: string) =>
    apiClient.get<Integration>(`/api/v1/integrations/${id}`),
}

// ─── Customer Stories ────────────────────────────────────────
export interface CustomerStory {
  id: string
  title: string
  slug: string
  excerpt: string
  content: string
  company_name: string
  company_logo?: string
  industry: string
  featured_image?: string
  published_at: string
}

export const customerStoriesApi = {
  getStories: (params?: { page?: number; industry?: string; search?: string }) =>
    apiClient.get<PaginatedResponse<CustomerStory>>("/api/v1/customer-stories", { params }),

  getStory: (slug: string) =>
    apiClient.get<CustomerStory>(`/api/v1/customer-stories/${slug}`),
}

// ─── Careers ─────────────────────────────────────────────────
export interface Job {
  id: string
  title: string
  department: string
  location: string
  type: "full-time" | "part-time" | "contract" | "internship"
  description: string
  requirements: string[]
  published_at: string
  closing_at?: string
  is_remote: boolean
}

export const careersApi = {
  getJobs: () =>
    apiClient.get<Job[]>("/api/v1/careers/jobs"),

  getJob: (id: string) =>
    apiClient.get<Job>(`/api/v1/careers/jobs/${id}`),
}

// ─── Press ───────────────────────────────────────────────────
export interface PressRelease {
  id: string
  title: string
  slug: string
  excerpt: string
  content: string
  published_at: string
  author: string
  tags: string[]
}

export interface PressKit {
  brand_name: string
  description: string
  logo_urls: { label: string; url: string }[]
  screenshots: { title: string; url: string }[]
  fact_sheet: Record<string, string>
  contact_email: string
}

export const pressApi = {
  getReleases: () =>
    apiClient.get<PressRelease[]>("/api/v1/press/releases"),

  getRelease: (slug: string) =>
    apiClient.get<PressRelease>(`/api/v1/press/releases/${slug}`),

  getKit: () =>
    apiClient.get<PressKit>("/api/v1/press/kit"),
}

// ─── Partners ────────────────────────────────────────────────
export interface Partner {
  id: string
  name: string
  slug: string
  description: string
  logo_url: string
  website: string
  tier: "gold" | "silver" | "technology"
  categories: string[]
}

export const partnersApi = {
  getPartners: (type?: string) =>
    apiClient.get<Partner[]>("/api/v1/partners", { params: { type } }),

  getPartner: (id: string) =>
    apiClient.get<Partner>(`/api/v1/partners/${id}`),
}

// ─── Newsletter ──────────────────────────────────────────────
export interface NewsletterSubscribeRequest {
  email: string
  name?: string
  preferences?: string[]
  turnstile_token?: string
}

export const newsletterApi = {
  subscribe: (data: NewsletterSubscribeRequest) =>
    apiClient.post<{ status: string; message: string }>("/api/v1/newsletter/subscribe", data),

  unsubscribe: (email: string) =>
    apiClient.post<{ status: string; message: string }>("/api/v1/newsletter/unsubscribe", { email }),
}

// ─── Global Search ───────────────────────────────────────────
export interface SearchResult {
  id: string
  type: string
  title: string
  description: string
  url: string
  score: number
}

export interface SearchResponse {
  results: SearchResult[]
  total: number
  query: string
  type?: string
}

export const searchApi = {
  search: (query: string, type?: string) =>
    apiClient.get<SearchResponse>("/api/v1/search", { params: { q: query, type } }),
}

// ─── Notifications (Portal) ──────────────────────────────────
export interface AppNotification {
  id: string
  title: string
  message: string
  type: "info" | "warning" | "success" | "error"
  is_read: boolean
  created_at: string
  link_url?: string
}

export const notificationsApi = {
  getNotifications: () =>
    apiClient.get<AppNotification[]>("/api/v1/notifications"),

  markRead: (id: string) =>
    apiClient.post<AppNotification>(`/api/v1/notifications/${id}/read`),

  markAllRead: () =>
    apiClient.post<{ status: string }>("/api/v1/notifications/read-all"),

  getPreferences: () =>
    apiClient.get<NotificationPreference>("/api/v1/notifications/preferences"),

  updatePreferences: (data: Partial<NotificationPreference>) =>
    apiClient.patch<NotificationPreference>("/api/v1/notifications/preferences", data),
}

// ─── Audit Log ────────────────────────────────────────────
export const auditLogApi = {
  list: (params?: { company_id?: string; actor?: string; action?: string; page?: number; per_page?: number }) =>
    apiClient.get<{ entries: AuditLogEntry[]; total: number; page: number; per_page: number }>("/api/v1/audit-log", { params }).then((r) => r.data),
}

// ── Waitlist ──────────────────────────────────────────────────────

export interface WaitlistJoinRequest {
  company_name: string
  email: string
  contact_name?: string
  company_size?: string
  country?: string
  fleet_size?: string
  source?: string
  turnstile_token?: string
}

export interface WaitlistJoinResponse {
  status: string
  referral_code: string
}

export interface WaitlistEntry {
  id: number
  company_name: string
  contact_name: string | null
  email: string
  fleet_size: string | null
  company_size: string | null
  country: string | null
  source: string
  referral_code: string
  referred_by: string | null
  status: string
  joined_at: string
  invited_at: string | null
  activated_at: string | null
  converted_at: string | null
  notes: string | null
  user_agent: string | null
  unsubscribed_at: string | null
}

export interface WaitlistEntryUpdate {
  status?: string
  notes?: string
  admin_override?: boolean
}

export interface WaitlistPageResponse {
  entries: WaitlistEntry[]
  total: number
  page: number
  page_size: number
  by_status: Record<string, number>
}

export interface WaitlistStatsResponse {
  total: number
  by_status: Record<string, number>
  by_country: Record<string, number>
  by_company_size: Record<string, number>
  by_fleet_size: Record<string, number>
  by_source: Record<string, number>
  growth_daily: Array<{ date: string; count: number }>
  conversion_rate: number
}

export interface WaitlistEntriesParams {
  search?: string
  status?: string
  country?: string
  company_size?: string
  fleet_size?: string
  source?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export interface WaitlistCountResponse {
  count: number
  cached_at: string
}

export const waitlistApi = {
  /** Public: join the waitlist */
  join: (data: WaitlistJoinRequest) =>
    apiClient.post<WaitlistJoinResponse>("/api/v1/waitlist/join", data),

  /** Public: current waitlist signup count (backend-cached ~60s) */
  getCount: () =>
    apiClient.get<WaitlistCountResponse>("/api/v1/waitlist/count"),

  /** Admin: list entries with filters & pagination */
  listEntries: (params?: WaitlistEntriesParams) =>
    apiClient.get<WaitlistPageResponse>("/api/v1/waitlist/admin/entries", { params }),

  /** Admin: update entry status/notes */
  updateEntry: (id: number, data: WaitlistEntryUpdate) =>
    apiClient.patch<WaitlistEntry>(`/api/v1/waitlist/admin/entries/${id}`, data),

  /** Admin: delete entry */
  deleteEntry: (id: number) =>
    apiClient.delete(`/api/v1/waitlist/admin/entries/${id}`),

  /** Admin: export CSV */
  exportCsv: (params?: WaitlistEntriesParams) =>
    apiClient.get("/api/v1/waitlist/admin/export.csv", {
      params,
      responseType: "blob",
    }),

  /** Admin: get stats */
  getStats: () =>
    apiClient.get<WaitlistStatsResponse>("/api/v1/waitlist/admin/stats"),

  /** Admin: send email campaign */
  sendCampaign: (data: { subject: string; body: string; segment?: string }) =>
    apiClient.post<{ status: string; count: number; total_recipients: number; errors: number }>(
      "/api/v1/waitlist/admin/campaign",
      data
    ),

  /** Public: unsubscribe */
  unsubscribe: (token: string) =>
    apiClient.get(`/api/v1/waitlist/unsubscribe/${token}`),
}

// ─── Contact ────────────────────────────────────────────────────────
export interface ContactRequest {
  name: string
  email: string
  subject: string
  message: string
  hp_field?: string
  turnstile_token?: string
}

export interface ContactResponse {
  status: string
}

export const contactApi = {
  /** Public: send a contact message */
  send: (data: ContactRequest) =>
    apiClient.post<ContactResponse>("/api/v1/contact", data),
}

// ─── Referral API ────────────────────────────────────────────────

export interface Referral {
  id: string
  referrer_email: string
  referred_email: string
  referral_code: string
  status: "pending" | "completed" | "expired"
  created_at: string
  completed_at: string | null
  reward_applied: boolean
}

export interface ReferralStatsResponse {
  total_referrals: number
  completed_referrals: number
  pending_referrals: number
  rewards_earned: number
  referrals: Referral[]
}

export interface ReferralRegisterRequest {
  referral_code?: string
}

// ─── Support / Live Chat ──────────────────────────────────

export interface SupportMessageRequest {
  conversation_id: string | null
  message: string
  channel: "chat" | "in_app"
}

export interface SupportMessageResponse {
  conversation_id: string
  reply: string
  requires_action: boolean
  escalated: boolean
}

// ─── Analytics ──────────────────────────────────────────────────
export const analyticsApi = {
  getFinancial: (params?: { date_from?: string; date_to?: string }) =>
    apiClient.get("/api/v1/analytics/financial", { params }).then((r) => r.data),
}

// ─── Ops Console ───────────────────────────────────────────────────
export const opsApi = {
  getTickets: (params?: { risk_tier?: string; status?: string; sort?: string; order?: string }) =>
    apiClient.get<OpsTicket[]>("/api/v1/ops/tickets", { params }),
  getTicket: (id: string) =>
    apiClient.get<OpsTicketDetail>(`/api/v1/ops/tickets/${id}`),
  getApprovals: () =>
    apiClient.get<OpsApproval[]>("/api/v1/ops/approvals"),
  handleApproval: (id: string, action: "approve" | "reject" | "ask_question") =>
    apiClient.post<{ status: string; new_status: string }>(`/api/v1/ops/approvals/${id}/${action}`),
  getGuardrails: () =>
    apiClient.get<GuardrailViolation[]>("/api/v1/ops/guardrails"),
  resolveGuardrail: (id: number) =>
    apiClient.post<{ status: string }>(`/api/v1/ops/guardrails/${id}/resolve`),
  getDashboard: () =>
    apiClient.get<OpsSummary>("/api/v1/ops/dashboard"),
  getKnowledgeDrafts: () =>
    apiClient.get<KnowledgeDraft[]>("/api/v1/ops/knowledge/drafts"),
  approveKnowledgeDoc: (docId: string) =>
    apiClient.post<{ status: string }>(`/api/v1/ops/knowledge/${docId}/approve`),
  rejectKnowledgeDoc: (docId: string) =>
    apiClient.post<{ status: string }>(`/api/v1/ops/knowledge/${docId}/reject`),
}

// ─── Admin Diagnostics ─────────────────────────────────────────
export const adminApi = {
  getCompanyRowCounts: () => apiClient.get("/api/v1/admin/db/company-row-counts").then((r) => r.data),
  getSystemInfo: () => apiClient.get("/api/v1/admin/system/info").then((r) => r.data),
  getDiagnostics: () => apiClient.get("/api/v1/admin/diagnostics").then((r) => r.data),
}

export const referralApi = {
  /** Get the current user's referral stats and list */
  getMyReferrals: () =>
    apiClient.get<ReferralStatsResponse>("/api/v1/referrals/my"),

  /** Create a referral by sending an invitation to an email address */
  createReferral: (data: { referred_email: string }) =>
    apiClient.post<{ status: string; referral: Referral }>("/api/v1/referrals/create", data),

  /** Track a referral code being used during registration (called from frontend on register) */
  trackReferral: (data: { referral_code: string }) =>
    apiClient.post<{ status: string }>("/api/v1/referrals/track", data),

  /** Admin: get all referrals */
  listReferrals: (params?: { page?: number; page_size?: number; status?: string }) =>
    apiClient.get<{ referrals: Referral[]; total: number; page: number; page_size: number }>(
      "/api/v1/referrals/admin/list",
      { params }
    ),

  /** Admin: get referral stats */
  getReferralStats: () =>
    apiClient.get<{
      total_referrals: number
      completed_referrals: number
      pending_referrals: number
      rewards_earned: number
    }>("/api/v1/referrals/admin/stats"),
}
