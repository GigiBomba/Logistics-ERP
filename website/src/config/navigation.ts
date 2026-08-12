import {
  BarChart3,
  BookOpen,
  Building2,
  ClipboardList,
  CreditCard,
  Download,
  Gift,
  LayoutDashboard,
  LifeBuoy,
  Monitor,
  Settings,
  Shield,
  Smartphone,
  User,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

export interface NavItem {
  label: string
  href: string
  icon?: LucideIcon
  external?: boolean
  requiresAuth?: boolean
  children?: NavItem[]
}

export interface NavSection {
  title?: string
  items: NavItem[]
}

export const publicNavItems: NavItem[] = [
  { label: "Home", href: "/" },
  {
    label: "Product",
    href: "/features",
    children: [
      { label: "Features", href: "/features" },
      { label: "Argo", href: "/argo" },
      { label: "Product Tour", href: "/product-tour" },
      { label: "Integrations", href: "/integrations" },
      { label: "Ecosystem", href: "/products" },
    ],
  },
  { label: "Pricing", href: "/pricing" },
  {
    label: "Tools",
    href: "/roi-calculator",
    children: [
      { label: "ROI Calculator", href: "/roi-calculator" },
      { label: "Route Demo", href: "/route-demo" },
    ],
  },
  { label: "Download", href: "/download" },
  { label: "Industries", href: "/industries/transport" },
  { label: "Docs", href: "/docs" },
  { label: "Blog", href: "/blog" },
  {
    label: "About",
    href: "/about",
    children: [
      { label: "About", href: "/about" },
      { label: "Roadmap", href: "/roadmap" },
      { label: "Changelog", href: "/changelog" },
    ],
  },
  { label: "Contact", href: "/contact" },
]

export const footerNavSections: NavSection[] = [
  {
    title: "Product",
    items: [
      { label: "Features", href: "/features" },
      { label: "Argo", href: "/argo" },
      { label: "ARGO", href: "/features#ai" },
      { label: "Products", href: "/products" },
      { label: "Pricing", href: "/pricing" },
      { label: "Integrations Explorer", href: "/integrations-explorer" },
      { label: "API Playground", href: "/api-playground" },
      { label: "Download", href: "/download" },
      { label: "Roadmap", href: "/roadmap" },
      { label: "Waitlist", href: "/waitlist" },
    ],
  },
  {
    title: "Solutions",
    items: [
      { label: "Transport", href: "/industries/transport" },
      { label: "Freight", href: "/industries/freight" },
      { label: "Fleet", href: "/industries/fleet" },
      { label: "Owner Operators", href: "/industries/owner-operators" },
      { label: "Enterprise", href: "/enterprise" },
    ],
  },
  {
    title: "Company",
    items: [
      { label: "About", href: "/about" },
      { label: "Mission", href: "/mission" },
      { label: "Waitlist", href: "/waitlist" },
      { label: "Contact", href: "/contact" },
      { label: "Trust Center", href: "/trust-center" },
    ],
  },
  {
    title: "Resources",
    items: [
      { label: "Documentation", href: "/docs" },
      { label: "Product Tour", href: "/product-tour" },
      { label: "ROI Calculator", href: "/roi-calculator" },
      { label: "Route Demo", href: "/route-demo" },
      { label: "Blog", href: "/blog" },
      { label: "FAQ", href: "/faq" },
      { label: "Support", href: "/support" },
      { label: "Changelog", href: "/changelog" },
    ],
  },
  {
    title: "Legal",
    items: [
      { label: "Privacy Policy", href: "/privacy" },
      { label: "Terms of Service", href: "/terms" },
      { label: "Cookie Policy", href: "/cookie-policy" },
      { label: "Accessibility", href: "/accessibility-statement" },
    ],
  },
]

export const dashboardNavItems: NavItem[] = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { label: "Analytics", href: "/dashboard/analytics", icon: BarChart3 },
  { label: "Profile", href: "/dashboard/profile", icon: User },
  { label: "Company", href: "/dashboard/company", icon: Building2 },
  { label: "Subscription", href: "/dashboard/subscription", icon: CreditCard },
  { label: "Devices", href: "/dashboard/devices", icon: Smartphone },
  { label: "Referrals", href: "/dashboard/referrals", icon: Gift },
  { label: "Downloads", href: "/dashboard/downloads", icon: Download },
  { label: "Documentation", href: "/dashboard/docs", icon: BookOpen },
  { label: "Support", href: "/dashboard/support", icon: LifeBuoy },
  { label: "All Devices", href: "/admin/devices", icon: Monitor },
  { label: "Support Ops", href: "/admin/ops", icon: Shield, children: [
    { label: "Tickets", href: "/admin/ops/tickets" },
    { label: "Approvals", href: "/admin/ops/approvals" },
    { label: "Guardrails", href: "/admin/ops/guardrails" },
    { label: "Dashboards", href: "/admin/ops/dashboards" },
    { label: "Knowledge", href: "/admin/ops/knowledge" },
  ]},
  { label: "Activity Log", href: "/dashboard/activity", icon: ClipboardList },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
]
