// ─── User & Auth ────────────────────────────────────────────
export type UserRole = "owner" | "admin" | "dispatcher" | "manager" | "driver"

export interface User {
  id: number | string
  email: string
  role: UserRole
  is_admin: boolean
  company_id?: number | null
  display_name?: string
  company_name?: string | null
  subscription_tier?: PlanTier | null
  // Legacy/optional fields kept for backward compat
  name?: string
  avatar_url?: string
  email_verified?: boolean
  created_at?: string
  updated_at?: string
}

export interface LoginRequest {
  username: string
  password: string
  turnstile_token?: string
}

export interface RegisterRequest {
  email: string
  password: string
  name: string
  company_name?: string
  referral_code?: string
  turnstile_token?: string
}

export interface AuthResponse {
  access_token: string
  /** Only present on the transitional body fallback — the refresh token is normally delivered via httpOnly cookie. */
  refresh_token?: string
  token_type: string
  expires_in?: number
  user?: User
  mfa_required?: boolean
  mfa_session_token?: string
}

export interface PasswordResetRequest {
  email: string
}

export interface PasswordResetConfirm {
  token: string
  new_password: string
}

// ─── Company ────────────────────────────────────────────────
// Backend: companies table (id, company_name, subscription_tier, is_active, created_at, updated_at)
// Extended fields (address, VAT, etc.) stored via /api/v1/settings/company (JSON file)
export interface Company {
  id: string | number
  company_name: string
  subscription_tier: PlanTier
  is_active?: boolean
  // Extended settings (from JSON file)
  name?: string                    // alias for company_name
  vat_number?: string
  address?: string
  city?: string
  country?: string
  postal_code?: string
  phone?: string
  website?: string
  logo_url?: string
  industry?: string
  created_at?: string
  updated_at?: string
}

export interface CompanyUpdateRequest {
  company_name?: string
  vat_number?: string
  address?: string
  city?: string
  country?: string
  postal_code?: string
  phone?: string
  website?: string
  logo_url?: string
  industry?: string
}

// ─── Subscription ──────────────────────────────────────────
export type PlanTier = "starter" | "professional" | "enterprise"

export type BillingTerm = "monthly" | "annual"
export type SubscriptionStatus = "trialing" | "active" | "past_due" | "payment_deferred" | "canceled" | "locked"

export interface Subscription {
  id: string
  company_id: string
  billing_term: BillingTerm
  status: SubscriptionStatus
  licensed_truck_count: number
  pending_truck_count?: number
  ai_copilot_enabled: boolean
  priority_support_enabled: boolean
  api_access_enabled: boolean
  price_per_truck_erp_cents: number
  price_per_truck_ai_cents: number
  priority_support_price_cents: number
  api_access_price_cents: number
  annual_discount_pct: number
  current_period_start?: string
  current_period_end?: string
  trial_ends_at?: string
  payment_deferred_until?: string
  service_credit_cents: number
  stripe_customer_id?: string
  stripe_subscription_id?: string
  created_at: string
  updated_at: string
}

export interface SubscriptionPlan {
  id: string
  name: string
  description: string
  price_per_truck_monthly_cents: number
  price_per_truck_annual_cents: number
  ai_copilot_monthly_cents: number
  ai_copilot_annual_cents: number
  annual_discount_pct: number
  features: string[]
}

// ─── Downloads ─────────────────────────────────────────────
export interface DesktopRelease {
  version: string
  release_date: string
  windows_url: string
  macos_url?: string
  linux_url?: string
  size_mb: number
  changelog: string
  requirements: SystemRequirements
  checksums: Checksums
}

export interface SystemRequirements {
  os: string[]
  ram: string
  storage: string
  processor: string
  additional?: string
}

export interface Checksums {
  windows_sha256?: string
  macos_sha256?: string
  linux_sha256?: string
}

// ─── Documentation ─────────────────────────────────────────
export interface DocCategory {
  id: string
  title: string
  description: string
  icon: string
  article_count: number
}

export interface DocArticle {
  id: string
  category_id: string
  title: string
  excerpt: string
  content: string
  last_updated: string
  slug: string
}

// ─── Support ───────────────────────────────────────────────
export interface SupportTicket {
  id: number | string
  subject: string
  status: "open" | "in_progress" | "resolved" | "closed"
  priority: "low" | "medium" | "high" | "urgent"
  created_at: string
  updated_at: string
}

// ─── API ───────────────────────────────────────────────────
export interface ApiError {
  detail: string
  code?: string
  field_errors?: Record<string, string[]>
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ─── Blog ───────────────────────────────────────────────────
export interface BlogAuthor {
  id: number | string
  name: string
  avatar_url?: string
  bio?: string
  role?: string
}

export interface BlogCategory {
  id: number | string
  name: string
  slug: string
  description?: string
  post_count?: number
}

export interface BlogPost {
  id: number | string
  title: string
  slug: string
  excerpt: string
  content?: string
  // Denormalized from blog_authors table
  author_name?: string
  author_avatar?: string
  // Denormalized from blog_categories table
  category?: string
  category_id?: number | string
  tags: string[]
  featured_image?: string
  reading_time_minutes: number
  published_at?: string
  seo_title?: string
  seo_description?: string
  created_at?: string
  updated_at?: string
}

// ─── Changelog ──────────────────────────────────────────────
export interface ChangelogSection {
  type: "added" | "changed" | "fixed" | "removed" | "deprecated"
  items: string[]
}

export interface ChangelogEntry {
  version: string
  release_date: string
  sections: ChangelogSection[]
  known_issues?: string[]
}

// ─── Roadmap ────────────────────────────────────────────────
export type RoadmapStatus = "planned" | "in_progress" | "completed" | "cancelled"

export interface RoadmapItem {
  id: string
  title: string
  description: string
  status: RoadmapStatus
  category: string
  target_date?: string
  votes?: number
}

// ─── Service Status ─────────────────────────────────────────
export type ServiceHealth = "operational" | "degraded" | "outage" | "maintenance"

export interface ServiceStatus {
  name: string
  status: ServiceHealth
  description?: string
  updated_at: string
}

export interface ServiceStatusGroup {
  name: string
  services: ServiceStatus[]
}

// ─── Tutorials ──────────────────────────────────────────────
export type TutorialCategory = "beginner" | "intermediate" | "advanced" | "administrator" | "dispatcher" | "driver" | "installation" | "ai" | "ocr" | "analytics"

export interface Tutorial {
  id: string
  title: string
  slug: string
  excerpt: string
  content: string
  category: TutorialCategory
  reading_time_minutes: number
  published_at: string
  updated_at: string
  related_doc_ids?: string[]
  video_url?: string
}

// ─── Developer Resources ────────────────────────────────────
export type DevResourceType = "toolkit" | "api" | "sdk" | "integration" | "guide"

export interface DevResource {
  id: string
  title: string
  description: string
  icon: string
  type: DevResourceType
  href: string
}

// ─── Security Reports ──────────────────────────────────────
export type SecuritySeverity = "low" | "medium" | "high" | "critical"

export interface SecurityReport {
  id: string
  title: string
  description: string
  severity: SecuritySeverity
  status: string
  reported_at: string
  resolved_at?: string
}

// ─── Announcements ──────────────────────────────────────────
export type AnnouncementSeverity = "info" | "warning" | "success"

export interface Announcement {
  id: string
  title: string
  content: string
  severity: AnnouncementSeverity
  is_pinned: boolean
  published_at: string
  expires_at?: string
}

// ─── Notification Preferences ───────────────────────────────
export interface NotificationPreference {
  email_notifications: boolean
  product_updates: boolean
  security_alerts: boolean
  marketing_emails: boolean
  blog_digest: boolean
}

// ─── User Sessions ──────────────────────────────────────────
export interface UserSession {
  id: string
  device: string
  browser: string
  ip: string
  location?: string
  last_active: string
  is_current: boolean
}

// ─── Invoices ───────────────────────────────────────────────
export type InvoiceStatus = "paid" | "open" | "void" | "draft"

export interface Invoice {
  id: string
  number: string
  amount: number
  currency: string
  status: InvoiceStatus
  issued_at: string
  due_at: string
  paid_at?: string
  pdf_url?: string
}

// ─── Analytics ──────────────────────────────────────────────
export interface AnalyticsEvent {
  name: string
  category: string
  label?: string
  value?: number
  metadata?: Record<string, unknown>
}

// ─── Organization ──────────────────────────────────────────
// The backend Organizations API (/api/v1/organizations router) is canonical for
// teams, membership, and invitations: GET /organizations, GET/POST/PATCH /organizations/{slug},
// GET /organizations/{slug}/members, DELETE /organizations/{slug}/members/{member_id},
// GET/POST /organizations/{slug}/invitations, POST /organizations/invitations/{token}/accept.
// users.company_id remains for legacy single-company billing ownership and coexists by design —
// these types map to the backend org model, not to the legacy companies table.
export interface Organization {
  id: string | number
  name: string
  company_name?: string
  subscription_tier?: PlanTier
  is_active?: boolean
  slug?: string          // backend-provided (Organizations API); frontend may compute it as a fallback
  logo_url?: string      // backend-provided via Organizations API / settings JSON
  // Extended settings (from /api/v1/settings/company JSON)
  industry?: string
  address?: string
  city?: string
  country?: string
  postal_code?: string
  vat_number?: string
  phone?: string
  website?: string
  size?: "1-10" | "11-50" | "51-200" | "201-500" | "501+"
  created_at?: string
  updated_at?: string
  member_count?: number
  user_role?: "owner" | "admin" | "member"
}

// Backend-backed: mirrors the Organizations API member records (GET /organizations/{slug}/members,
// DELETE /organizations/{slug}/members/{member_id}). users.company_id is separate and only tracks
// legacy single-company billing ownership.
export interface OrganizationMember {
  id: string | number
  org_id: string | number
  user_id: string | number
  role: "owner" | "admin" | "member"  // NOTE: "admin" here = org admin, NOT developer admin (is_admin flag)
  status: "active" | "pending" | "suspended"
  name?: string          // from JOIN with users table
  email?: string         // from JOIN with users table
  joined_at?: string
  invited_at?: string    // only in mock data
}

export interface OrganizationInvitation {
  id: string | number
  org_id: string | number
  email: string
  role: string
  token: string
  invited_by?: string | number
  invited_by_name?: string  // from JOIN
  status: "pending" | "accepted" | "expired"
  created_at?: string
  expires_at?: string
}

// ─── User Management ───────────────────────────────────────
export interface UserProfile extends User {
  timezone?: string
  language?: string
  bio?: string
  phone?: string
  job_title?: string
  department?: string
}

export interface UserPermission {
  resource: string
  actions: ("read" | "write" | "delete" | "admin")[]
}

export interface UserRole_ {
  name: string
  permissions: UserPermission[]
}

// ─── Licensing ─────────────────────────────────────────────
export interface License {
  id: string | number
  license_key: string
  plan_tier: string
  seats: number
  seats_used: number
  status: "active" | "suspended" | "expired" | "revoked"
  issued_at: string
  expires_at?: string
  created_at?: string
}

export interface LicenseDevice {
  id: string | number
  license_id?: string | number
  name: string
  os?: string
  ip?: string
  last_seen?: string
  activated_at?: string
}

// ─── Device Management ─────────────────────────────────────
export interface DeviceInfo {
  id: number
  device_id: string
  device_name: string
  platform: string
  user_email: string
  user_name: string
  is_active: boolean
  last_seen: string
  created_at: string
}

// ─── Onboarding ────────────────────────────────────────────
export interface OnboardingStep {
  id: string
  title: string
  description: string
  completed: boolean
  required: boolean
  link?: string
}

export interface OnboardingChecklist {
  steps: OnboardingStep[]
  completed_count: number
  total_count: number
}

// ─── Integrations ──────────────────────────────────────────
export interface Integration {
  id: string
  name: string
  description: string
  icon: string
  category: "telematics" | "accounting" | "communication" | "analytics" | "erp" | "other"
  status: "available" | "planned" | "beta"
  provider: string
  website_url: string
}

// ─── Customer Stories ──────────────────────────────────────
export interface CustomerStory {
  id: string
  title: string
  slug: string
  company_name: string
  industry: string
  company_size: string
  logo_url?: string
  excerpt: string
  content: string
  challenge: string
  solution: string
  results: { metric: string; value: string }[]
  featured: boolean
  published_at: string
}

// ─── Careers ───────────────────────────────────────────────
export interface JobPosting {
  id: string
  title: string
  department: string
  location: string
  type: "full-time" | "part-time" | "contract" | "remote"
  description: string
  requirements: string[]
  posted_at: string
}

// ─── Press ─────────────────────────────────────────────────
export interface PressRelease {
  id: string
  title: string
  slug: string
  excerpt: string
  content: string
  published_at: string
  category: "product" | "company" | "partnership" | "award"
}

export interface PressKit {
  logos: { name: string; url: string; type: "svg" | "png" }[]
  brand_colors: { name: string; hex: string }[]
  downloads: { name: string; url: string }[]
}

// ─── Partners ──────────────────────────────────────────────
export interface Partner {
  id: string
  name: string
  logo_url: string
  type: "technology" | "implementation" | "reseller"
  description: string
  website_url: string
  featured: boolean
}

// ─── Newsletter ────────────────────────────────────────────
export interface NewsletterSubscription {
  email: string
  preferences: {
    product_updates: boolean
    blog_digest: boolean
    event_invites: boolean
    partner_offers: boolean
  }
}

// ─── Global Search ─────────────────────────────────────────
export interface SearchResult {
  id: string
  title: string
  excerpt: string
  type: "doc" | "blog" | "tutorial" | "faq" | "changelog" | "roadmap" | "download"
  url: string
  category?: string
}

export interface SearchResults {
  query: string
  results: SearchResult[]
  total: number
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

// ─── Ops Console ──────────────────────────────────────────────
export interface OpsTicket {
  issue_id: string
  company_id?: string
  summary: string
  risk_tier: "low" | "medium" | "high" | "critical"
  status: string
  customer_impact?: string
  created_at: string
  updated_at: string
}

export interface OpsTicketDetail extends OpsTicket {
  customer_id: string
  reported_by_channel: string
  reproduction_steps: string[]
  logs: string | null
  attachments: any[]
  suspected_module: string
  app_version: string
  environment: string
  linked_known_issue_id: string | null
  confidence_at_escalation: number | null
}

export interface StateLogEntry {
  id: number
  issue_id: string
  from_state: string | null
  to_state: string
  entered_at: string
  duration_ms: number | null
  outcome: string | null
  detail: Record<string, any> | null
}

export interface OpsApproval {
  issue_id: string
  summary: string
  risk_tier: string
  status: string
  files_changed: number
  tests_passed: number
  invariants_passed: number
  has_elevated_scrutiny: boolean
  created_at: string
}

export interface GuardrailViolation {
  id: number
  guardrail_id: string
  severity: string
  diff_excerpt: string
  issue_id: string | null
  resolved: boolean
  created_at: string
}

export interface OpsSummary {
  unresolved: number
  pending_approvals: number
  patch_success_rate: number
  critical_escalations: number
}

export interface KnowledgeDraft {
  id: number
  corpus: string
  doc_id: string
  section: string | null
  content: string
  status: string
  last_updated: string
}

// ─── Audit Log ────────────────────────────────────────────
export interface AuditLogEntry {
  id: string
  company_id: string
  actor_user_id: string
  actor_name?: string
  action: AuditAction
  target_type?: string
  target_id?: string
  metadata?: Record<string, string>
  ip_address?: string
  created_at: string
}

export type AuditAction =
  | "login"
  | "logout"
  | "password_change"
  | "mfa_enabled"
  | "mfa_disabled"
  | "member_invited"
  | "member_removed"
  | "role_changed"
  | "device_deactivated"
  | "license_transferred"
  | "subscription_changed"
  | "settings_updated"
  | "data_exported"
  | "account_deleted"
  | "referral_created"
  | "referral_redeemed"

// ─── Notifications ─────────────────────────────────────────
export interface PortalNotification {
  id: string
  type: "release" | "billing" | "security" | "support" | "doc_update" | "system"
  title: string
  message: string
  read: boolean
  link?: string
  created_at: string
}
