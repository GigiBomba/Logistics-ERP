import {
  BookOpen,
  Building2,
  CreditCard,
  Download,
  LayoutDashboard,
  LifeBuoy,
  Settings,
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
  { label: "Features", href: "/features" },
  { label: "Products", href: "/products" },
  { label: "Product Tour", href: "/product-tour" },
  { label: "Integrations", href: "/integrations" },
  { label: "Pricing", href: "/pricing" },
  { label: "ROI Calculator", href: "/roi-calculator" },
  { label: "Route Demo", href: "/route-demo" },
  { label: "Download", href: "/download" },
  { label: "Industries", href: "/industries/transport" },
  { label: "Docs", href: "/docs" },
  { label: "Blog", href: "/blog" },
  { label: "Roadmap", href: "/roadmap" },
  { label: "Changelog", href: "/changelog" },
  { label: "About", href: "/about" },
  { label: "Contact", href: "/contact" },
]

export const footerNavSections: NavSection[] = [
  {
    title: "Product",
    items: [
      { label: "Features", href: "/features" },
      { label: "Products", href: "/products" },
      { label: "Pricing", href: "/pricing" },
      { label: "Integrations Explorer", href: "/integrations-explorer" },
      { label: "API Playground", href: "/api-playground" },
      { label: "Download", href: "/download" },
      { label: "Roadmap", href: "/roadmap" },
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
      { label: "Contact", href: "/contact" },
      { label: "Trust Center", href: "/trust-center" },
      { label: "Waitlist", href: "/waitlist" },
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
    ],
  },
]

export const dashboardNavItems: NavItem[] = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { label: "Profile", href: "/dashboard/profile", icon: User },
  { label: "Company", href: "/dashboard/company", icon: Building2 },
  { label: "Subscription", href: "/dashboard/subscription", icon: CreditCard },
  { label: "Downloads", href: "/dashboard/downloads", icon: Download },
  { label: "Documentation", href: "/dashboard/docs", icon: BookOpen },
  { label: "Support", href: "/dashboard/support", icon: LifeBuoy },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
]
