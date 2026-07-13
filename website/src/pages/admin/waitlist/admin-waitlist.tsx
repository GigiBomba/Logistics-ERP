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
import OverviewTab from "./overview-tab"
import EntriesTab from "./entries-tab"
import CampaignTab from "./campaign-tab"

export default function AdminWaitlistPage() {
  const { isAdmin } = useAuth()
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
        <Callout variant="warning" title="Access Denied">
          You do not have permission to access this page.
        </Callout>
      </SectionWrapper>
    )
  }

  return (
    <>
      <Helmet>
        <title>Waitlist Management — Operion ERP</title>
      </Helmet>

      <PageHeader
        title="Waitlist Management"
        description={
          statsLoading
            ? "Loading waitlist stats…"
            : statsError
              ? "Unable to load stats"
              : `${stats?.total ?? 0} total signups · Manage entries, review analytics, and plan campaigns.`
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
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="entries">Entries</TabsTrigger>
              <TabsTrigger value="campaign">Campaign</TabsTrigger>
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
