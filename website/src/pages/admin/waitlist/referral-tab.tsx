import { useEffect, useState } from "react"
import { motion } from "motion/react"
import {
  Users,
  CheckCircle2,
  Clock,
  TrendingUp,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { StatCard } from "@/components/shared/stat-card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/loading-spinner"
import { Callout } from "@/components/ui/callout"
import { Badge } from "@/components/ui/badge"
import { referralApi, type Referral } from "@/api/endpoints"
import { extractApiError } from "@/api/client"
import { useLocale } from "@/i18n/locale-context"

export default function ReferralTab() {
  const { t } = useLocale()
  const [referrals, setReferrals] = useState<Referral[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<{
    total_referrals: number
    completed_referrals: number
    pending_referrals: number
  } | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    Promise.all([
      referralApi.listReferrals({ page_size: 100 }),
      referralApi.getReferralStats(),
    ])
      .then(([refRes, statsRes]) => {
        if (!cancelled) {
          setReferrals(refRes.data.referrals)
          setStats(statsRes.data)
        }
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
  }, [])

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (error) {
    return (
      <Callout variant="danger" title={t("admin.waitlist.referrals.loadFailed")}>
        {error}
        <div className="mt-3">
          <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
            {t("admin.waitlist.overview.retry")}
          </Button>
        </div>
      </Callout>
    )
  }

  return (
    <div className="space-y-8">
      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
        >
          <StatCard
            value={String(stats?.total_referrals ?? 0)}
            label={t("admin.waitlist.overview.totalReferrals")}
            icon={Users}
          />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <StatCard
            value={String(stats?.pending_referrals ?? 0)}
            label={t("referral.pending")}
            icon={Clock}
          />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <StatCard
            value={String(stats?.completed_referrals ?? 0)}
            label={t("referral.completed")}
            icon={CheckCircle2}
          />
        </motion.div>
      </div>

      {/* Referral Rate */}
      {stats && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card>
            <CardContent className="flex items-center gap-6 py-6">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                <TrendingUp className="h-8 w-8 text-primary" />
              </div>
              <div>
                <p className="text-4xl font-bold tracking-tight">
                  {stats.total_referrals > 0
                    ? ((stats.completed_referrals / stats.total_referrals) * 100).toFixed(1)
                    : "0.0"}%
                </p>
                <p className="text-sm text-muted-foreground">{t("admin.waitlist.overview.referralRate")}</p>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Referrals Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t("admin.waitlist.referrals.title")}</CardTitle>
            <CardDescription>{t("admin.waitlist.referrals.desc")}</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {referrals.length === 0 ? (
              <div className="px-6 py-8 text-center text-sm text-muted-foreground">
                {t("admin.waitlist.referrals.noReferrals")}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                        {t("admin.waitlist.referrals.referrer")}
                      </th>
                      <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                        {t("admin.waitlist.referrals.referred")}
                      </th>
                      <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                        {t("admin.waitlist.referrals.code")}
                      </th>
                      <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                        {t("admin.waitlist.referrals.status")}
                      </th>
                      <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                        {t("admin.waitlist.referrals.date")}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {referrals.map((ref) => (
                      <tr key={ref.id} className="hover:bg-muted/30 transition-colors">
                        <td className="px-4 py-3 font-medium">{ref.referrer_email}</td>
                        <td className="px-4 py-3">{ref.referred_email}</td>
                        <td className="px-4 py-3">
                          <code className="rounded bg-muted px-2 py-0.5 text-xs font-mono">
                            {ref.referral_code}
                          </code>
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={
                              ref.status === "completed"
                                ? "success"
                                : ref.status === "pending"
                                  ? "secondary"
                                  : "outline"
                            }
                          >
                            {ref.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {new Date(ref.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}
