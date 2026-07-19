import { useEffect, useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Callout } from "@/components/ui/callout"
import { Skeleton } from "@/components/ui/loading-spinner"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useAuth } from "@/contexts/auth-provider"
import { waitlistApi, type WaitlistStatsResponse } from "@/api/endpoints"
import { extractApiError } from "@/api/client"
import { useLocale } from "@/i18n/locale-context"
import OverviewTab from "./overview-tab"
import EntriesTab from "./entries-tab"
import CampaignTab from "./campaign-tab"

export default function AdminWaitlistPage() {
  const { isAdmin } = useAuth()
  const { t } = useLocale()
  const [stats, setStats] = useState<WaitlistStatsResponse | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsError, setStatsError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAdmin) return
    let cancelled = false
    setStatsLoading(true)
    setStatsError(null)
    waitlistApi
      .getStats()
      .then((res) => {
        if (!cancelled) setStats(res.data)
      })
      .catch((err) => {
        if (!cancelled) setStatsError(extractApiError(err))
      })
      .finally(() => {
        if (!cancelled) setStatsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [isAdmin])

  if (!isAdmin) {
    return (
      <SectionWrapper>
        <Callout variant="warning" title={t("adminWaitlist.accessDenied.title")}>
          {t("adminWaitlist.accessDenied.message")}
        </Callout>
      </SectionWrapper>
    )
  }

  return (
    <>
      <Helmet>
        <title>{t("adminWaitlist.pageTitle")}</title>
      </Helmet>

      <PageHeader
        title={t("adminWaitlist.pageHeader")}
        description={
          statsLoading
            ? t("adminWaitlist.loading")
            : statsError
              ? t("adminWaitlist.loadError")
              : t("adminWaitlist.subtitle").replace("{count}", String(stats?.total ?? 0))
        }
      />

      <SectionWrapper className="pt-0">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          {statsError && (
            <Callout variant="danger" className="mb-6">
              {statsError}
            </Callout>
          )}

          <Tabs defaultValue="overview">
            <TabsList>
              <TabsTrigger value="overview">{t("adminWaitlist.tabs.overview")}</TabsTrigger>
              <TabsTrigger value="entries">{t("adminWaitlist.tabs.entries")}</TabsTrigger>
              <TabsTrigger value="campaign">{t("adminWaitlist.tabs.campaign")}</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="mt-6">
              {statsLoading && !stats ? (
                <div className="space-y-6">
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-28" />
                    ))}
                  </div>
                  <Skeleton className="h-64" />
                </div>
              ) : (
                <OverviewTab stats={stats} />
              )}
            </TabsContent>

            <TabsContent value="entries" className="mt-6">
              <EntriesTab />
            </TabsContent>

            <TabsContent value="campaign" className="mt-6">
              <CampaignTab />
            </TabsContent>
          </Tabs>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
