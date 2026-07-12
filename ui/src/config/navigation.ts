import { LayoutDashboard, BarChart3, Users, Settings, FileText, HelpCircle } from "lucide-react"

export interface NavItem {
  label: string
  href: string
  icon?: React.ComponentType<{ className?: string }>
  external?: boolean
}

export const publicNavItems: NavItem[] = [
  { label: "Features", href: "/features", icon: LayoutDashboard },
  { label: "Pricing", href: "/pricing", icon: BarChart3 },
  { label: "About", href: "/about", icon: Users },
  { label: "Docs", href: "/docs", icon: FileText, external: true },
  { label: "Support", href: "/support", icon: HelpCircle },
]

export const authNavItems: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Team", href: "/team", icon: Users },
  { label: "Settings", href: "/settings", icon: Settings },
]
