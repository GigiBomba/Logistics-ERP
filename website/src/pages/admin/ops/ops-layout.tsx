import { Outlet, useLocation, Link } from "react-router"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { Ticket, ClipboardCheck, ShieldAlert, LayoutDashboard, BookOpen } from "lucide-react"
import { useLocale } from "@/i18n/locale-context"
import { cn } from "@/lib/utils"

const tabs = [
  { label: "ops.layout.tickets", fallback: "Tickets", href: "/admin/ops/tickets", icon: Ticket },
  { label: "ops.layout.approvals", fallback: "Approvals", href: "/admin/ops/approvals", icon: ClipboardCheck },
  { label: "ops.layout.guardrails", fallback: "Guardrails", href: "/admin/ops/guardrails", icon: ShieldAlert },
  { label: "ops.layout.dashboards", fallback: "Dashboards", href: "/admin/ops/dashboards", icon: LayoutDashboard },
  { label: "ops.layout.knowledge", fallback: "Knowledge", href: "/admin/ops/knowledge", icon: BookOpen },
]

export default function OpsLayout() {
  const { t } = useLocale()
  const location = useLocation()

  return (
    <>
      <Helmet>
        <title>{t("ops.layout.pageTitle") || "Founder Ops — Operion"}</title>
      </Helmet>

      <div className="border-b bg-background">
        <div className="container-wide py-6">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            <h1 className="text-3xl font-bold tracking-tight">
              {t("ops.layout.heading") || "Founder Ops Console"}
            </h1>
            <p className="mt-2 max-w-2xl text-muted-foreground">
              {t("ops.layout.description") || "Review tickets, approve changes, monitor guardrails, and manage knowledge drafts."}
            </p>
          </motion.div>

          <nav className="mt-6 flex gap-2 overflow-x-auto">
            {tabs.map((tab) => {
              const isActive = location.pathname === tab.href || location.pathname.startsWith(`${tab.href}/`)
              return (
                <Link
                  key={tab.href}
                  to={tab.href}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  <tab.icon className="h-4 w-4" />
                  {t(tab.label) || tab.fallback}
                </Link>
              )
            })}
          </nav>
        </div>
      </div>

      <div className="container-wide py-8">
        <Outlet />
      </div>
    </>
  )
}
