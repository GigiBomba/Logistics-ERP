import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, Outlet, useLocation } from "react-router"
import { Menu, X, BookOpen, MapPin, Radio, Send, Scan, BarChart3, Users, FileText, ChevronLeft, ChevronDown, Clock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { SearchInput } from "@/components/shared/search-input"
import { cn } from "@/lib/utils"
import { useLocale } from "@/i18n/locale-context"

const sidebarItems = [
  { icon: BookOpen, labelKey: "docs.sidebar.gettingStarted", href: "/docs/getting-started" },
  { icon: MapPin, labelKey: "docs.sidebar.routePlanning", href: "/docs/route-planning" },
  { icon: Radio, labelKey: "docs.sidebar.fleetTracking", href: "/docs/fleet-tracking" },
  { icon: Send, labelKey: "docs.sidebar.dispatch", href: "/docs/dispatch" },
  { icon: Scan, labelKey: "docs.sidebar.ocrDocuments", href: "/docs/ocr" },
  { icon: BarChart3, labelKey: "docs.sidebar.analytics", href: "/docs/analytics" },
  { icon: Users, labelKey: "docs.sidebar.administration", href: "/docs/administration" },
  { icon: FileText, labelKey: "docs.sidebar.apiReference", href: "/docs/api" },
]

export default function DocsLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [versionOpen, setVersionOpen] = useState(false)
const { t } = useLocale()
  const location = useLocation()

  const filteredItems = searchQuery
    ? sidebarItems.filter((item) =>
        t(item.labelKey).toLowerCase().includes(searchQuery.toLowerCase())
      )
    : sidebarItems

  return (
    <>
      <Helmet><title>{t("docs.pageTitle")}</title></Helmet>
      <div className="flex min-h-[80vh]">
        {/* Mobile sidebar toggle */}
        <div className="lg:hidden fixed top-16 left-4 z-40">
          <Button variant="outline" size="sm" onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            <span className="ml-2">{t("docs.menu")}</span>
          </Button>
        </div>

        {/* Sidebar backdrop */}
        {sidebarOpen && (
          <div className="fixed inset-0 z-30 bg-black/20 lg:hidden" onClick={() => setSidebarOpen(false)} />
        )}

        {/* Sidebar */}
        <aside
          className={cn(
            "fixed top-16 left-0 z-30 h-[calc(100vh-4rem)] w-64 border-r bg-background transition-transform lg:sticky lg:translate-x-0 flex flex-col",
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          )}
        >
          {/* Header */}
          <div className="p-4 border-b">
            <Link to="/docs" className="flex items-center gap-2" onClick={() => setSidebarOpen(false)}>
              <BookOpen className="h-5 w-5 text-primary" />
              <span className="font-semibold">{t("docs.title")}</span>
            </Link>
          </div>

          {/* Search */}
          <div className="px-4 pt-3 pb-1">
            <SearchInput
              placeholder={t("common.filterSections")}
              value={searchQuery}
              onChange={setSearchQuery}
              onClear={() => setSearchQuery("")}
            />
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5">
            {filteredItems.length > 0 ? (
              filteredItems.map((item) => (
                <Link
                  key={item.href}
                  to={item.href}
                  onClick={() => { setSidebarOpen(false); setSearchQuery("") }}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent group",
                    location.pathname === item.href || location.pathname.startsWith(item.href + "/")
                      ? "bg-accent text-accent-foreground font-medium"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <item.icon className={cn(
                    "h-4 w-4 shrink-0 transition-colors",
                    location.pathname === item.href || location.pathname.startsWith(item.href + "/")
                      ? "text-primary"
                      : "text-muted-foreground group-hover:text-foreground"
                  )} />
                  {t(item.labelKey)}
                </Link>
              ))
            ) : (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground">
                {t("docs.noSectionsFound")}
              </p>
            )}
          </nav>

          {/* Bottom section */}
          <div className="p-4 border-t space-y-3">
            {/* "On this page" placeholder */}
            <div>
              <div className="flex items-center gap-1.5 mb-1.5">
                <Clock className="h-3 w-3 text-muted-foreground" />
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {t("docs.onThisPage")}
                </span>
              </div>
              <p className="text-[11px] text-foreground/80 leading-relaxed">
                {t("docs.onThisPageDesc")}
              </p>
            </div>

            {/* Version selector */}
            <div className="relative">
              <button
                onClick={() => setVersionOpen(!versionOpen)}
                className="flex w-full items-center justify-between rounded-md border border-input bg-background/50 px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent transition-colors"
              >
                <span className="font-medium">v1.0</span>
                <ChevronDown className="h-3 w-3" />
              </button>
              {versionOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setVersionOpen(false)} />
                  <div className="absolute bottom-full left-0 right-0 mb-1 z-20 rounded-md border bg-popover p-3 shadow-md">
                    <p className="text-xs text-muted-foreground">
                      {t("docs.versionHistoryComingSoon")}
                    </p>
                  </div>
                </>
              )}
            </div>

            {/* Docs home link */}
            <Link
              to="/docs"
              className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setSidebarOpen(false)}
            >
              <ChevronLeft className="h-3 w-3" />
              {t("docs.documentationHome")}
            </Link>
          </div>
        </aside>

        {/* Content */}
        <main className="flex-1 px-4 py-8 lg:px-12 lg:py-12 max-w-4xl min-w-0">
          <Outlet />
        </main>
      </div>
    </>
  )
}
