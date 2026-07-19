import { useEffect, useMemo, useState } from "react"
import { motion } from "motion/react"
import {
  Users,
  MailOpen,
  Zap,
  CheckCircle2,
  TrendingUp,
  Globe,
  Building2,
  Truck,
  Link2,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { StatCard } from "@/components/shared/stat-card"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/loading-spinner"
import { Callout } from "@/components/ui/callout"
import { waitlistApi, type WaitlistStatsResponse } from "@/api/endpoints"
import { extractApiError } from "@/api/client"
import { useLocale } from "@/i18n/locale-context"

interface OverviewTabProps {
  stats: WaitlistStatsResponse | null
}

function BreakdownGrid({
  title,
  icon: Icon,
  data,
}: {
  title: string
  icon: React.ElementType
  data: Record<string, number>
}) {
  const { t } = useLocale()
  const entries = useMemo(() => Object.entries(data).sort((a, b) => b[1] - a[1]), [data])
  const max = entries[0]?.[1] ?? 1

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="h-4 w-4" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {entries.length === 0 && (
          <p className="text-sm text-muted-foreground">{t("adminWaitlist.overview.noData")}</p>
        )}
        {entries.map(([key, count]) => (
          <div key={key} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{key}</span>
              <span className="text-muted-foreground">{count}</span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-primary/70 transition-all"
                style={{ width: `${Math.max((count / max) * 100, 4)}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function FunnelBar({
  label,
  count,
  max,
  colorClass,
}: {
  label: string
  count: number
  max: number
  colorClass: string
}) {
  const pct = max > 0 ? (count / max) * 100 : 0
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">{count}</span>
      </div>
      <div className="h-4 w-full rounded-md bg-muted overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className={"h-full rounded-md " + colorClass}
        />
      </div>
    </div>
  )
}

function GrowthChart({ data }: { data?: Array<{ date: string; count: number }> | null }) {
  const { t } = useLocale()
  const sliced = useMemo(() => (data ?? []).slice(-30), [data])
  const max = useMemo(() => Math.max(...sliced.map((d) => d.count), 1), [sliced])

  if (!data || data.length === 0) {
    return null
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{t("adminWaitlist.overview.growth")}</CardTitle>
        <CardDescription>{t("adminWaitlist.overview.growthDesc")}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-1 h-40">
          {sliced.map((d, i) => {
            const h = (d.count / max) * 100
            return (
              <TooltipBar key={d.date} date={d.date} count={d.count}>
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: `${h}%` }}
                  transition={{ duration: 0.4, delay: i * 0.01 }}
                  className="flex-1 min-w-[2px] rounded-t-sm bg-primary/60 hover:bg-primary transition-colors"
                />
              </TooltipBar>
            )
          })}
        </div>
        <div className="mt-2 flex justify-between text-[10px] text-muted-foreground">
          <span>{sliced[0]?.date}</span>
          <span>{sliced[sliced.length - 1]?.date}</span>
        </div>
      </CardContent>
    </Card>
  )
}

function TooltipBar({
  date,
  count,
  children,
}: {
  date: string
  count: number
  children: React.ReactNode
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      className="relative flex-1 flex flex-col justify-end h-full"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {children}
      {hovered && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 z-10 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-[10px] text-background shadow-sm">
          {date}: {count}
        </div>
      )}
    </div>
  )
}

export default function OverviewTab({ stats }: OverviewTabProps) {
  const { t } = useLocale()
  const [localStats, setLocalStats] = useState<WaitlistStatsResponse | null>(stats)
  const [loading, setLoading] = useState(!stats)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (stats) {
      setLocalStats(stats)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    waitlistApi
      .getStats()
      .then((res) => {
        if (!cancelled) setLocalStats(res.data)
      })
      .catch((err) => {
        if (!cancelled) setError(extractApiError(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [stats])

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (error) {
    return (
      <Callout variant="danger" title={t("adminWaitlist.overview.loadFailed")}>
        {error}
        <div className="mt-3">
          <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
            {t("adminWaitlist.overview.retry")}
          </Button>
        </div>
      </Callout>
    )
  }

  if (!localStats) return null

  const bs = localStats.by_status
  const total = localStats.total
  const invited = bs.invited ?? 0
  const activated = bs.activated ?? 0
  const converted = bs.converted ?? 0

  return (
    <div className="space-y-8">
      {/* Stat Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
        >
          <StatCard value={String(total)} label={t("adminWaitlist.overview.totalSignups")} icon={Users} />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <StatCard value={String(invited)} label={t("adminWaitlist.overview.invited")} icon={MailOpen} />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <StatCard value={String(activated)} label={t("adminWaitlist.overview.activated")} icon={Zap} />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <StatCard value={String(converted)} label={t("adminWaitlist.overview.converted")} icon={CheckCircle2} />
        </motion.div>
      </div>

      {/* Conversion Rate */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <Card>
          <CardContent className="flex items-center gap-6 py-6">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <TrendingUp className="h-8 w-8 text-primary" />
            </div>
            <div>
              <p className="text-4xl font-bold tracking-tight">
                {(localStats.conversion_rate * 100).toFixed(1)}%
              </p>
              <p className="text-sm text-muted-foreground">{t("adminWaitlist.overview.conversionRate")}</p>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Funnel */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t("adminWaitlist.overview.funnel")}</CardTitle>
            <CardDescription>{t("adminWaitlist.overview.funnelDesc")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 max-w-2xl">
            <FunnelBar label={t("adminWaitlist.overview.joined")} count={total} max={total} colorClass="bg-muted-foreground/40" />
            <FunnelBar label={t("adminWaitlist.overview.invited")} count={invited} max={total} colorClass="bg-blue-500" />
            <FunnelBar label={t("adminWaitlist.overview.activated")} count={activated} max={total} colorClass="bg-amber-500" />
            <FunnelBar label={t("adminWaitlist.overview.converted")} count={converted} max={total} colorClass="bg-emerald-500" />
          </CardContent>
        </Card>
      </motion.div>

      {/* Breakdowns */}
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
        >
          <BreakdownGrid title={t("adminWaitlist.overview.byCountry")} icon={Globe} data={localStats.by_country} />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <BreakdownGrid title={t("adminWaitlist.overview.byCompanySize")} icon={Building2} data={localStats.by_company_size} />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
        >
          <BreakdownGrid title={t("adminWaitlist.overview.byFleetSize")} icon={Truck} data={localStats.by_fleet_size} />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <BreakdownGrid title={t("adminWaitlist.overview.bySource")} icon={Link2} data={localStats.by_source} />
        </motion.div>
      </div>

      {/* Growth Chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.55 }}
      >
        <GrowthChart data={localStats.growth_daily} />
      </motion.div>
    </div>
  )
}
