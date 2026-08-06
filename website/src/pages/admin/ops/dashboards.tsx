import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import {
  AlertTriangle,
  ClipboardCheck,
  Ticket,
  TrendingUp,
  Activity,
  Cpu,
  Layers,
  DollarSign,
  GitBranch,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { EmptyState } from "@/components/shared/empty-state"
import { useOpsDashboard } from "@/services/queries"

// ─── Fallback static data for sections without API endpoints ──
// These are honest defaults, not mock data. Replace with real API
// queries once the corresponding endpoints are available.

const supportHealth = {
  openTickets: "—",
  avgResponseMinutes: "—",
  slaCompliance: null as number | null,
  satisfaction: null as number | null,
}

const pipelineFunnel: { stage: string; count: number | string }[] = [
  { stage: "Submitted", count: "—" },
  { stage: "In Review", count: "—" },
  { stage: "Approved", count: "—" },
  { stage: "Merged", count: "—" },
]

const guardrailActivity = {
  blocksThisWeek: "—",
  reviewsThisWeek: "—",
  falsePositives: "—",
}

const costMetrics = {
  computeThisMonth: "—",
  storageThisMonth: "—",
  trend: null as string | null,
}

const capacityMetrics = {
  queueDepth: "—",
  maxCapacity: "—",
  activeWorkers: "—",
}

const dependencyHealth: { name: string; status: string }[] = [
  { name: "Routing API", status: "—" },
  { name: "Maps Provider", status: "—" },
  { name: "PDF Service", status: "—" },
  { name: "Push Gateway", status: "—" },
  { name: "Billing API", status: "—" },
]

export default function OpsDashboardsPage() {
  const { t } = useLocale()
  const { data: summary, isLoading, isError } = useOpsDashboard()

  const statusLight = (status: string) => {
    const colors: Record<string, string> = {
      operational: "bg-green-500",
      degraded: "bg-amber-500",
      outage: "bg-red-500",
      maintenance: "bg-blue-500",
    }
    return <span className={`inline-block h-2.5 w-2.5 rounded-full ${colors[status] || "bg-gray-400"}`} />
  }

  const maxFunnel = Math.max(...pipelineFunnel.map((s) => (typeof s.count === "number" ? s.count : 0)))

  return (
    <>
      <Helmet>
        <title>{t("ops.dashboards.pageTitle") || "Dashboards — Operion Ops"}</title>
      </Helmet>

      <SectionWrapper className="pt-0">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="space-y-8"
        >
          {/* Summary bar */}
          {isLoading ? (
            <div className="flex justify-center py-12">
              <LoadingSpinner size="lg" />
            </div>
          ) : isError ? (
            <EmptyState
              title={t("common.error") || "Error"}
              description={t("ops.dashboards.loadError") || "Failed to load dashboard data. Please try again later."}
              icon={<AlertTriangle className="h-16 w-16" />}
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card>
                <CardContent className="flex items-center gap-4 p-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900/40">
                    <Ticket className="h-5 w-5 text-amber-700 dark:text-amber-200" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{summary?.unresolved ?? "—"}</p>
                    <p className="text-xs text-muted-foreground">{t("ops.dashboards.unresolved") || "Unresolved tickets"}</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="flex items-center gap-4 p-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-100 dark:bg-indigo-900/40">
                    <ClipboardCheck className="h-5 w-5 text-indigo-700 dark:text-indigo-200" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{summary?.pending_approvals ?? "—"}</p>
                    <p className="text-xs text-muted-foreground">{t("ops.dashboards.pendingApprovals") || "Pending approvals"}</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="flex items-center gap-4 p-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 dark:bg-green-900/40">
                    <TrendingUp className="h-5 w-5 text-green-700 dark:text-green-200" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">
                      {summary?.patch_success_rate != null ? `${summary.patch_success_rate}%` : "—"}
                    </p>
                    <p className="text-xs text-muted-foreground">{t("ops.dashboards.patchSuccess") || "Patch success rate"}</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="flex items-center gap-4 p-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100 dark:bg-red-900/40">
                    <AlertTriangle className="h-5 w-5 text-red-700 dark:text-red-200" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{summary?.critical_escalations ?? "—"}</p>
                    <p className="text-xs text-muted-foreground">{t("ops.dashboards.criticalEscalations") || "Critical escalations"}</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Health panels */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Support health */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-muted-foreground" />
                  {t("ops.dashboards.supportHealth") || "Support health"}
                </CardTitle>
                <CardDescription>
                  {t("ops.dashboards.supportHealthDesc") || "Real-time support metrics — data pending API integration."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t("ops.dashboards.openTickets") || "Open tickets"}</span>
                  <span className="text-sm font-semibold">{supportHealth.openTickets}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t("ops.dashboards.avgResponse") || "Avg. response time"}</span>
                  <span className="text-sm font-semibold">{supportHealth.avgResponseMinutes} min</span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t("ops.dashboards.slaCompliance") || "SLA compliance"}</span>
                    <span className="font-semibold">{supportHealth.slaCompliance != null ? `${supportHealth.slaCompliance}%` : "—"}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-secondary">
                    <div
                      className="h-full rounded-full bg-green-500"
                      style={{ width: `${supportHealth.slaCompliance != null ? supportHealth.slaCompliance : 0}%` }}
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t("ops.dashboards.satisfaction") || "Satisfaction score"}</span>
                    <span className="font-semibold">{supportHealth.satisfaction != null ? `${supportHealth.satisfaction}/5` : "—"}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-secondary">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${supportHealth.satisfaction != null ? (supportHealth.satisfaction / 5) * 100 : 0}%` }}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Pipeline funnel */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Layers className="h-5 w-5 text-muted-foreground" />
                  {t("ops.dashboards.pipelineFunnel") || "Pipeline funnel"}
                </CardTitle>
                <CardDescription>
                  {t("ops.dashboards.pipelineFunnelDesc") || "Patch pipeline — data pending API integration."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {pipelineFunnel.map((stage, i) => (
                  <div key={stage.stage} className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{stage.stage}</span>
                      <span className="font-semibold">{stage.count}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-secondary">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${maxFunnel > 0 ? (typeof stage.count === "number" ? (stage.count / maxFunnel) * 100 : 0) : 0}%` }}
                        transition={{ duration: 0.6, delay: i * 0.1 }}
                        className="h-full rounded-full bg-primary"
                      />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Guardrail activity */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Cpu className="h-5 w-5 text-muted-foreground" />
                  {t("ops.dashboards.guardrailActivity") || "Guardrail activity"}
                </CardTitle>
                <CardDescription>
                  {t("ops.dashboards.guardrailActivityDesc") || "Automated guardrail stats — data pending API integration."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t("ops.dashboards.blocksThisWeek") || "Hard blocks this week"}</span>
                  <Badge variant="destructive">{guardrailActivity.blocksThisWeek}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t("ops.dashboards.reviewsThisWeek") || "Reviews required this week"}</span>
                  <Badge variant="default">{guardrailActivity.reviewsThisWeek}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t("ops.dashboards.falsePositives") || "False positives"}</span>
                  <Badge variant="secondary">{guardrailActivity.falsePositives}</Badge>
                </div>
              </CardContent>
            </Card>

            {/* Cost */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5 text-muted-foreground" />
                  {t("ops.dashboards.cost") || "Cost"}
                </CardTitle>
                <CardDescription>
                  {t("ops.dashboards.costDesc") || "Cost metrics — data pending API integration."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t("ops.dashboards.compute") || "Compute this month"}</span>
                  <span className="text-sm font-semibold">{costMetrics.computeThisMonth}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t("ops.dashboards.storage") || "Storage this month"}</span>
                  <span className="text-sm font-semibold">{costMetrics.storageThisMonth}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t("ops.dashboards.trend") || "Trend vs last month"}</span>
                  <span className="text-sm font-semibold text-muted-foreground">
                    {costMetrics.trend || "—"}
                  </span>
                </div>
              </CardContent>
            </Card>

            {/* Capacity / queue depth */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Cpu className="h-5 w-5 text-muted-foreground" />
                  {t("ops.dashboards.capacity") || "Capacity & queue depth"}
                </CardTitle>
                <CardDescription>
                  {t("ops.dashboards.capacityDesc") || "Worker capacity — data pending API integration."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t("ops.dashboards.queueDepth") || "Queue depth"}</span>
                    <span className="font-semibold">
                      {capacityMetrics.queueDepth} / {capacityMetrics.maxCapacity}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-secondary">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: "0%" }}
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t("ops.dashboards.activeWorkers") || "Active workers"}</span>
                  <span className="text-sm font-semibold">{capacityMetrics.activeWorkers}</span>
                </div>
              </CardContent>
            </Card>

            {/* Dependency health */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <GitBranch className="h-5 w-5 text-muted-foreground" />
                  {t("ops.dashboards.dependencies") || "Dependency health"}
                </CardTitle>
                <CardDescription>
                  {t("ops.dashboards.dependenciesDesc") || "External service status — data pending API integration."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {dependencyHealth.map((dep) => (
                    <div key={dep.name} className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {statusLight(dep.status)}
                        <span className="text-sm">{dep.name}</span>
                      </div>
                      <Badge variant="outline" className="text-xs capitalize text-muted-foreground">
                        {dep.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
