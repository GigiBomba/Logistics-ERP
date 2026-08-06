import { useState, useRef, useEffect } from "react"
import { Link, useLocation, Outlet } from "react-router"
import { useQueryClient } from "@tanstack/react-query"
import { motion, AnimatePresence } from "motion/react"
import { Menu, X, Sun, Moon, Monitor, Search, LogOut, Command, ChevronDown, MessageCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn, getInitials } from "@/lib/utils"
import { useTheme } from "@/contexts/theme-provider"
import { useAuth } from "@/contexts/auth-provider"
import { publicNavItems, footerNavSections, dashboardNavItems } from "@/config/navigation"
import { siteConfig } from "@/config/site"
import { getRouteLayout } from "@/config/route-layouts"
import { GlobalSearch } from "@/components/shared/global-search"
import { SupportModal } from "@/components/shared/support-modal"
import { NewsletterForm } from "@/components/shared/newsletter-form"
import { JsonLd, organizationSchema } from "@/components/seo/structured-data"
import { OrgSwitcher } from "@/components/shared/org-switcher"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { useOrganizations, usePortalNotifications, useMarkNotificationRead, useMarkAllRead } from "@/services/queries"
import { NotificationCenter } from "@/components/shared/notification-center"
import { useLocale } from "@/i18n/locale-context"
import { LanguageSwitcher } from "@/components/shared/language-switcher"
import { LiveChat } from "@/components/shared/live-chat"
import { TrialBanner } from "@/components/shared/trial-banner"
import type { NavItem } from "@/config/navigation"
import { trackCTAClick } from "@/services/analytics"

// Translation key helpers for nav items
const publicNavKeyMap: Record<string, string> = {
  "/": "nav.home",
  "/features": "nav.features",
  "/pricing": "nav.pricing",
  "/download": "nav.download",
  "/roadmap": "nav.roadmap",
  "/about": "nav.about",
  "/blog": "nav.blog",
  "/changelog": "nav.changelog",
  "/contact": "nav.contact",
  "/docs": "nav.docs",
  "/industries/transport": "nav.industries",
  "/integrations": "nav.integrations",
  "/product-tour": "nav.productTour",
  "/products": "nav.products",
  "/roi-calculator": "nav.roiCalculator",
  "/route-demo": "nav.routeDemo",
  "/argo": "nav.argo",
}

const dashboardNavKeyMap: Record<string, string> = {
  "/dashboard": "dashboard.overview",
  "/dashboard/profile": "common.profile",
  "/dashboard/company": "dashboard.company",
  "/dashboard/subscription": "dashboard.subscription",
  "/dashboard/referrals": "referral.title",
  "/dashboard/downloads": "common.downloads",
  "/dashboard/docs": "common.documentation",
  "/dashboard/support": "common.support",
  "/dashboard/settings": "common.settings",
}

const footerSectionKeyMap: Record<string, string> = {
  "Product": "footer.product",
  "Company": "footer.company",
  "Resources": "footer.resources",
  "Legal": "footer.legal",
  "Solutions": "nav.solutions",
}

const footerLinkKeyMap: Record<string, string> = {
  "/about": "nav.about",
  "/api-playground": "nav.apiPlayground",
  "/blog": "nav.blog",
  "/changelog": "nav.changelog",
  "/contact": "nav.contact",
  "/docs": "common.documentation",
  "/download": "nav.download",
  "/enterprise": "nav.enterprise",
  "/faq": "nav.faq",
  "/features": "nav.features",
  "/industries/fleet": "nav.fleet",
  "/industries/freight": "nav.freight",
  "/industries/owner-operators": "nav.ownerOps",
  "/industries/transport": "nav.transport",
  "/integrations-explorer": "nav.integrationsExplorer",
  "/mission": "nav.mission",
  "/pricing": "nav.pricing",
  "/privacy": "footer.privacy",
  "/product-tour": "nav.productTour",
  "/products": "nav.products",
  "/roadmap": "nav.roadmap",
  "/roi-calculator": "nav.roiCalculator",
  "/route-demo": "nav.routeDemo",
  "/support": "common.support",
  "/terms": "footer.terms",
  "/trust-center": "nav.trustCenter",
  "/waitlist": "nav.waitlist",
}

// ─── Dropdown Nav Component ──────────────────────────────────

function DropdownNavItem({ item }: { item: (typeof publicNavItems)[number] }) {
  const { t } = useLocale()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const closeTimer = useRef<ReturnType<typeof setTimeout>>(null)

  // Label for dropdown trigger — use a direct label map (not href-based, since parent tabs share hrefs with children)
  const triggerLabelMap: Record<string, string> = {
    "/features": "nav.product",
  }
  const triggerLabel = t(triggerLabelMap[item.href] ?? item.label)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [])

  if (!item.children) return null

  const isActive = item.children.some(
    (c) => location.pathname === c.href || (c.href !== "/" && location.pathname.startsWith(c.href))
  )

  function handleMouseEnter() {
    if (closeTimer.current) { clearTimeout(closeTimer.current); closeTimer.current = null }
    setOpen(true)
  }

  function handleMouseLeave() {
    closeTimer.current = setTimeout(() => setOpen(false), 150)
  }

  return (
    <div ref={ref} className="relative" onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave}>
      <Link
        to={item.href}
        className={cn(
          "px-3 py-2 rounded-md text-sm font-medium transition-colors hover:text-primary inline-flex items-center gap-1",
          isActive ? "text-primary bg-accent" : "text-muted-foreground"
        )}
      >
        {triggerLabel}
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </Link>
      {open && (
        <div className="absolute top-full left-0 pt-1 z-50">
          <div className="w-48 rounded-lg border bg-popover shadow-lg py-1">
            {item.children.map((child) => (
              <Link
                key={child.href}
                to={child.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "block px-4 py-2 text-sm transition-colors hover:bg-accent",
                  location.pathname === child.href
                    ? "text-primary font-medium"
                    : "text-muted-foreground"
                )}
              >
                {t(publicNavKeyMap[child.href] ?? child.label)}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Dashboard Layout ──────────────────────────────────────────

function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [activeOrgId, setActiveOrgId] = useState<string>("")
  const { theme, setTheme } = useTheme()
  const { user, logout } = useAuth()
  const { t } = useLocale()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { data: organizations = [] } = useOrganizations()
  const { data: notifications = [], isLoading: notificationsLoading } = usePortalNotifications()
  const markReadMutation = useMarkNotificationRead()
  const markAllReadMutation = useMarkAllRead()

  const themeIcons = {
    light: <Sun className="h-4 w-4" />,
    dark: <Moon className="h-4 w-4" />,
    system: <Monitor className="h-4 w-4" />,
  }

  function cycleTheme() {
    const next: Record<string, "dark" | "light" | "system"> = {
      light: "dark",
      dark: "system",
      system: "light",
    }
    setTheme(next[theme])
  }

  function handleLogout() {
    logout()
    // No explicit navigate here: ProtectedRoute deterministically redirects
    // unauthenticated users to /login?returnUrl=<current> once `user` clears.
    // A manual navigate("/") here races that redirect (non-deterministic end URL).
  }

  function handleSwitchOrg(orgId: string) {
    setActiveOrgId(orgId)
    // Invalidate org-scoped queries so the new organization's data is refetched.
    queryClient.invalidateQueries({ queryKey: ["devices"] })
    queryClient.invalidateQueries({ queryKey: ["licenses"] })
    queryClient.invalidateQueries({ queryKey: ["subscription"] })
    queryClient.invalidateQueries({ queryKey: ["company"] })
    queryClient.invalidateQueries({ queryKey: ["notifications"] })
  }

  const isActiveRoute = (href: string) => {
    if (href === "/dashboard") return location.pathname === "/dashboard"
    return location.pathname.startsWith(href)
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[280px] flex-col border-r bg-background transition-transform duration-200 ease-in-out",
          "md:static md:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Sidebar header with logo */}
        <div className="flex h-14 items-center justify-between border-b px-4">
          <Link to="/dashboard" className="flex items-center gap-2 font-bold text-lg tracking-tight">
            <img src="/logo3.png" alt={siteConfig.name} className="h-14 w-auto object-contain" />
            <span>{siteConfig.name}</span>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent md:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* User info */}
        <div className="border-b px-4 py-4">
          <div className="flex items-center gap-3">
            <Avatar size="sm">
              {user?.avatar_url ? (
                <AvatarImage src={user.avatar_url} alt={user.name} />
              ) : null}
              <AvatarFallback>{user ? getInitials(user.name ?? "") : "U"}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium truncate">{user?.name ?? "User"}</p>
              <p className="text-xs text-muted-foreground truncate">{user?.email ?? ""}</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          <div className="space-y-1">
            {dashboardNavItems.map((item: NavItem) => {
              const Icon = item.icon
              const active = isActiveRoute(item.href)
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  {Icon && <Icon className="h-4 w-4 shrink-0" />}
                  <span>{t(dashboardNavKeyMap[item.href] ?? item.label)}</span>
                </Link>
              )
            })}
          </div>
        </nav>

        {/* Org switcher */}
        <div className="border-t px-3 py-3">
          <OrgSwitcher
            organizations={organizations as unknown as import("@/types").Organization[]}
            activeOrgId={activeOrgId || String(organizations[0]?.id || "")}
            onSwitch={handleSwitchOrg}
          />
        </div>

        {/* Logout */}
        <div className="border-t px-3 py-3">
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            <span>{t("common.signOut")}</span>
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Dashboard navbar */}
        <header className="sticky top-0 z-20 flex h-14 items-center gap-4 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4">
          {/* Mobile sidebar toggle */}
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label={t("common.toggleMenu")}
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent md:hidden"
          >
            <Menu className="h-4 w-4" />
          </button>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Search trigger */}
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 rounded-lg border border-input bg-background px-3 py-1.5 text-sm text-muted-foreground shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground max-w-48 min-w-[120px]"
            aria-label={t("common.openSearch")}
          >
            <Search className="h-4 w-4 shrink-0" />
            <span className="hidden md:inline flex-1 text-left">{t("common.search")}</span>
            <kbd className="hidden lg:inline-flex items-center gap-0.5 rounded border border-border/50 bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground/70">
              <Command className="h-2.5 w-2.5" />
              <span>K</span>
            </kbd>
          </button>

          {/* Theme toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={cycleTheme}
            aria-label={t("common.toggleTheme")}
          >
            {themeIcons[theme]}
          </Button>

          {/* Language switcher */}
          <LanguageSwitcher />

          {/* Live chat */}
          <LiveChat />

          {/* Notification bell */}
          <NotificationCenter
            notifications={notifications}
            unreadCount={notifications.filter((n) => !n.read).length}
            onMarkRead={(id) => markReadMutation.mutate(id)}
            onMarkAllRead={() => markAllReadMutation.mutate()}
            loading={notificationsLoading}
          />

          {/* User menu */}
          <div className="relative">
            <button
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              aria-label={user?.name ?? t("common.signOut")}
              aria-expanded={userMenuOpen}
              className="flex items-center gap-2 rounded-lg p-1 transition-colors hover:bg-accent"
            >
              <Avatar size="sm">
                {user?.avatar_url ? (
                  <AvatarImage src={user.avatar_url} alt={user?.name ?? "User"} />
                ) : null}
                <AvatarFallback>{user ? getInitials(user.name ?? "") : "U"}</AvatarFallback>
              </Avatar>
            </button>

            <AnimatePresence>
              {userMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setUserMenuOpen(false)}
                  />
                  <motion.div
                    initial={{ opacity: 0, y: -4, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -4, scale: 0.96 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 top-full z-50 mt-1.5 w-48 overflow-hidden rounded-xl border bg-popover shadow-lg"
                  >
                    <div className="p-1.5">
                      <Link
                        to="/dashboard/profile"
                        onClick={() => setUserMenuOpen(false)}
                        className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm transition-colors hover:bg-accent"
                      >
                        {t("common.profile")}
                      </Link>
                      <Link
                        to="/dashboard/settings"
                        onClick={() => setUserMenuOpen(false)}
                        className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm transition-colors hover:bg-accent"
                      >
                        {t("common.settings")}
                      </Link>
                    </div>
                    <div className="border-t p-1.5">
                      <button
                        onClick={() => {
                          setUserMenuOpen(false)
                          handleLogout()
                        }}
                        className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm transition-colors hover:bg-destructive/10 hover:text-destructive"
                      >
                        <LogOut className="h-4 w-4" />
                        {t("common.signOut")}
                      </button>
                    </div>
                  </motion.div>
                </>
              )}
            </AnimatePresence>
          </div>
        </header>

        {/* Dashboard content */}
        <main className="flex-1 p-6">
          <TrialBanner />
          <Outlet />
        </main>
      </div>

      {/* Global Search */}
      <GlobalSearch open={searchOpen} onOpenChange={setSearchOpen} />
    </div>
  )
}

// ─── Public Layout ─────────────────────────────────────────────

function PublicLayout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [supportModalOpen, setSupportModalOpen] = useState(false)
  const { theme, setTheme } = useTheme()
  const { user, isAuthenticated } = useAuth()
  const { t } = useLocale()
  const location = useLocation()

  const themeIcons = {
    light: <Sun className="h-4 w-4" />,
    dark: <Moon className="h-4 w-4" />,
    system: <Monitor className="h-4 w-4" />,
  }

  function cycleTheme() {
    const next: Record<string, "dark" | "light" | "system"> = {
      light: "dark",
      dark: "system",
      system: "light",
    }
    setTheme(next[theme])
  }

  return (
    <div className="flex min-h-screen flex-col">
      {/* Sitewide Organization Schema */}
      <JsonLd data={organizationSchema()} />

      {/* Navbar */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container-wide flex h-16 items-center gap-6">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 font-bold text-xl tracking-tight shrink-0">
            <img src="/logo3.png" alt={siteConfig.name} className="h-14 w-auto object-contain" />
            <span>{siteConfig.name}</span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {publicNavItems.map((item) =>
              item.children ? (
                <DropdownNavItem key={item.href} item={item} />
              ) : (
                <Link
                  key={item.href}
                  to={item.href}
                  className={cn(
                    "px-3 py-2 rounded-md text-sm font-medium transition-colors hover:text-primary",
                    location.pathname === item.href
                      ? "text-primary bg-accent"
                      : "text-muted-foreground"
                  )}
                >
                  {t(publicNavKeyMap[item.href] ?? item.label)}
                </Link>
              )
            )}
          </nav>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Desktop actions */}
          <div className="hidden md:flex items-center gap-2">
            {/* Search trigger */}
            <button
              onClick={() => setSearchOpen(true)}
              className="flex items-center gap-2 rounded-lg border border-input bg-background px-3 py-1.5 text-sm text-muted-foreground shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground max-w-48 min-w-[120px]"
              aria-label={t("common.openSearch")}
            >
              <Search className="h-4 w-4 shrink-0" />
              <span className="hidden md:inline flex-1 text-left">{t("common.search")}</span>
              <kbd className="hidden lg:inline-flex items-center gap-0.5 rounded border border-border/50 bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground/70">
                <Command className="h-2.5 w-2.5" />
                <span>K</span>
              </kbd>
            </button>

            {/* Support chat */}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSupportModalOpen(true)}
              className="relative"
              aria-label={t("support.liveChat")}
            >
              <MessageCircle className="h-[18px] w-[18px]" />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              onClick={cycleTheme}
              aria-label={t("common.toggleTheme")}
            >
              {themeIcons[theme]}
            </Button>

            <LanguageSwitcher />

            {isAuthenticated ? (
              <Link
                to="/dashboard"
                className="flex items-center gap-2 rounded-lg p-1 transition-colors hover:bg-accent"
                aria-label={t("common.dashboard")}
              >
                <Avatar size="sm" className="ring-1 ring-border">
                  {user?.avatar_url ? (
                    <AvatarImage src={user.avatar_url} alt={user?.name ?? ""} />
                  ) : null}
                  <AvatarFallback className="text-xs">
                    {user ? getInitials(user.name ?? user.email ?? "") : "U"}
                  </AvatarFallback>
                </Avatar>
                <span className="text-sm font-medium text-foreground hidden lg:inline">{t("common.dashboard")}</span>
              </Link>
            ) : (
              <>
                <Button variant="ghost" asChild>
                  <Link to="/login">{t("common.signIn")}</Link>
                </Button>
                <Button asChild>
                  <Link to="/waitlist" onClick={() => trackCTAClick("navbar_desktop", location.pathname)}>{t("nav.waitlist")}</Link>
                </Button>
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="flex md:hidden items-center gap-2">
            {/* Support chat */}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSupportModalOpen(true)}
              aria-label={t("support.liveChat")}
            >
              <MessageCircle className="h-[18px] w-[18px]" />
            </Button>
            <Button variant="ghost" size="icon" onClick={cycleTheme} aria-label={t("common.toggleTheme")}>
              {themeIcons[theme]}
            </Button>
            <LanguageSwitcher />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label={t("common.toggleMenu")}
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </div>
        </div>

        {/* Mobile menu */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="border-t md:hidden overflow-hidden"
            >
              <nav className="container-wide flex flex-col gap-1 py-4">
                {publicNavItems.map((item) => {
                  // Use same label overrides as desktop DropdownNavItem for consistency
                  const mobileParentLabelMap: Record<string, string> = {
                    "/features": "nav.product",
                    "/roi-calculator": "nav.tools",
                    "/about": "nav.about",
                  }
                  const parentLabel = mobileParentLabelMap[item.href] ?? publicNavKeyMap[item.href] ?? item.label
                  if (item.children) {
                    return (
                      <div key={item.href}>
                        <div className="px-3 py-2 text-sm font-medium text-muted-foreground">
                          {t(parentLabel)}
                        </div>
                        {item.children.map((child) => (
                          <Link
                            key={child.href}
                            to={child.href}
                            onClick={() => setMobileMenuOpen(false)}
                            className={cn(
                              "block pl-6 pr-3 py-2 text-sm rounded-md transition-colors",
                              location.pathname === child.href
                                ? "text-primary bg-accent"
                                : "text-muted-foreground hover:text-primary"
                            )}
                          >
                            {t(publicNavKeyMap[child.href] ?? child.label)}
                          </Link>
                        ))}
                      </div>
                    )
                  }
                  return (
                    <Link
                      key={item.href}
                      to={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={cn(
                        "px-3 py-2 rounded-md text-sm font-medium transition-colors",
                        location.pathname === item.href
                          ? "text-primary bg-accent"
                          : "text-muted-foreground hover:text-primary"
                      )}
                    >
                      {t(publicNavKeyMap[item.href] ?? item.label)}
                    </Link>
                  )
                })}
                <div className="mt-2 flex flex-col gap-2 border-t pt-4">
                  {isAuthenticated ? (
                    <>
                      <Link
                        to="/dashboard"
                        onClick={() => setMobileMenuOpen(false)}
                        className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:bg-accent"
                      >
                        <Avatar size="sm">
                          {user?.avatar_url ? (
                            <AvatarImage src={user.avatar_url} alt={user?.name ?? ""} />
                          ) : null}
                          <AvatarFallback className="text-xs">
                            {user ? getInitials(user.name ?? user.email ?? "") : "U"}
                          </AvatarFallback>
                        </Avatar>
                        <span>{t("common.dashboard")}</span>
                      </Link>
                    </>
                  ) : (
                    <>
                      <Button asChild className="w-full">
                        <Link to="/waitlist" onClick={() => { setMobileMenuOpen(false); trackCTAClick("navbar_mobile", location.pathname) }}>{t("nav.waitlist")}</Link>
                      </Button>
                      <Button variant="ghost" asChild className="w-full">
                        <Link to="/login" onClick={() => setMobileMenuOpen(false)}>{t("common.signIn")}</Link>
                      </Button>
                    </>
                  )}
                </div>
              </nav>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* Main content */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t bg-muted/30">
        <div className="container-wide py-12 md:py-16">
          <div className="grid gap-8 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-5">
            <div className="sm:col-span-2 md:col-span-1">
              <Link to="/" className="flex items-center gap-2 font-bold text-lg">
                <img src="/logo3.png" alt={siteConfig.name} className="h-10 w-auto object-contain" />
                {siteConfig.name}
              </Link>
              <p className="mt-3 text-sm text-muted-foreground max-w-xs">
                {t("footer.tagline")}
              </p>
            </div>
            {footerNavSections.map((section) => (
              <div key={section.title}>
                <h3 className="font-semibold text-sm">{t(footerSectionKeyMap[section.title ?? ""] ?? section.title ?? "")}</h3>
                <ul className="mt-3 space-y-2">
                  {section.items.map((link) => (
                    <li key={link.href}>
                      <Link
                        to={link.href}
                        className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {t(footerLinkKeyMap[link.href] ?? link.label)}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Newsletter + bottom bar */}
          <div className="mt-12 border-t pt-8">
            <div className="mb-8 max-w-sm">
              <NewsletterForm variant="footer" />
            </div>
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <Link
                  to="/status"
                  className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                  </span>
                  {t("footer.status")}
                </Link>
                <span className="text-muted-foreground/30 hidden sm:inline" aria-hidden="true">|</span>
                <p className="text-sm text-muted-foreground">
                  &copy; {new Date().getFullYear()} {siteConfig.name}. {t("footer.copyright")}
                </p>
              </div>
              <div className="flex items-center gap-4">
                <Link to="/privacy" className="text-sm text-muted-foreground hover:text-foreground">
                  {t("footer.privacy")}
                </Link>
                <Link to="/terms" className="text-sm text-muted-foreground hover:text-foreground">
                  {t("footer.terms")}
                </Link>
              </div>
            </div>
          </div>
        </div>
      </footer>

      {/* Global Search */}
      <GlobalSearch open={searchOpen} onOpenChange={setSearchOpen} />
      <SupportModal open={supportModalOpen} onOpenChange={setSupportModalOpen} />
    </div>
  )
}

// ─── AppShell Router ───────────────────────────────────────────

export function AppShell() {
  const location = useLocation()
  const layout = getRouteLayout(location.pathname)

  if (layout === "dashboard") {
    return <DashboardLayout />
  }

  return <PublicLayout />
}
