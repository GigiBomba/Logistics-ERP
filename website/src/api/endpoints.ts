import apiClient from "@/api/client"
import type {
  AuthResponse,
  LoginRequest,
  RegisterRequest,
} from "@/types"

export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<AuthResponse>(
      "/api/v1/auth/token",
      new URLSearchParams({
        username: data.username,
        password: data.password,
        grant_type: "password",
      }),
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
    ),

  register: (data: RegisterRequest) =>
    apiClient.post<AuthResponse>("/api/v1/registration/register", {
      email: data.email,
      password: data.password,
      display_name: data.name,
      company_name: data.company_name || "My Company",
    }),

  logout: () => apiClient.post("/api/v1/auth/logout"),

  refreshToken: (refreshToken: string) =>
    apiClient.post<AuthResponse>("/api/v1/auth/refresh", { refresh_token: refreshToken }),

  forgotPassword: (email: string) =>
    apiClient.post("/api/v1/auth/forgot-password", { email }),

  resetPassword: (token: string, newPassword: string) =>
    apiClient.post("/api/v1/auth/reset-password", { token, new_password: newPassword }),

  // TODO: Implement backend endpoint
  // verifyEmail: (token: string) =>
  //   apiClient.post("/api/v1/auth/verify-email", { token }),

  // TODO: Implement backend endpoint
  // getMe: () => apiClient.get<User>("/api/v1/auth/me"),

  // TODO: Implement backend endpoint
  // updateProfile: (data: { name?: string; email?: string }) =>
  //   apiClient.patch<User>("/api/v1/auth/me", data),

  // TODO: Implement backend endpoint
  // changePassword: (data: { current_password: string; new_password: string }) =>
  //   apiClient.post("/api/v1/auth/change-password", data),
}

// TODO: Implement backend endpoint
// export const subscriptionApi = {
//   getCurrent: () => apiClient.get<Subscription>("/api/v1/subscriptions/current"),
//   getPlans: () => apiClient.get<Plan[]>("/api/v1/subscriptions/plans"),
// }

// TODO: Implement backend endpoint
// export const companyApi = {
//   get: () => apiClient.get<Company>("/api/v1/company"),
//   update: (data: CompanyUpdateRequest) => apiClient.patch<Company>("/api/v1/company", data),
// }

export interface CreateTicketRequest {
  subject: string
  description: string
  priority?: "low" | "medium" | "high" | "urgent"
}

// TODO: Implement backend endpoint
// export const supportApi = {
//   createTicket: (data: CreateTicketRequest) =>
//     apiClient.post<SupportTicket>("/api/v1/support/tickets", data),
//   getTickets: () => apiClient.get<SupportTicket[]>("/api/v1/support/tickets"),
//   getTicket: (id: string) => apiClient.get<SupportTicket>(`/api/v1/support/tickets/${id}`),
// }

// TODO: Implement backend endpoint
// export const downloadApi = {
//   getLatest: () => apiClient.get("/api/v1/downloads/latest"),
//   getVersions: () => apiClient.get("/api/v1/downloads/versions"),
// }

// ─── Blog ───────────────────────────────────────────────────
// TODO: Implement backend endpoint
// export const blogApi = {
//   getPosts: (params?: { page?: number; category?: string; tag?: string; search?: string }) =>
//     apiClient.get<PaginatedResponse<BlogPost>>("/api/blog/posts", { params }),
// 
//   getPost: (slug: string) =>
//     apiClient.get<BlogPost>(`/api/blog/posts/${slug}`),
// 
//   getCategories: () =>
//     apiClient.get<BlogCategory[]>("/api/blog/categories"),
// 
//   getAuthor: (id: string) =>
//     apiClient.get<BlogAuthor>(`/api/blog/authors/${id}`),
// }

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

// TODO: Implement backend endpoint
// export const adminBlogApi = {
//   createPost: (data: CreateBlogPostRequest) =>
//     apiClient.post<BlogPost>("/api/admin/blog/posts", data),
// 
//   updatePost: (slug: string, data: UpdateBlogPostRequest) =>
//     apiClient.patch<BlogPost>(`/api/admin/blog/posts/${slug}`, data),
// 
//   deletePost: (slug: string) =>
//     apiClient.delete(`/api/admin/blog/posts/${slug}`),
// }

// ─── Changelog ──────────────────────────────────────────────
// TODO: Implement backend endpoint
// export const changelogApi = {
//   getEntries: () =>
//     apiClient.get<ChangelogEntry[]>("/api/v1/changelog"),
// }

// ─── Roadmap ────────────────────────────────────────────────
// TODO: Implement backend endpoint
// export const roadmapApi = {
//   getItems: (status?: string) =>
//     apiClient.get<RoadmapItem[]>("/api/v1/roadmap", { params: { status } }),
// }

// ─── Service Status ─────────────────────────────────────────
// TODO: Implement backend endpoint
// export const statusApi = {
//   getStatus: () =>
//     apiClient.get<ServiceStatusGroup[]>("/api/v1/status"),
// }

// ─── Tutorials ──────────────────────────────────────────────
// TODO: Implement backend endpoint
// export const tutorialsApi = {
//   getTutorials: (params?: { category?: string; search?: string }) =>
//     apiClient.get<Tutorial[]>("/api/v1/tutorials", { params }),
// 
//   getTutorial: (slug: string) =>
//     apiClient.get<Tutorial>(`/api/v1/tutorials/${slug}`),
// }

// ─── Developer Resources ────────────────────────────────────
// TODO: Implement backend endpoint
// export const developersApi = {
//   getResources: () =>
//     apiClient.get<DevResource[]>("/api/v1/developers/resources"),
// 
//   getToolkitVersions: () =>
//     apiClient.get<DesktopRelease[]>("/api/v1/developers/toolkit/versions"),
// }

// ─── Security Reports ───────────────────────────────────────
// TODO: Implement backend endpoint
// export const securityApi = {
//   getReports: () =>
//     apiClient.get<SecurityReport[]>("/api/v1/security/reports"),
// 
//   submitReport: (data: { title: string; description: string; severity: string }) =>
//     apiClient.post<SecurityReport>("/api/v1/security/reports", data),
// }

// ─── Announcements ──────────────────────────────────────────
// TODO: Implement backend endpoint
// export const announcementsApi = {
//   getAnnouncements: () =>
//     apiClient.get<Announcement[]>("/api/v1/announcements"),
// }

// ─── Invoices (Subscription domain) ─────────────────────────
// TODO: Implement backend endpoint
// export const invoicesApi = {
//   getInvoices: () =>
//     apiClient.get<Invoice[]>("/api/v1/subscriptions/invoices"),
// }

// ─────────────────── V3 API Endpoint Groups ───────────────────

// ─── Organizations ──────────────────────────────────────────
export interface Organization {
  id: string
  name: string
  slug: string
  logo_url?: string
  website?: string
  created_at: string
  updated_at: string
}

export interface OrganizationMember {
  id: string
  user_id: string
  name: string
  email: string
  role: "owner" | "admin" | "member"
  joined_at: string
}

export interface OrganizationInvitation {
  id: string
  email: string
  role: string
  token: string
  status: "pending" | "accepted" | "expired"
  created_at: string
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

// TODO: Implement backend endpoint
// export const organizationsApi = {
//   getAll: () =>
//     apiClient.get<Organization[]>("/api/v1/organizations"),
// 
//   get: (slug: string) =>
//     apiClient.get<Organization>(`/api/v1/organizations/${slug}`),
// 
//   create: (data: CreateOrganizationRequest) =>
//     apiClient.post<Organization>("/api/v1/organizations", data),
// 
//   update: (slug: string, data: UpdateOrganizationRequest) =>
//     apiClient.patch<Organization>(`/api/v1/organizations/${slug}`, data),
// 
//   getMembers: (slug: string) =>
//     apiClient.get<OrganizationMember[]>(`/api/v1/organizations/${slug}/members`),
// 
//   inviteMember: (slug: string, data: InviteMemberRequest) =>
//     apiClient.post<OrganizationInvitation>(`/api/v1/organizations/${slug}/invitations`, data),
// 
//   removeMember: (slug: string, memberId: string) =>
//     apiClient.delete(`/api/v1/organizations/${slug}/members/${memberId}`),
// 
//   getInvitations: (slug: string) =>
//     apiClient.get<OrganizationInvitation[]>(`/api/v1/organizations/${slug}/invitations`),
// 
//   acceptInvitation: (token: string) =>
//     apiClient.post<OrganizationMember>(`/api/v1/organizations/invitations/${token}/accept`),
// }

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

// TODO: Implement backend endpoint
// export const licensesApi = {
//   getLicenses: () =>
//     apiClient.get<License[]>("/api/v1/licenses"),
// 
//   getLicense: (id: string) =>
//     apiClient.get<License>(`/api/v1/licenses/${id}`),
// 
//   getDevices: (licenseId: string) =>
//     apiClient.get<LicenseDevice[]>(`/api/v1/licenses/${licenseId}/devices`),
// 
//   removeDevice: (licenseId: string, deviceId: string) =>
//     apiClient.delete(`/api/v1/licenses/${licenseId}/devices/${deviceId}`),
// }

// ─── Onboarding ──────────────────────────────────────────────
export interface OnboardingChecklist {
  id: string
  title: string
  steps: OnboardingStep[]
  progress: number
}

export interface OnboardingStep {
  id: string
  title: string
  description: string
  completed: boolean
  order: number
}

// TODO: Implement backend endpoint
// export const onboardingApi = {
//   getChecklist: () =>
//     apiClient.get<OnboardingChecklist>("/api/v1/onboarding/checklist"),
// 
//   completeStep: (stepId: string) =>
//     apiClient.post<OnboardingStep>(`/api/v1/onboarding/steps/${stepId}/complete`),
// }

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

// TODO: Implement backend endpoint
// export const integrationsApi = {
//   getIntegrations: (category?: string) =>
//     apiClient.get<Integration[]>("/api/v1/integrations", { params: { category } }),
// 
//   getIntegration: (id: string) =>
//     apiClient.get<Integration>(`/api/v1/integrations/${id}`),
// }

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

// TODO: Implement backend endpoint
// export const customerStoriesApi = {
//   getStories: (params?: { page?: number; industry?: string; search?: string }) =>
//     apiClient.get<PaginatedResponse<CustomerStory>>("/api/v1/customer-stories", { params }),
// 
//   getStory: (slug: string) =>
//     apiClient.get<CustomerStory>(`/api/v1/customer-stories/${slug}`),
// }

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

// TODO: Implement backend endpoint
// export const careersApi = {
//   getJobs: () =>
//     apiClient.get<Job[]>("/api/v1/careers/jobs"),
// 
//   getJob: (id: string) =>
//     apiClient.get<Job>(`/api/v1/careers/jobs/${id}`),
// }

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

// TODO: Implement backend endpoint
// export const pressApi = {
//   getReleases: () =>
//     apiClient.get<PressRelease[]>("/api/v1/press/releases"),
// 
//   getRelease: (slug: string) =>
//     apiClient.get<PressRelease>(`/api/v1/press/releases/${slug}`),
// 
//   getKit: () =>
//     apiClient.get<PressKit>("/api/v1/press/kit"),
// }

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

// TODO: Implement backend endpoint
// export const partnersApi = {
//   getPartners: (type?: string) =>
//     apiClient.get<Partner[]>("/api/v1/partners", { params: { type } }),
// 
//   getPartner: (id: string) =>
//     apiClient.get<Partner>(`/api/v1/partners/${id}`),
// }

// ─── Newsletter ──────────────────────────────────────────────
export interface NewsletterSubscribeRequest {
  email: string
  name?: string
  preferences?: string[]
}

// TODO: Implement backend endpoint
// export const newsletterApi = {
//   subscribe: (data: NewsletterSubscribeRequest) =>
//     apiClient.post<{ status: string; message: string }>("/api/v1/newsletter/subscribe", data),
// 
//   unsubscribe: (email: string) =>
//     apiClient.post<{ status: string; message: string }>("/api/v1/newsletter/unsubscribe", { email }),
// }

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

// TODO: Implement backend endpoint
// export const searchApi = {
//   search: (query: string, type?: string) =>
//     apiClient.get<SearchResponse>("/api/v1/search", { params: { q: query, type } }),
// }

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

// TODO: Implement backend endpoint
// export const notificationsApi = {
//   getNotifications: () =>
//     apiClient.get<AppNotification[]>("/api/v1/notifications"),
// 
//   markRead: (id: string) =>
//     apiClient.post<AppNotification>(`/api/v1/notifications/${id}/read`),
// 
//   markAllRead: () =>
//     apiClient.post<{ status: string }>("/api/v1/notifications/read-all"),
// 
//   getPreferences: () =>
//     apiClient.get<NotificationPreference>("/api/v1/notifications/preferences"),
// 
//   updatePreferences: (data: Partial<NotificationPreference>) =>
//     apiClient.patch<NotificationPreference>("/api/v1/notifications/preferences", data),
// }

// ── Waitlist ──────────────────────────────────────────────────────

export interface WaitlistJoinRequest {
  company_name: string
  email: string
  contact_name?: string
  company_size?: string
  country?: string
  fleet_size?: string
  source?: string
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

export const waitlistApi = {
  /** Public: join the waitlist */
  join: (data: WaitlistJoinRequest) =>
    apiClient.post<WaitlistJoinResponse>("/api/v1/waitlist/join", data),

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

  /** Public: unsubscribe */
  unsubscribe: (token: string) =>
    apiClient.get(`/api/v1/waitlist/unsubscribe/${token}`),
}
