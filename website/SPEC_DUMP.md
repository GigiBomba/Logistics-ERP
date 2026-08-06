# 📋 ULTIMATE SPEC DUMP: Operion Website — Every Aspect

> Generated: July 2026  
> Purpose: Blueprint for comprehensive website improvement  
> Project: `C:\Users\Bonjo\source\repos\operion-website`

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [App Architecture & Initialization](#3-app-architecture--initialization)
4. [Routing & Navigation](#4-routing--navigation)
5. [Authentication & Security](#5-authentication--security)
6. [Theme & Styling System](#6-theme--styling-system)
7. [Internationalization (i18n)](#7-internationalization-i18n)
8. [API Layer](#8-api-layer)
9. [Data Types & Models](#9-data-types--models)
10. [Dashboard Pages — Complete Walkthrough](#10-dashboard-pages--complete-walkthrough)
11. [Public Marketing Pages — Complete Walkthrough](#11-public-marketing-pages--complete-walkthrough)
12. [Auth Pages](#12-auth-pages)
13. [Admin Pages](#13-admin-pages)
14. [Shared Components](#14-shared-components)
15. [Device Management Feature — Complete Analysis](#15-device-management-feature--complete-analysis)
16. [UX Patterns & Design System](#16-ux-patterns--design-system)
17. [Onboarding & User Journey](#17-onboarding--user-journey)
18. [Marketing & Conversion](#18-marketing--conversion)
19. [Testing Infrastructure](#19-testing-infrastructure)
20. [Complete Gaps & Improvement Areas](#20-complete-gaps--improvement-areas)
21. [Configuration Summary](#21-configuration-summary)
22. [Environment & Deployment](#22-environment--deployment)

---

## 1. Project Overview

**Operion** is a **logistics operations ERP platform** serving transport, freight, fleet, and logistics companies. The website at `https://operion.com` serves as both the **public marketing site** (50+ pages) and the **customer portal/dashboard** (15 protected pages) for a desktop + mobile logistics application stack.

**Current stage**: Final productization phase — all major backend features complete, frontend UI built, real API consumed for auth/companies/devices/blogs/support/organizations/licenses. Several dashboard features use mock data (subscription, billing, invoices) because backend endpoints are not yet live.

**Backend API**: `https://api.operionerp.xyz` (Python/FastAPI) — documented via Cloudflare endpoints, uses OAuth2 JWT, real PostgreSQL database.

**Separate but related**: A full Python/FastAPI ERP backend exists at `Calculator logistica/` with its own PostgreSQL schema (1088 lines) covering trucks, drivers, trips, invoices, CMR documents, GPS telemetry, tachograph data, maintenance, webhooks, and more.

---

## 2. Technology Stack

### Frontend

| Category | Library | Version |
|----------|---------|---------|
| UI Framework | React | 19.2.7 |
| Build Tool | Vite | 8.1.1 |
| Language | TypeScript | 6.0.2 |
| Routing | react-router | 7.18.1 |
| Server State | @tanstack/react-query | 5.101.2 |
| Forms | react-hook-form + @hookform/resolvers | 7.81.0 / 5.4.0 |
| Validation | zod | 4.4.3 |
| Styling | Tailwind CSS | 4.3.2 |
| Animations | motion | 12.42.2 |
| Icons | lucide-react | 1.24.0 |
| HTTP Client | axios | 1.7.9 |
| Toasts | sonner | 2.0.7 |
| SEO Head | react-helmet-async | 3.0.0 |
| Error Boundaries | react-error-boundary | — |
| Testing (Unit) | Vitest | 4.1.10 |
| Testing (E2E) | Playwright | 1.61.1 |
| Testing (Mutation) | Stryker | — |
| Linting | Oxlint | 1.71.0 |
| CSS Plugin | @tailwindcss/typography | — |

### Backend (consumed, not hosted in this repo)

| Layer | Technology |
|-------|-----------|
| API Server | Python FastAPI |
| Auth | OAuth2 with JWT |
| Database | PostgreSQL |
| Hosting | Cloudflare Workers (API) |
| Email | SMTP |
| Storage | likely R2/S3 for documents |

---

## 3. App Architecture & Initialization

### Entry Point (`main.tsx`)

```
createRoot → StrictMode
  → ErrorBoundary (fallback UI: "Something went wrong" + Try Again button)
    → HelmetProvider (SEO head management)
      → QueryClientProvider (TanStack Query)
        │ staleTime: 5min, retry: 1, refetchOnWindowFocus: false
        → ThemeProvider (light/dark/system)
          → LocaleProvider (en/ro/de/fr/es/pl)
            → AuthProvider (JWT-based auth state)
              → App (BrowserRouter + Routes)
                → Toaster (sonner, bottom-right, rich colors, close button)
```

### Provider Details

**QueryClient**:
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,  // 5 min
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
```

**ErrorBoundary**: Uses `react-error-boundary` at the top level — catches all uncaught React errors. Shows centered error message with "Try again" button.

**Toaster**: Uses `sonner` positioned `bottom-right` with `richColors` and a close button.

---

## 4. Routing & Navigation

### Route Architecture (`App.tsx`, 807 lines)

```
<BrowserRouter>
  <Route element={<AppShell />}>              ← Layout switch: Dashboard vs Public
    │
    ├── Public Routes (∼50)                   ← Under PublicLayout (header + footer)
    │   ├── / (HomePage)                      ← Full marketing hero
    │   ├── /features                         ← Features page
    │   ├── /pricing                          ← Pricing page
    │   ├── /download                         ← Desktop download page
    │   ├── /about, /argo, /mission           ← Brand pages
    │   ├── /faq, /contact                    ← Support pages
    │   ├── /privacy, /terms                  ← Legal pages
    │   ├── /blog, /blog/:slug, /blog/category/:category, /blog/author/:authorId
    │   ├── /tutorials, /tutorials/:slug
    │   ├── /changelog, /roadmap, /status     ← Product updates
    │   ├── /security                         ← Security info
    │   ├── /developers, /developers/toolkit
    │   ├── /products, /integrations
    │   ├── /community, /newsletter, /customers
    │   ├── /careers, /press, /brand
    │   ├── /enterprise, /partners
    │   ├── /trust, /trust-center
    │   ├── /api-playground, /integrations-explorer
    │   ├── /waitlist                         ← Lead gen funnel
    │   ├── /product-tour, /roi-calculator, /route-demo
    │   ├── /industries/transport, /freight, /fleet, /owner-operators,
    │   │     /agriculture, /construction, /manufacturing
    │   └── Error pages: /500, /maintenance, /offline, *
    │
    ├── Auth Routes (no AppShell layout)      ← Clean centered layout
    │   ├── /login
    │   ├── /register
    │   ├── /forgot-password
    │   ├── /reset-password
    │   └── /verify-email
    │
    ├── <ProtectedRoute>                      ← Auth guard
    │   └── Dashboard Routes (15)
    │       ├── /dashboard                    ← Main overview
    │       ├── /dashboard/profile            ← Profile & settings
    │       ├── /dashboard/company            ← Company info
    │       ├── /dashboard/subscription       ← Plan management
    │       ├── /dashboard/billing            ← Billing & invoices
    │       ├── /dashboard/devices            ← Mobile device mgmt
    │       ├── /dashboard/licenses           ← License management
    │       ├── /dashboard/downloads          ← Desktop app downloads
    │       ├── /dashboard/docs               ← Documentation
    │       ├── /dashboard/support            ← Support tickets
    │       ├── /dashboard/settings           ← App settings
    │       ├── /dashboard/organizations      ← Multi-org
    │       ├── /dashboard/organizations/:slug/settings
    │       ├── /dashboard/onboarding         ← Getting started
    │       └── /dashboard/referrals          ← Referral program
    │
    ├── Docs Routes
    │   └── /docs, /docs/:category, /docs/:category/:slug
    │
    ├── <AdminRoute>                          ← Auth + admin guard
    │   ├── /admin/blog/editor, /admin/blog/editor/:slug
    │   ├── /admin/waitlist                   ← Waitlist management
    │   └── /admin/ops/*                      ← Ops console (5 pages)
    │
    └── Error Pages (no AppShell)
        └── /500, /maintenance, /offline, *
```

### Navigation System (`src/config/navigation.ts`)

3 navigation data structures:
- **`publicNavItems`**: 9 top-level nav items with dropdown children (Product, Tools, About)
- **`footerNavSections`**: 5 columns (Product, Solutions, Company, Resources, Legal)
- **`dashboardNavItems`**: 12 sidebar items with icons — Overview, Profile, Company, Subscription, Devices, Referrals, Downloads, Documentation, Support, Support Ops (admin), Settings

### Layout Switch (`app-shell.tsx`)

```typescript
function AppShell() {
  const location = useLocation()
  const isDashboard = location.pathname.startsWith("/dashboard")
  if (isDashboard) return <DashboardLayout />
  return <PublicLayout />
}
```

### PublicLayout (∼770 lines)

- **Header**: sticky, backdrop-blur, border-b
  - Logo → `/`
  - Desktop nav: dropdowns on hover with 150ms delay, ChevronDown animation
  - Search trigger: ⌘K, border, hover effect
  - Theme toggle: light↔dark↔system cycle
  - LanguageSwitcher dropdown
  - If authenticated: avatar + "Dashboard" link
  - If not: [Sign In] ghost button + [Waitlist] primary button
  - Mobile: hamburger menu with full nav + auth actions
- **Footer**: 5-column grid, newsletter form, status indicator (pulsing green dot), copyright, privacy/terms
- **GlobalSearch**: modal overlay (⌘K)

### DashboardLayout (∼770 lines)

- **Sidebar** (fixed, 280px, scrollable, mobile-overlay):
  - Logo + app name
  - User avatar + name + email
  - 12 nav items with icons, active highlighting
  - `OrgSwitcher` at bottom
  - Logout button (destructive hover)
- **Header** (sticky, 56px, backdrop-blur):
  - Mobile hamburger toggle
  - Search trigger (⌘K)
  - Theme toggle
  - LanguageSwitcher
  - LiveChat trigger
  - Notification bell (no badge/dropdown yet)
  - User menu dropdown (slide-down animation): Profile, Settings, Sign Out
- **Main**: `<Outlet />` with `p-6`

---

## 5. Authentication & Security

### Auth Context (`auth-provider.tsx`, 149 lines)

**Stored tokens** (all in localStorage):

| Key | Value |
|-----|-------|
| `operion-access-token` | JWT access token |
| `operion-refresh-token` | JWT refresh token |
| `operion-avatar-url` | Cached avatar URL |
| `operion-locale` | Locale code |
| `operion-theme` | Theme preference |

**AuthContextValue:**
```typescript
{
  user: User | null,
  isLoading: boolean,
  isAuthenticated: boolean,
  isAdmin: boolean,
  login: (email, password) => Promise<void>,
  register: (data) => Promise<void>,
  logout: () => void,
  refreshUser: () => Promise<void>,
  updateUser: (user) => void,
}
```

**Login flow:**
1. `POST /api/v1/auth/token` with `username: email`, `password`, `grant_type: password` (URL-encoded)
2. Store access + refresh tokens in localStorage
3. Fetch `GET /api/v1/auth/me` for full user profile
4. Set user in state, preserving stored avatar URL as fallback

**Register flow:**
1. `POST /api/v1/registration/register` with email, password, display_name, company_name, referral_code
2. Response includes tokens + user object → stored + state set
3. Navigate to `/verify-email`

**Logout flow:**
- Client-side only: removes tokens + avatar from localStorage, sets user to null
- Does NOT call backend logout endpoint

**Session restore on mount:**
1. Read token from localStorage
2. If exists → call `/api/v1/auth/me`
3. On 401 → clear all auth state
4. Set `isLoading = false`

**Admin check:**
```typescript
const isAdmin = user?.is_admin === true || user?.role === "admin"
```

### API Client (`client.ts`, 144 lines)

**Axios instance:**
- `baseURL`: empty in dev (Vite proxy), `https://api.operionerp.xyz` in prod
- `timeout`: 15 seconds

**Request interceptor:**
- Attaches `Authorization: Bearer <token>`
- Attaches `X-CSRF-Token` (read from `csrf_token` cookie) for POST/PUT/PATCH/DELETE

**Response interceptor (401 refresh):**
1. On 401: if already retrying → queue the request (promise queue pattern)
2. Set `_retry = true`, `isRefreshing = true`
3. `POST /api/v1/auth/refresh` with refresh_token
4. On success: store new tokens, process queued requests, retry original
5. On failure: clear auth, redirect to `/login` (unless already on `/login`)
6. Queue ensures concurrent 401s don't cause multiple refresh attempts

**CSRF Protection:** Double-submit cookie pattern — backend sets `csrf_token` cookie, frontend sends as `X-CSRF-Token` header.

**Error extraction:**
```typescript
extractApiError(error) → string
// Handles AxiosError with ApiError shape:
// { detail: string, field_errors: Record<string, string[]> }
```

### JWT Decoding (`jwt.ts`, 38 lines)
- Client-side decode with NO signature verification (intentional)
- Used ONLY for UI gating (admin panel visibility)
- Server always verifies signatures on protected endpoints

### Route Guards (`protected-route.tsx`, 33 lines)

**ProtectedRoute** (dashboard):
- Loading → centered `LoadingSpinner size="lg"`
- Not authenticated → `<Navigate to="/login" replace />`
- OK → `<Outlet />`

**AdminRoute** (admin pages):
- Same as ProtectedRoute
- Not admin → `<Navigate to="/dashboard" replace />`
- Note: No redirect back to original page after login (no `?returnUrl=` parameter)

### Security Model Summary

| Mechanism | Detail |
|-----------|--------|
| Auth protocol | OAuth2 password grant |
| Token type | JWT (access + refresh) |
| Token storage | localStorage (XSS-vulnerable by design) |
| Refresh | Automatic via interceptor with request queue |
| CSRF | Double-submit cookie (csrf_token → X-CSRF-Token header) |
| Frontend auth guard | ProtectedRoute + AdminRoute components |
| JWT client decode | No signature verification (UI gating only) |
| Server verification | JWT signature verified on every protected endpoint |
| API proxy | Vite proxy in dev (avoids CORS) |
| No 2FA | Placeholder UI only, "coming soon" |
| No SSO | Not implemented |
| No "Remember me" | Not implemented |

---

## 6. Theme & Styling System

### Theme Provider (`theme-provider.tsx`, 64 lines)
- 3 modes: `light`, `dark`, `system`
- Persisted to `localStorage("operion-theme")`
- System mode: listens to `prefers-color-scheme` media query, updates live
- Applies `.dark`/`.light` class on `<html>` element
- Tailwind v4 uses `@custom-variant dark (&:is(.dark *))` — explicit class strategy

### CSS Architecture
- **`globals.css`** — 159 lines: Tailwind imports, CSS variables (OKLCH), custom utilities
- **`interactions.css`** — custom interaction animations

### Color System (OKLCH)

| Token | Light | Dark |
|-------|-------|------|
| `--primary` | `oklch(0.38 0.14 265)` — deep indigo | `oklch(0.7 0.16 265)` — lighter indigo |
| `--background` | `oklch(1 0 0)` — white | `oklch(0.145 0 0)` — near-black |
| `--card` | `oklch(1 0 0)` | `oklch(0.18 0 0)` |
| `--destructive` | `oklch(0.577 0.245 27.325)` — red | `oklch(0.5 0.2 27)` |
| `--sidebar` | `oklch(0.985 0 0)` | `oklch(0.16 0 0)` |

**Chart palette**: 5-color scheme (indigo, teal, green, amber, orange)

**Typography**: 
- Sans: `Inter, ui-sans-serif, system-ui, sans-serif`
- Mono: `"JetBrains Mono", ui-monospace, monospace`
- Border radius: Default `--radius: 0.625rem` (10px), with sm/md/lg/xl variants

**Utilities**:
- `.container-tight`: max-w-5xl with px-4/6/8
- `.container-wide`: w-full with px-6/10/16
- `img { content-visibility: auto }` — performance optimization
- `prefers-reduced-motion: reduce` — disables all animations

### Component UI Library
17 shadcn/ui-style components rebuilt from scratch: `avatar`, `badge`, `breadcrumb`, `button`, `callout`, `card`, `copy-button`, `input`, `loading-spinner`, `pagination`, `progress`, `separator`, `skeleton`, `tabs`, `tag`, `tooltip`

**Button variants**: `default`, `secondary`, `destructive`, `outline`, `ghost`, `link`
**Button sizes**: `sm`, `default`, `lg`, `xl`

---

## 7. Internationalization (i18n)

### Locale Provider (`locale-context.tsx`, 69 lines)
- **6 locales**: English, Romanian, German, French, Spanish, Polish
- Default: English (`en`)
- Persisted to `localStorage("operion-locale")`
- Flat key-value JSON translation files (no nesting)
- `t(key)` function: tries current locale → falls back to default locale → returns raw key

### Supported Locales

| Code | Language |
|------|----------|
| `en` | English |
| `ro` | Romanian |
| `de` | German |
| `fr` | French |
| `es` | Spanish |
| `pl` | Polish |

### Translation Key Structure
Namespace pattern: `domain.section.key`
- `nav.home`, `nav.features`, `nav.pricing`
- `home.hero.title`, `home.hero.subtitle`
- `features.route.heading`, `features.fleet.heading`
- `dashboard.welcomeBack`, `dashboard.overview`
- `profile.title`, `profile.general`
- `subscription.title`, `subscription.plan`
- `billing.pageTitle`, `billing.invoices`
- `settings.title`, `settings.appearance`
- `auth.welcomeBack`, `auth.signInDesc`
- `waitlist.heroTitle`, `waitlist.joinButton`
- `support.pageTitle`, `support.submitTicket`
- `language.en`, `language.ro`, `language.de`
- `footer.privacy`, `footer.terms`
- `common.signIn`, `common.dashboard`, `common.comingSoon`

---

## 8. API Layer

### Auth (12 endpoints)
```
POST   /api/v1/auth/token                    → Login (OAuth2 password)
POST   /api/v1/registration/register         → Register
POST   /api/v1/auth/logout                   → Logout (exists but unused in UI)
POST   /api/v1/auth/refresh                  → Refresh token
POST   /api/v1/auth/forgot-password          → Forgot password
POST   /api/v1/auth/reset-password           → Reset password
POST   /api/v1/auth/verify-email             → Verify email
GET    /api/v1/auth/me                       → Get current user
PATCH  /api/v1/auth/me                       → Update profile
POST   /api/v1/auth/change-password          → Change password
GET    /api/v1/auth/sessions                 → List sessions
DELETE /api/v1/auth/sessions/:id             → Revoke session
```

### Company (2 endpoints)
```
GET    /api/v1/company                       → Get company info
PATCH  /api/v1/company                       → Update company info
```

### Support (4 endpoints)
```
POST   /api/v1/support/tickets               → Create ticket
GET    /api/v1/support/tickets               → List tickets
GET    /api/v1/support/tickets/:id           → Get ticket detail
POST   /api/v1/support/messages              → Send message (live chat with ARGO)
```

### Blog (10 endpoints)
Full CRUD for posts, categories, authors + admin management.

### Content (10 endpoints)
Changelog, roadmap, status, tutorials, developer resources, security reports, announcements.

### Organizations (9 endpoints)
CRUD orgs, members, invitations, accept invitation.

### Licenses (4 endpoints)
```
GET    /api/v1/licenses                      → List licenses
GET    /api/v1/licenses/:id                  → Get license
GET    /api/v1/licenses/:id/devices          → List license devices
DELETE /api/v1/licenses/:id/devices/:deviceId → Remove device from license
```

### Mobile Devices (2 endpoints)
```
GET    /api/v1/mobile/devices                → List mobile devices
DELETE /api/v1/mobile/devices/:deviceId      → Deactivate device
```

### Onboarding (2 endpoints)
```
GET    /api/v1/onboarding/checklist          → Get checklist
POST   /api/v1/onboarding/steps/:id/complete → Complete step
```

### Integrations + Customer Stories (4 endpoints)

### Careers / Press / Partners (8 endpoints)

### Newsletter / Search / Notifications (8 endpoints)

### Waitlist (10 endpoints)
Join, admin CRUD, export CSV, stats, campaigns.

### Referral (5 endpoints)
My referrals, track, admin list/stats.

### Ops Console (10 endpoints)
Tickets, approvals, guardrails, dashboard, knowledge docs.

### Commented-out / Future Endpoints
```typescript
// subscriptionApi — commented out
//   GET /api/v1/subscriptions/current
//   GET /api/v1/subscriptions/plans

// downloadApi — commented out
//   GET /api/v1/downloads/latest
//   GET /api/v1/downloads/versions

// invoicesApi — commented out
//   GET /api/v1/subscriptions/invoices
```

---

## 9. Data Types & Models

### `src/types/index.ts` (683 lines)

**User & Auth:**
```typescript
UserRole = "admin" | "dispatcher" | "manager" | "driver"

User { id, email, role, is_admin, company_id?, display_name?,
       company_name?, subscription_tier?, name?, avatar_url?,
       email_verified?, created_at?, updated_at? }

AuthResponse { access_token, refresh_token, token_type, expires_in?, user? }
```

**Company:**
```typescript
Company { id, company_name, subscription_tier, is_active?,
          name?, vat_number?, address?, city?, country?,
          postal_code?, phone?, website?, logo_url?, industry?,
          created_at?, updated_at? }
```

**Subscription / Plans:**
```typescript
PlanTier = "starter" | "professional" | "enterprise"
SubscriptionStatus = "active" | "past_due" | "canceled" | "trialing" | "incomplete"
Subscription { id, plan_tier, status, current_period_start/end, cancel_at_period_end, licenses, licenses_used }
Plan { tier, name, description, price_monthly, price_yearly, features, highlighted? }
```

**Device Management:**
```typescript
DeviceInfo { id, device_id, device_name, platform, user_email, user_name,
             is_active, last_seen, created_at }
LicenseDevice { id, license_id?, name, os?, ip?, last_seen?, activated_at? }
License { id, license_key, plan_tier, seats, seats_used, status, issued_at, expires_at? }
```

**Organizations:**
```typescript
Organization { id, name, slug?, logo_url?, industry?, address?, city?, country?, ... }
OrganizationMember { id, org_id, user_id, role, status, name?, email?, joined_at? }
OrganizationInvitation { id, org_id, email, role, token, status, created_at? }
```

**Blog:** `BlogPost { id, title, slug, excerpt, content?, author_name?, tags, ... }`

**Support:** `SupportTicket { id, subject, status, priority, created_at, updated_at }`

**Notifications:** `PortalNotification { id, type, title, message, read, link?, created_at }`

**Ops Console:** `OpsTicket`, `OpsTicketDetail`, `OpsApproval`, `GuardrailViolation`, `OpsSummary`, `KnowledgeDraft`

---

## 10. Dashboard Pages — Complete Walkthrough

### 10.1 `/dashboard` — Main Dashboard (`dashboard.tsx`, 423 lines)

**Data source**: All hardcoded mock data (no API calls)

**Sections**:
1. **Header**: "Welcome back" + subtitle (i18n)
2. **Stats Row** (4 cards): Core Modules (8), Native Apps (2), Online Portal (green pulse), Development status
3. **Tabs**: Overview | Recent Activity
4. **Overview tab**:
   - **Subscription Summary** (3 cards): Professional Plan active, Licenses used, Latest version
   - **Quick Actions** (3 cards): Downloads, Documentation, Support
   - **Two-column**: Storage Usage (2.3GB/10GB, 23%) + Active Sessions
   - **Documentation Shortcuts** (5 cards): Getting Started, Route Planning, Dispatch, Integrations, API Reference
   - **Latest Release** (ReleaseCard): v1.0.0 with features
   - **Announcements** (2 items)
5. **Activity tab**: Timeline with 5 events (login, release, password change, etc.)

### 10.2 `/dashboard/profile` — Profile Page (`profile.tsx`, 556 lines)

**Data source**: `useProfile()` → `GET /api/v1/auth/me`

**Tabs**: General | Security | Notifications | Sessions

**General tab** (6 cards):
- Profile Information (name + email form, saves via API)
- Avatar Upload (file picker, preview, local state save only)
- Timezone (8 options, local state)
- Language (6 options, local state)
- Theme (Light/Dark/System)
- Preferences (placeholder)

**Security tab** (3 cards):
- Change Password (form with validation, saves via API)
- 2FA ("Coming Soon" callout + disabled button)
- Account Security (status cards)

**Notifications tab**: 5 checkboxes, save button disabled

**Sessions tab**: 3 mock sessions + "No connected devices" callout

### 10.3 `/dashboard/company` — Company Page (`company.tsx`, 319 lines)

**Data source**: `useCompany()` → `GET /api/v1/company`

**Tabs**: General | Team | Billing

- Company info from API, quick stats (hardcoded: 20 team, 4 depts, Starter plan, 5/25 licenses)
- Upload Logo disabled, Edit Details disabled, VAT placeholder, Team empty state
- Departments (hardcoded), Invitations (2 mock), Employee overview

### 10.4 `/dashboard/subscription` — Subscription Page (`subscription.tsx`, 317 lines)

**Data source**: All hardcoded mock data

**Tabs**: Plan | Billing | History

- Professional Plan €99/month, renews Sep 1
- Upgrade/Downgrade/Cancel buttons disabled
- Feature comparison table (3 tiers, 8 features)
- Timeline (4 events), Payment methods empty, Mock invoices with download disabled

### 10.5 `/dashboard/billing` — Billing Page (`billing.tsx`, 502 lines)

**Data source**: All hardcoded mock invoices

**Tabs**: Overview | Invoices | Payment Methods | Tax Info

- Current plan, next billing, usage summary (licenses 12/25, API —, storage 2.3GB/10GB)
- 6 mock invoices (4 paid, 1 open, 1 void), filters disabled, download disabled
- Payment methods empty (Visa/MC/Amex logos), tax info form disabled

### 10.6 `/dashboard/devices` — Devices Page (`devices.tsx`, 561 lines)

See Section 15 for full detail.

### 10.7 `/dashboard/licenses` — Licenses Page (`licenses.tsx`, 377 lines)

**Data source**: `useLicenses()` → API with mock fallback + hardcoded mockDevices

- 3 mock licenses with progress bars and expiry dates
- 4 mock devices (Deactivate disabled, Device History "coming soon")
- Callouts: Offline Activation, Floating Licenses (Q4 2026)

### 10.8 `/dashboard/support` — Support Page (`support.tsx`, 376 lines)

**Data source**: Real API + mock fallback

**Tabs**: Submit Ticket | My Tickets | Knowledge Base

- Bug report + feature request forms (validated, posts to API)
- Contact info (email, phone, office, hours)
- Live Chat "Coming Soon", AI Assistant "Coming Soon"
- Ticket list with status filter dropdown
- Knowledge base (4 category cards + 4 FAQ accordion items)

### 10.9 `/dashboard/downloads` — Downloads Page (`downloads.tsx`, 119 lines)

**Data source**: Hardcoded config

- Desktop installer (version from config), system requirements
- Previous versions empty, Toolkit "Coming Soon"

### 10.10 `/dashboard/settings` — Settings Page (`settings.tsx`, 373 lines)

**Data source**: Local state only

**Tabs**: Appearance | Notifications | Language & Region | Security | Data & Privacy

- Theme selector, notification checkboxes (save disabled)
- Language (6 options), Region (5 countries), Timezone (8 options)
- Password status, 2FA "Coming Soon", Sessions link to Profile
- Data Export "Coming Soon", Delete Account disabled, API Keys "Coming Soon"

### 10.11 `/dashboard/onboarding` — Onboarding Page (`onboarding.tsx`, 444 lines)

**Data source**: All hardcoded mock data

- Circular SVG progress (1/8 = 12.5%)
- 8-step checklist (Verify email ✅, 7 pending)
- 4 tutorial cards, 3 releases, 5 best practices
- "Need help?" → Contact Support CTA

### 10.12 `/dashboard/organizations` — Organizations Page
Full CRUD via API: list, create, members, invitations, remove. Uses real queries.

### 10.13 `/dashboard/referrals` — Referrals Page
Referral stats + list via API. Full implementation.

---

## 11. Public Marketing Pages — Complete Walkthrough

### 11.1 Home Page (`home.tsx`, 564 lines)

1. **SEO Head**: Title, description, canonical URL
2. **Hero Section**:
   - Background: gradient `primary/5 → background → accent/20` + blurred roundels
   - "ARGO AI Engine" uppercase label
   - Badge: "AI-Powered Logistics" with Sparkle
   - H1 + subtitle (i18n)
   - 4 bullet points (animated staggered): Smart Route Planning, Assisted Dispatch, Automated Documents, Multi-Platform
   - 2 CTAs: [Join the Waitlist →] primary + [See Features] outline
   - Trust signal: pulsing dot + "Final productization phase"
   - **Right column**: Product mockup — browser chrome, sidebar, metric cards (24 Active Routes, 98% On Time), SVG animated route map with moving truck, dispatch table with 3 rows
3. **Stats Section**: 4 stat cards (6 Core Modules, 2 Native Apps, Web Portal, Final Stage)
4. **Features Section**: 8 feature cards (Profit Calc, Route Planning, Dispatch, Fleet, Documents, Analytics, AI Copilot, AI Workflow)
5. **Benefits Section**: 4 benefit cards (Reduce Costs, Speed, Paperwork, Scale)
6. **Workflow Section**: 4-step (Calculate → Plan → AI → Dispatch)
7. **Screenshots Section**: 3 tabs with placeholder ("Coming soon")
8. **Roadmap Section**: 3 timeline items
9. **FAQ Section**: 5 accordion items
10. **CTA Section**: "Ready to transform your logistics?"

### 11.2 Features Page (`features.tsx`, 223 lines)
Anchored sections: Route Planning, Fleet Management, Dispatch Console, Document Center, Analytics, AI & Automation, Integrations. Each: heading, problem statement, 3 feature cards, screenshot placeholder.

### 11.3 Pricing Page (`pricing.tsx`, 116 lines)
- JSON-LD structured data (Product + FAQ schema)
- "Early Access — Free" CTA, €0/month
- Feature comparison table (3 tiers), FAQ

### 11.4 Waitlist Page (`waitlist.tsx`, 374 lines)
- Full-width primary gradient hero with white text
- Form card (glass effect): company name + email, honeypot anti-spam
- Success state: referral code displayed (mono font, Key icon)
- Error states: 409 (duplicate → amber message), 429 (rate limit → toast)
- Social proof: "500+ logistics professionals joined"
- Benefits section (6 cards in grid): Early Access, AI Copilot, Workflow Automation, Notifications, Extended Trial, Reduced Price

### 11.5 Other Public Pages
About, Argo, Mission, FAQ, Contact, Privacy, Terms, Security, Community, Newsletter, Customers, Careers, Press, Brand, Enterprise, Partners, Trust, Trust Center, Changelog, Roadmap, Status, Developers, Toolkit, Products, Integrations, API Playground, Integrations Explorer, Product Tour, ROI Calculator, Route Demo, 7 Industry pages.

### 11.6 Blog
Full blog with listing (paginated), article detail, category filter, author pages. Consumes real API.

---

## 12. Auth Pages

### 12.1 Login Page (`login.tsx`, 108 lines)
- Centered card with animation | Logo "O" badge + "Operion"
- Email + Password with icons + visibility toggle
- Forgot Password link | Sign In button (loading state)
- "Don't have an account? Sign Up" | "Back to home"

### 12.2 Register Page (`register.tsx`, 154 lines)
- 6 fields: Full Name, Email, Company Name, Referral Code (from URL ?ref=), Password, Confirm Password
- Password visibility toggles on both fields
- On success: navigate to /verify-email

### 12.3 Forgot Password / Reset Password / Verify Email
Standard token-based flows.

---

## 13. Admin Pages

### 13.1 Admin Blog Editor
Full CRUD: title, slug, excerpt, content, category, tags, featured image, SEO fields, publish toggle.

### 13.2 Admin Waitlist
- Overview tab: stats (total, by status, conversion rate)
- Entries tab: paginated table with search + filters + CSV export
- Campaign tab: send email campaigns
- Referral tab: admin referral tracking

### 13.3 Ops Console (5 pages)
- Tickets, Approvals, Guardrails, Dashboards, Knowledge
- Built for internal support operations with AI-assisted workflows

---

## 14. Shared Components

### UI Components (17)
`avatar`, `badge`, `breadcrumb`, `button`, `callout`, `card`, `copy-button`, `input`, `loading-spinner`, `pagination`, `progress`, `separator`, `skeleton`, `tabs`, `tag`, `tooltip`

### Shared Feature Components (∼25)
`blog-card`, `testimonial-card`, `comparison-table`, `cta-section`, `cta-banner`, `empty-state`, `error-boundary`, `faq-accordion`, `feature-card`, `global-search` (⌘K), `hero-section`, `language-switcher`, `live-chat` (ARGO AI), `logo-cloud`, `newsletter-form`, `notification-center`, `org-switcher`, `page-header`, `pricing-card`, `release-card`, `search-input`, `section-wrapper`, `social-share`, `stat-card`, `status-badge`, `table-of-contents`, `timeline`

---

## 15. Device Management Feature — Complete Analysis

### Current State: 3 Device Concepts (not unified)

| Concept | API Endpoints | UI Location | Status |
|---------|--------------|-------------|--------|
| **Mobile Devices** | `GET/DELETE /api/v1/mobile/devices` | `/dashboard/devices` | ✅ Working (real API) |
| **License Devices** | `GET/DELETE /api/v1/licenses/:id/devices` | `/dashboard/licenses` | ⚠️ Uses mock data, deactivate disabled |
| **Auth Sessions** | `GET/DELETE /api/v1/auth/sessions` | `/dashboard/devices` (bottom) + Profile | ✅ Working (real API) |

### Mobile Devices Page (`/dashboard/devices`)

**React Query Hooks:**
```typescript
useDevices()              → GET /api/v1/mobile/devices
useDeactivateDevice()     → DELETE /api/v1/mobile/devices/:id
useSessions()             → GET /api/v1/auth/sessions
useRevokeSession()        → DELETE /api/v1/auth/sessions/:id
```

**Page structure:**
1. **Header** — "Devices" + subtitle
2. **Stats Row** — Total Devices, Active, Inactive, Platforms
3. **Platform Breakdown** — Badge pills (Android, iOS, Windows, macOS, Linux) with counts
4. **Registered Devices** (All/Active/Inactive tabs) — DeviceCards with:
   - Platform icon (Smartphone/Tablet/Monitor/Server)
   - Device name + platform label
   - Active/Inactive badge
   - User name + email
   - Last seen (relative time: "5m ago", "2h ago")
   - Registered date
   - **Deactivate button** with 2-step inline confirmation
5. **Info Callout** — Auto-registration explanation
6. **Desktop App Sessions** — SessionCards with platform icon, device name, IP, last active, **Revoke** with confirmation

**Platform detection:**
```typescript
"android"    → Smartphone + "Android" badge
"ios"/"iphone"/"ipad" → Tablet + "iOS"/"iPadOS" badge
"linux"/"server" → Server + "Linux" badge
"windows"/"macos"/"mac" → Monitor + "Windows"/"macOS" badge
```

### Device Types

```typescript
DeviceInfo { id, device_id, device_name, platform, user_email, user_name,
             is_active, last_seen, created_at }

SessionInfo { id, user_email, device_name, device_platform, ip_address,
              created_at, expires_at, last_active_at }

LicenseDevice { id, license_id?, name, os?, ip?, last_seen?, activated_at? }
```

### Known Device Management Gaps

| Gap | Priority | Detail |
|-----|----------|--------|
| License devices use mock data not API | 🔴 High | `mockDevices` hardcoded, not `useLicenseDevices()` |
| License device deactivate disabled | 🔴 High | Button has `disabled` attribute |
| No device search/filter | 🟡 Medium | Only All/Active/Inactive tabs |
| No device detail view | 🟡 Medium | Clicking a card does nothing |
| No device audit log/activity | 🟡 Medium | No event history per device |
| No remote commands | 🔴 High | No remote wipe, lock, force logout |
| No geolocation for mobile | 🟡 Medium | No last-known-location or map |
| No device health indicators | 🟢 Low | No battery, signal, app version |
| No per-device driver reassignment | 🟡 Medium | Can't change user assignment |
| No bulk operations | 🟢 Low | Can only deactivate one at a time |
| No admin cross-tenant view | 🟡 Medium | No overview of all companies' devices |
| No QR code/pairing flow | 🟡 Medium | No one-tap mobile setup |
| Missing success/error toasts | 🟢 Low | Mutations lack toast feedback |
| No staleTime on useDevices | 🟢 Low | Refetches on every mount |
| DeviceInfo type duplication | 🟢 Low | Defined in both endpoints.ts and types/index.ts |

---

## 16. UX Patterns & Design System

### Common Page Layout Pattern
```
motion.div (fade-in-up, whileInView, once)
  → h1 (text-3xl font-bold tracking-tight)
  → p (mt-2 text-muted-foreground)
  → Stats row (grid gap-4 sm:grid-cols-2 lg:grid-cols-4)
  → Tabs (default "overview")
    → Motion.div cards with staggered delays (0.05, 0.1, 0.15...)
```

### Animation System
- **Entrance**: `initial={{ opacity: 0, y: 20 }}` → `whileInView={{ opacity: 1, y: 0 }}`
- **Staggered delays**: `transition={{ delay: 0.05 * index }}`
- **Viewport**: `viewport={{ once: true }}` — fires once
- **Easing**: `ease: [0.22, 1, 0.36, 1]` (custom cubic-bezier)
- **Reduced motion**: `prefers-reduced-motion: reduce` disables all animations

### Staggered Delay Pattern (universal)
```typescript
// Card 1: delay: 0.05
// Card 2: delay: 0.1
// Card 3: delay: 0.15
// Card 4: delay: 0.2  (increments of 0.05)
```

### State Patterns
- **Loading**: Centered `LoadingSpinner size="lg"`
- **Empty**: `EmptyState` with large icon (h-16 w-16) + title + description
- **Error**: `Callout variant="danger"` with error message
- **Confirmation**: Inline toggle (button → "Are you sure?" + Confirm/Cancel)
- **Form validation**: Inline `text-xs text-destructive` errors, button disabled during `isPending`
- **Toasts**: `sonner` with rich colors for success/error

### Dashboard Card Design
```css
rounded-xl border bg-card p-6 text-card-foreground shadow-sm
hover:shadow-md  /* for interactive cards */
```

### Stats Display
```typescript
<StatCard value={String(count)} label="Label" icon={Icon} />
```
Custom cards for non-numeric stats (status indicators like green pulse dot).

---

## 17. Onboarding & User Journey

### Complete User Journey Map

```
1. LANDING PAGE (Marketing)
   ├── Hero + Features + Pricing + Waitlist
   ├── Blog + Tutorials + Docs
   │
2. WAITLIST (Lead Gen)
   ├── Company name + email form
   ├── Success → referral code displayed
   ├── Referral program (share code)
   │
3. REGISTRATION (Auth)
   ├── /register (name, email, company, password, referral code)
   ├── /verify-email (post-registration)
   │
4. LOGIN (Auth)
   ├── /login (email + password)
   ├── Forgot password → reset flow
   │
5. DASHBOARD (Post-Auth)
   ├── /dashboard (overview, stats, announcements)
   ├── /dashboard/onboarding (8-step checklist)
   │
6. SETUP PHASE
   ├── /dashboard/profile (name, email, avatar, timezone, language, theme)
   ├── /dashboard/company (company info, logo, team)
   ├── /dashboard/subscription (choose plan — coming soon)
   ├── /dashboard/organizations (invite team members)
   │
7. DEVICE SETUP
   ├── /dashboard/devices (mobile device management)
   ├── /dashboard/licenses (license management)
   ├── /dashboard/downloads (desktop app download)
   │
8. DAILY USE
   ├── /dashboard/docs (documentation)
   ├── /dashboard/support (tickets, bug reports, feature requests)
   ├── /dashboard/settings (preferences, security)
   ├── /dashboard/billing (invoices, payment methods — coming soon)
   ├── /dashboard/referrals (referral program)
   │
9. ADMIN (if admin role)
   ├── /admin/blog/editor (content management)
   ├── /admin/waitlist (lead management)
   └── /admin/ops/* (operations console)
```

### Onboarding Checklist (8 steps)

| Step | Required | Status |
|------|----------|--------|
| 1. Verify email | ✅ | Mock-completed |
| 2. Set up company profile | ✅ | Mock-pending |
| 3. Choose your plan | ✅ | Mock-pending |
| 4. Download Operion Desktop | ❌ | Mock-pending |
| 5. Create your first route | ❌ | Mock-pending |
| 6. Add team members | ❌ | Mock-pending |
| 7. Set up notifications | ❌ | Mock-pending |
| 8. Explore documentation | ❌ | Mock-pending |

**Note**: Checklist is hardcoded mock — API exists (`GET /api/v1/onboarding/checklist`) but not consumed.

---

## 18. Marketing & Conversion

### Conversion Funnel
```
Public Visit → Landing Page
  → Blog/Docs/Tutorials (SEO/content marketing)
  → Features/Pricing (consideration)
  → Waitlist Join (lead capture)
    → Referral Code (viral loop)
      → Email Verification
        → Login → Dashboard
          → Onboarding → Setup → Daily Active User
```

### Lead Capture Points
1. **Waitlist page** — primary CTA (hero, nav, mobile menu)
2. **Newsletter form** — footer on every public page
3. **Contact page** — contact form
4. **Demo pages** — Product Tour, ROI Calculator, Route Demo

### SEO
- Per-page meta tags via `react-helmet-async`
- JSON-LD structured data (Product, FAQ schemas on pricing page)
- Sitemap.xml + Robots.txt in public/
- Canonical URLs on all pages
- Blog with categories, authors, tags (SEO-optimized content)

### Trust Signals
- "500+ logistics professionals joined" (waitlist)
- "Trusted by logistics professionals" (home page)
- Service status page (pulsing green dot)
- "Final productization phase" badge
- Changelog + Roadmap (transparency)
- Customer stories + Testimonials + Partner logo cloud

### Analytics
- Page view tracking via `trackPageView(pathname)` on every route change
- Google Analytics via `VITE_GA_MEASUREMENT_ID` env var

---

## 19. Testing Infrastructure

| Test Type | Tool | Location | Scope |
|-----------|------|----------|-------|
| Unit tests | Vitest | `src/__tests__/unit/` | Config, auth, i18n, API, schemas |
| Integration tests | Vitest | `src/__tests__/integration/` | Cross-module |
| Mutation tests | Stryker | `src/__tests__/mutation/` | Test quality |
| E2E tests | Playwright | `e2e/` (14 files) | Full user flows |
| Chaos tests | Playwright | `e2e/chaos/` (5 files) | API failures, stress, offline, rate limiting, token expiry |
| Load tests | k6 | `stress/` | Performance |
| A11y tests | Playwright + axe | `e2e/accessibility.spec.ts` | WCAG compliance |
| Responsive tests | Playwright | `e2e/responsive.spec.ts` | Mobile/tablet/desktop |

### E2E Test Files
- `public-navigation.spec.ts` / `v2-public-navigation.spec.ts` / `v3-navigation.spec.ts`
- `protected-routes.spec.ts` / `auth-flow.spec.ts` / `admin-blog-flow.spec.ts`
- `accessibility.spec.ts` / `responsive.spec.ts` / `dark-mode.spec.ts` / `seo-validation.spec.ts`
- `docs-navigation.spec.ts`
- `chaos/api-failures.spec.ts` / `navigation-stress.spec.ts` / `offline.spec.ts` / `rate-limiting.spec.ts` / `token-expiry.spec.ts`

---

## 20. Complete Gaps & Improvement Areas

### 🚫 MISSING BACKEND (Stubbed in UI)

| Feature | UI Status | API Status |
|---------|-----------|------------|
| Subscription management | Full UI with mock data | No backend endpoint |
| Plan tiers (Starter/Pro/Enterprise) | Full comparison table | No backend endpoint |
| Invoices | Full list with mock data | No backend endpoint |
| Payment methods | UI placeholders | No backend endpoint |
| Tax info/VAT | UI form placeholders | No backend endpoint |
| Downloads (desktop app) | Hardcoded config | No backend endpoint |
| API key management | Disabled UI | No backend endpoint |

### 🟡 PARTIALLY BUILT

| Feature | What's Missing |
|---------|---------------|
| Device management | License devices use mock, no search/detail/bulk/audit |
| Notification preferences | UI renders but save button disabled |
| Profile avatar | Upload UI works but doesn't persist to API |
| Onboarding checklist | Hardcoded data (API available but not consumed) |
| Live chat | Placeholder UI with "Coming Soon" |
| AI Assistant | Placeholder UI with "Coming Soon" |
| 2FA | Placeholder UI with "Coming Soon" |
| Data export | Placeholder UI with "Coming Soon" |
| Delete account | Disabled destructive button |
| License management | Add/Transfer/Upgrade disabled, device list mock |

### 🟠 UX / FUNCTIONAL GAPS

| Gap | Detail |
|-----|--------|
| No return URL after login | Always redirects to /dashboard |
| No SSO/OAuth login | Email/password only |
| No "Remember me" on login | No session persistence toggle |
| No password strength indicator | On register/settings |
| Dashboard stats hardcoded | Real API exists for companies, devices, licenses but dashboard shows fake numbers |
| No pagination on device list | If >50 devices, no pagination support |
| No real-time updates | No WebSocket/polling for live changes |
| No CSV export for device list | No export capability |
| Notification bell has no dropdown | Icon exists but no functionality |
| No route-level code splitting optimization | All routes lazy-loaded but some pages are large |

### 🔴 MISSING FEATURES (Not Started)

| Feature | Impact |
|---------|--------|
| Multi-factor authentication | 🔴 High — security gap |
| SSO/Social login | 🟡 Medium — UX friction |
| Team/user management (RBAC) | 🔴 High — cannot manage users fully |
| Audit log | 🟡 Medium — no security visibility |
| Mobile app push notifications | 🟡 Medium — no real-time alerts |
| Email notification delivery | 🟢 Low — UI built, delivery backend needed |
| Billing/payment integration (Stripe) | 🔴 High — can't accept payments |
| Desktop app auto-update notifications | 🟢 Low |
| API rate limit display | 🟢 Low |
| User activity timeline | 🟢 Low |
| Dark mode image optimization | 🟢 Low |
| PWA support | 🟢 Low — no service worker |

### 🟢 WHAT WORKS WELL

- Auth (login, register, token refresh, session management)
- Blog (full CRUD with categories, authors, pagination)
- Support tickets (create + list with API)
- Company info (GET/PATCH via API)
- Organizations (full CRUD with members, invitations)
- Licenses (list via API)
- Mobile devices (list + deactivate via API)
- Desktop sessions (list + revoke via API)
- Referral program (create + track + admin)
- Waitlist (join + admin mgmt + CSV export + campaigns)
- Ops Console (tickets, approvals, guardrails, knowledge)
- i18n (6 languages)
- Theme (light/dark/system)
- Global search (⌘K)
- All loading, error, empty states
- Page animations (motion)
- SEO (meta tags, structured data, sitemap)

---

## 21. Configuration Summary

```typescript
// src/config/site.ts
siteConfig = {
  name: "Operion",
  tagline: "Logistics Operations System",
  description: "Operion is a logistics operations system — desktop and mobile apps with route planning, fleet management, dispatch, AI optimization, and document generation. All major features complete and in final productization phase.",
  url: "https://operion.com",
  ogImage: "/logo3.png",
  links: { twitter, github, linkedin }
}

apiConfig = {
  baseUrl: ""  // dev (Vite proxy) or "https://api.operionerp.xyz"
  timeout: 15000
}

downloadConfig = {
  latestVersion: "In Development",
  releaseDate: "",
  windowsInstaller: "",
  fileSize: "TBD"
}

seoConfig = {
  defaultTitle: "Operion — Logistics Operations System",
  titleTemplate: "%s — Operion",
  defaultDescription: "Operion is a logistics operations system...",
  twitterHandle: "@operion",
  siteName: "Operion",
  locale: "en_US"
}
```

---

## 22. Environment & Deployment

- **Dev server**: Port 3000
- **Vite proxy**: `/api` → `https://api.operionerp.xyz` (avoids CORS in dev)
- **Environment variables**: `.env` with `VITE_API_URL`, `VITE_GA_MEASUREMENT_ID`
- **Production**: `VITE_API_URL` set for direct API calls
- **Netlify**: `public/_redirects` for SPA fallback routing
- **Cloudflare**: API hosted on Cloudflare Workers (Observability tooling available)
- **TypeScript**: Project references pattern (app + node configs)

---

## File Index (Key Source Files)

| File | Lines | Purpose |
|------|-------|---------|
| `src/App.tsx` | 807 | Route definitions (all pages) |
| `src/components/layout/app-shell.tsx` | 775 | Public + Dashboard layouts |
| `src/api/endpoints.ts` | 821 | All API endpoint definitions |
| `src/api/client.ts` | 144 | Axios instance, interceptors, CSRF, token refresh |
| `src/services/queries.ts` | 460 | React Query hooks |
| `src/types/index.ts` | 683 | All TypeScript interfaces |
| `src/contexts/auth-provider.tsx` | 149 | Auth state management |
| `src/contexts/theme-provider.tsx` | 64 | Theme state management |
| `src/i18n/locale-context.tsx` | 69 | i18n + locale switching |
| `src/config/navigation.ts` | 144 | Nav data structures |
| `src/config/site.ts` | 148 | App configuration |
| `src/components/auth/protected-route.tsx` | 33 | Route guards |
| `src/services/jwt.ts` | 38 | JWT client decode |
| `src/styles/globals.css` | 159 | Tailwind + CSS variables |
| `src/pages/dashboard/devices.tsx` | 561 | Device management page |
| `src/pages/dashboard/licenses.tsx` | 377 | License management page |
| `src/pages/dashboard/dashboard.tsx` | 423 | Main dashboard |
| `src/pages/dashboard/profile.tsx` | 556 | User profile |
| `src/pages/dashboard/company.tsx` | 319 | Company info |
| `src/pages/dashboard/subscription.tsx` | 317 | Subscription |
| `src/pages/dashboard/billing.tsx` | 502 | Billing |
| `src/pages/dashboard/support.tsx` | 376 | Support tickets |
| `src/pages/dashboard/onboarding.tsx` | 444 | Onboarding checklist |
| `src/pages/dashboard/settings.tsx` | 373 | Settings |
| `src/pages/dashboard/downloads.tsx` | 119 | Downloads |
| `src/pages/public/home.tsx` | 564 | Marketing homepage |
| `src/pages/public/features.tsx` | 223 | Features page |
| `src/pages/public/pricing.tsx` | 116 | Pricing page |
| `src/pages/public/waitlist.tsx` | 374 | Waitlist signup |
| `src/pages/auth/login.tsx` | 108 | Login |
| `src/pages/auth/register.tsx` | 154 | Registration |

---

*End of spec dump — 22 sections covering every aspect of the Operion website.*
