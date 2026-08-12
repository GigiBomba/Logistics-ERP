import { useState, useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import {
  TrendingUp,
  DollarSign,
  PiggyBank,
  Banknote,
  Truck,
  BarChart3,
  Route,
  CheckCircle2,
  Clock,
  XCircle,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatCard } from "@/components/shared/stat-card"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { useLocale } from "@/i18n/locale-context"
import { useFinancialAnalytics } from "@/services/queries"

// ─── Types ──────────────────────────────────────────────────────

interface AnalyticsSummary {
  total_revenue: number
  total_expenses: number
  net_profit: number
  fleet_utilization: number
  revenue_trend?: number
  expenses_trend?: number
  profit_trend?: number
}

interface FleetUtilizationItem {
  vehicle: string
  utilization_rate: number
}

interface MonthlyTrend {
  month: string
  revenue: number
  expenses: number
}

interface TripStatus {
  completed: number
  in_progress: number
  cancelled: number
}

interface FinancialAnalyticsResponse {
  summary: AnalyticsSummary
  fleet_utilization: FleetUtilizationItem[]
  monthly_trends: MonthlyTrend[]
  trip_status: TripStatus
}

// ─── Helpers ────────────────────────────────────────────────────

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

function formatPercent(value: number): string {
  return `${Math.round(value)}%`
}

function formatTrendValue(value: number | undefined): string {
  if (value === undefined || value === null) return ""
  const sign = value >= 0 ? "+" : ""
  return `${sign}${value.toFixed(1)}%`
}

function addDays(date: Date, days: number): Date {
  const result = new Date(date)
  result.setDate(result.getDate() + days)
  return result
}

function formatDateInput(date: Date): string {
  return date.toISOString().split("T")[0]
}

function maxValue(...values: number[]): number {
  return Math.max(...values, 1)
}

// ─── Preset definitions ─────────────────────────────────────────

type PresetKey = "7d" | "30d" | "90d" | "1y"

interface Preset {
  key: PresetKey
  labelKey: string
  days: number
}

const presets: Preset[] = [
  { key: "7d", labelKey: "analytics.last7Days", days: 7 },
  { key: "30d", labelKey: "analytics.last30Days", days: 30 },
  { key: "90d", labelKey: "analytics.last90Days", days: 90 },
  { key: "1y", labelKey: "analytics.lastYear", days: 365 },
]

// ─── Page Component ─────────────────────────────────────────────

export default function AnalyticsPage() {
  const { t } = useLocale()

  // Date range state
  const today = useMemo(() => new Date(), [])
  const [activePreset, setActivePreset] = useState<PresetKey>("30d")
  const [customFrom, setCustomFrom] = useState("")
  const [customTo, setCustomTo] = useState("")
  const [useCustom, setUseCustom] = useState(false)

  // Compute date_from / date_to from preset or custom
  const dateFrom = useMemo(() => {
    if (useCustom && customFrom) return customFrom
    const preset = presets.find((p) => p.key === activePreset)
    if (preset) return formatDateInput(addDays(today, -preset.days))
    return formatDateInput(addDays(today, -30))
  }, [activePreset, useCustom, customFrom, today])

  const dateTo = useMemo(() => {
    if (useCustom && customTo) return customTo
    return formatDateInput(today)
  }, [useCustom, customTo, today])

  // Fetch data
  const { data, isLoading, isError } = useFinancialAnalytics(dateFrom, dateTo)

  const analytics = data as FinancialAnalyticsResponse | undefined

  // Handlers
  function handlePresetClick(key: PresetKey) {
    setActivePreset(key)
    setUseCustom(false)
  }

  function handleCustomApply() {
    if (customFrom && customTo) {
      setUseCustom(true)
    }
  }

  return (
    <>
      <Helmet>
        <title>{t("analytics.pageTitle")}</title>
      </Helmet>

      <SectionWrapper>
        {/* Page Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">{t("analytics.title")}</h1>
              <p className="mt-2 text-muted-foreground">{t("analytics.description")}</p>
            </div>
          </div>
        </motion.div>

        {/* Date Range Selector */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.05 }}
          className="mt-6"
        >
          <div className="flex flex-wrap items-center gap-2">
            {presets.map((preset) => (
              <Button
                key={preset.key}
                variant={activePreset === preset.key && !useCustom ? "default" : "outline"}
                size="sm"
                onClick={() => handlePresetClick(preset.key)}
              >
                {t(preset.labelKey)}
              </Button>
            ))}
            <span className="mx-1 text-muted-foreground">|</span>
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                aria-label={t("analytics.from")}
              />
              <span className="text-xs text-muted-foreground">{t("analytics.to")}</span>
              <input
                type="date"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-xs shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                aria-label={t("analytics.to")}
              />
              <Button variant="secondary" size="sm" onClick={handleCustomApply} disabled={!customFrom || !customTo}>
                {t("analytics.apply")}
              </Button>
            </div>
          </div>
        </motion.div>

        {/* Loading State */}
        {isLoading && (
          <div className="mt-8 flex min-h-[40vh] items-center justify-center">
            <LoadingSpinner size="lg" />
          </div>
        )}

        {/* Error State */}
        {isError && !isLoading && (
          <div className="mt-8 flex min-h-[40vh] items-center justify-center">
            <Card className="w-full max-w-md">
              <CardContent className="flex flex-col items-center gap-4 p-8 text-center">
                <BarChart3 className="h-12 w-12 text-muted-foreground" />
                <p className="text-lg font-medium">{t("analytics.failedToLoad")}</p>
                <p className="text-sm text-muted-foreground">
                  {t("analytics.failedToLoadDesc")}
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Content */}
        {!isLoading && !isError && analytics && (
          <>
            {/* Summary Stat Cards */}
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.05 }}
              >
                <StatCard
                  value={formatCurrency(analytics.summary.total_revenue)}
                  label={t("analytics.totalRevenue")}
                  icon={DollarSign}
                  trend={
                    analytics.summary.revenue_trend !== undefined
                      ? {
                          direction: (analytics.summary.revenue_trend ?? 0) >= 0 ? "up" as const : "down" as const,
                          value: formatTrendValue(analytics.summary.revenue_trend),
                        }
                      : undefined
                  }
                />
              </motion.div>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
              >
                <StatCard
                  value={formatCurrency(analytics.summary.total_expenses)}
                  label={t("analytics.totalExpenses")}
                  icon={PiggyBank}
                  trend={
                    analytics.summary.expenses_trend !== undefined
                      ? {
                          direction: (analytics.summary.expenses_trend ?? 0) >= 0 ? "up" as const : "down" as const,
                          value: formatTrendValue(analytics.summary.expenses_trend),
                        }
                      : undefined
                  }
                />
              </motion.div>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.15 }}
              >
                <StatCard
                  value={formatCurrency(analytics.summary.net_profit)}
                  label={t("analytics.netProfit")}
                  icon={Banknote}
                  trend={
                    analytics.summary.profit_trend !== undefined
                      ? {
                          direction: (analytics.summary.profit_trend ?? 0) >= 0 ? "up" as const : "down" as const,
                          value: formatTrendValue(analytics.summary.profit_trend),
                        }
                      : undefined
                  }
                />
              </motion.div>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
              >
                <StatCard
                  value={formatPercent(analytics.summary.fleet_utilization)}
                  label={t("analytics.fleetUtilization")}
                  icon={Truck}
                />
              </motion.div>
            </div>

            {/* Two Column Layout */}
            <div className="mt-8 grid gap-6 lg:grid-cols-2">
              {/* Fleet Utilization Section */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.25 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Truck className="h-5 w-5" />
                      {t("analytics.fleetUtilization")}
                    </CardTitle>
                    <CardDescription>{t("analytics.fleetUtilizationDescFull")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {analytics.fleet_utilization.length === 0 ? (
                      <p className="text-sm text-muted-foreground">{t("analytics.noFleetUtilization")}</p>
                    ) : (
                      analytics.fleet_utilization.map((item) => {
                        const pct = Math.round(item.utilization_rate * 100)
                        const barColor =
                          pct >= 80
                            ? "bg-green-500"
                            : pct >= 50
                              ? "bg-amber-500"
                              : "bg-red-500"
                        return (
                          <div key={item.vehicle} className="space-y-1.5">
                            <div className="flex items-center justify-between text-sm">
                              <span className="font-medium">{item.vehicle}</span>
                              <span className="text-muted-foreground">{pct}%</span>
                            </div>
                            <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                              <div
                                className={`h-full rounded-full transition-all ${barColor}`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        )
                      })
                    )}
                  </CardContent>
                </Card>
              </motion.div>

              {/* Monthly Trends Section */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.3 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <TrendingUp className="h-5 w-5" />
                      {t("analytics.monthlyTrends")}
                    </CardTitle>
                    <CardDescription>{t("analytics.monthlyTrendsDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {analytics.monthly_trends.length === 0 ? (
                      <p className="text-sm text-muted-foreground">{t("analytics.noTrendData")}</p>
                    ) : (
                      analytics.monthly_trends.map((item) => {
                        const maxRev = maxValue(...analytics.monthly_trends.map((m) => m.revenue))
                        const maxExp = maxValue(...analytics.monthly_trends.map((m) => m.expenses))
                        const revWidth = (item.revenue / maxRev) * 100
                        const expWidth = (item.expenses / maxExp) * 100
                        return (
                          <div key={item.month} className="space-y-1.5">
                            <div className="flex items-center justify-between text-sm">
                              <span className="font-medium">{item.month}</span>
                              <span className="text-xs text-muted-foreground">
                                {formatCurrency(item.revenue)} / {formatCurrency(item.expenses)}
                              </span>
                            </div>
                            {/* Revenue bar */}
                            <div className="flex items-center gap-2">
                              <span className="w-12 text-xs text-muted-foreground">{t("analytics.revenue")}</span>
                              <div className="flex-1 h-2.5 overflow-hidden rounded-full bg-muted">
                                <div
                                  className="h-full rounded-full bg-blue-500 transition-all"
                                  style={{ width: `${revWidth}%` }}
                                />
                              </div>
                            </div>
                            {/* Expense bar */}
                            <div className="flex items-center gap-2">
                              <span className="w-12 text-xs text-muted-foreground">{t("analytics.expenses")}</span>
                              <div className="flex-1 h-2.5 overflow-hidden rounded-full bg-muted">
                                <div
                                  className="h-full rounded-full bg-rose-500 transition-all"
                                  style={{ width: `${expWidth}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        )
                      })
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* Trip Status Section */}
            <div className="mt-6 grid gap-6 lg:grid-cols-1">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.35 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Route className="h-5 w-5" />
                      {t("analytics.tripStatus")}
                    </CardTitle>
                    <CardDescription>{t("analytics.tripStatusDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-4 sm:grid-cols-3">
                      {/* Completed */}
                      <div className="rounded-lg border bg-card p-4 text-center">
                        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
                          <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
                        </div>
                        <p className="mt-3 text-2xl font-bold">{analytics.trip_status.completed}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{t("analytics.completed")}</p>
                      </div>
                      {/* In Progress */}
                      <div className="rounded-lg border bg-card p-4 text-center">
                        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30">
                          <Clock className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                        </div>
                        <p className="mt-3 text-2xl font-bold">{analytics.trip_status.in_progress}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{t("analytics.inProgress")}</p>
                      </div>
                      {/* Cancelled */}
                      <div className="rounded-lg border bg-card p-4 text-center">
                        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
                          <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
                        </div>
                        <p className="mt-3 text-2xl font-bold">{analytics.trip_status.cancelled}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{t("analytics.cancelled")}</p>
                      </div>
                    </div>
                    {/* Total trips bar */}
                    <div className="mt-6">
                      <div className="flex items-center justify-between text-sm text-muted-foreground">
                        <span>{t("analytics.trips")}</span>
                        <span>
                          {analytics.trip_status.completed + analytics.trip_status.in_progress + analytics.trip_status.cancelled} total
                        </span>
                      </div>
                      <div className="mt-2 flex h-3 w-full overflow-hidden rounded-full bg-muted">
                        <div
                          className="bg-green-500 transition-all"
                          style={{
                            width: `${(analytics.trip_status.completed / maxValue(analytics.trip_status.completed + analytics.trip_status.in_progress + analytics.trip_status.cancelled, 1)) * 100}%`,
                          }}
                        />
                        <div
                          className="bg-blue-500 transition-all"
                          style={{
                            width: `${(analytics.trip_status.in_progress / maxValue(analytics.trip_status.completed + analytics.trip_status.in_progress + analytics.trip_status.cancelled, 1)) * 100}%`,
                          }}
                        />
                        <div
                          className="bg-red-500 transition-all"
                          style={{
                            width: `${(analytics.trip_status.cancelled / maxValue(analytics.trip_status.completed + analytics.trip_status.in_progress + analytics.trip_status.cancelled, 1)) * 100}%`,
                          }}
                        />
                      </div>
                      <div className="mt-2 flex justify-between text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <span className="inline-block h-2 w-2 rounded-full bg-green-500" /> {t("analytics.completed")}
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="inline-block h-2 w-2 rounded-full bg-blue-500" /> {t("analytics.inProgress")}
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="inline-block h-2 w-2 rounded-full bg-red-500" /> {t("analytics.cancelled")}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </>
        )}
      </SectionWrapper>
    </>
  )
}
