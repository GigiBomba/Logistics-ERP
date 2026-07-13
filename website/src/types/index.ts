// ─── User & Auth ────────────────────────────────────────────
export type UserRole = "admin" | "dispatcher" | "manager" | "driver"

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
}

export interface RegisterRequest {
  email: string
  password: string
  name: string
  company_name?: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in?: number
  user?: User
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
export type SubscriptionStatus = "active" | "past_due" | "canceled" | "trialing" | "incomplete"

export interface Subscription {
  id: string
  plan_tier: PlanTier
  status: SubscriptionStatus
  current_period_start: string
  current_period_end: string
  cancel_at_period_end: boolean
  licenses: number
  licenses_used: number
}

export interface Plan {
  tier: PlanTier
  name: string
  description: string
  price_monthly: number
  price_yearly: number
  features: string[]
  highlighted?: boolean
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
  id: string
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
  id: string
  name: string
  avatar_url?: string
  bio?: string
  role: string
}

export interface BlogCategory {
  id: string
  name: string
  slug: string
  post_count: number
}

export interface BlogPost {
  id: string
  title: string
  slug: string
  excerpt: string
  content: string
  author: BlogAuthor
  category_id: string
  tags: string[]
  featured_image?: string
  reading_time_minutes: number
  published_at: string
  updated_at: string
  seo_title?: string
  seo_description?: string
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
// FRONTEND-ONLY: Backend only supports one company per user (via users.company_id FK).
// Multi-org support is a planned future backend feature. These types represent the
// eventual multi-org model and currently map to the single companies table.
export interface Organization {
  id: string | number
  name: string
  company_name?: string
  subscription_tier?: PlanTier
  is_active?: boolean
  slug?: string          // frontend-computed from company_name
  logo_url?: string      // frontend-only, from settings JSON
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
}

// FRONTEND-ONLY: Backend has no org membership system (only users.company_id FK).
// This represents the planned member model.
export interface OrganizationMember {
  id: string
  org_id: string
  user_id: string
  role: "owner" | "admin" | "member"  // NOTE: "admin" here = org admin, NOT developer admin (is_admin flag)
  invited_at?: string
  joined_at: string
  status: "active" | "pending" | "suspended"
}

export interface OrganizationInvitation {
  id: string
  org_id: string
  email: string
  role: "owner" | "admin" | "member"
  invited_by: string
  created_at: string
  expires_at: string
  status: "pending" | "accepted" | "expired"
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
  id: string
  org_id: string
  plan_tier: string
  seats_total: number
  seats_used: number
  status: "active" | "expired" | "suspended" | "trial"
  issued_at: string
  expires_at?: string
  renewal_date?: string
  features: string[]
}

export interface Device {
  id: string
  license_id: string
  name: string
  platform: string
  last_active: string
  is_active: boolean
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
