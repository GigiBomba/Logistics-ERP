import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { Download, BookOpen, LifeBuoy, ChevronRight, CreditCard, Key, Megaphone, Activity, HardDrive, Globe, Map, Radio, Puzzle, Code, Rocket, Clock, Smartphone, LayoutGrid, AlertTriangle } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { ReleaseCard } from "@/components/shared/release-card"
import { StatCard } from "@/components/shared/stat-card"
import { EmptyState } from "@/components/shared/empty-state"
import { downloadConfig } from "@/config/site"
import type { Release } from "@/components/shared/release-card"
import { useLocale } from "@/i18n/locale-context"
import { useDevices, useCompany, useTickets, useServiceStatus, useAnnouncements, useChangelog } from "@/services/queries"

const shortcuts = [
  { icon: Download, labelKey: "dashboard.downloads", descriptionKey: "dashboard.downloadsDesc", href: "/dashboard/downloads" },
  { icon: BookOpen, labelKey: "dashboard.documentation", descriptionKey: "dashboard.documentationDesc", href: "/dashboard/docs" },
  { icon: LifeBuoy, labelKey: "dashboard.support", descriptionKey: "dashboard.supportDesc", href: "/dashboard/support" },
]

const docLinks = [
  { icon: Rocket, labelKey: "dashboard.gettingStarted", descriptionKey: "dashboard.gettingStartedDesc", href: "/docs/getting-started" },
  { icon: Map, labelKey: "dashboard.routePlanning", descriptionKey: "dashboard.routePlanningDesc", href: "/docs/route-planning" },
  { icon: Radio, labelKey: "dashboard.dispatch", descriptionKey: "dashboard.dispatchDesc", href: "/docs/dispatch" },
  { icon: Puzzle, labelKey: "dashboard.integrations", descriptionKey: "dashboard.integrationsDesc", href: "/docs/integrations" },
  { icon: Code, labelKey: "dashboard.apiReference", descriptionKey: "dashboard.apiReferenceDesc", href: "/docs/api-reference" },
]

export default function DashboardPage() {
  const { t } = useLocale()

  const { data: devices, isLoading: devicesLoading } = useDevices()
  const { data: tickets, isLoading: ticketsLoading } = useTickets()
  const { data: serviceStatus, isLoading: statusLoading } = useServiceStatus()
  const { data: changelog, isLoading: changelogLoading, isError: changelogError } = useChangelog()
  const { data: announcements, isLoading: announcementsLoading, isError: announcementsError } = useAnnouncements()
  const { data: company, isLoading: companyLoading } = useCompany()

  const deviceCount = devices?.length ?? 0
  const openTicketCount = tickets?.filter((t) => t.status === "open").length ?? 0

  const latestChangelogEntry = changelog?.[0]
  const latestRelease: Release | undefined = latestChangelogEntry
    ? {
        version: latestChangelogEntry.version,
        release_date: latestChangelogEntry.release_date,
        type: "app" as const,
        sections: latestChangelogEntry.sections.map((s) => ({
          title: s.type.charAt(0).toUpperCase() + s.type.slice(1),
          items: s.items,
        })),
      }
    : undefined

  const allServices = serviceStatus?.flatMap((g) => g.services) ?? []
  const anyOutage = allServices.some((s) => s.status === "outage")
  const anyDegraded = allServices.some((s) => s.status === "degraded")
  const portalStatusLabel = anyOutage ? "Outage" : anyDegraded ? "Degraded" : allServices.length > 0 ? "Active" : "Unknown"
  const portalStatusColor = anyOutage ? "text-red-600" : anyDegraded ? "text-yellow-600" : "text-green-600"
  const portalPingColor = anyOutage ? "bg-red-500" : anyDegraded ? "bg-yellow-500" : "bg-green-500"

  return (
    <>
      <Helmet><title>{t("common.dashboard")} — Operion ERP</title></Helmet>

      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h1 className="text-3xl font-bold tracking-tight">{t("dashboard.welcomeBack")}</h1>
          <p className="mt-2 text-muted-foreground">{t("dashboard.welcomeDesc")}</p>
        </motion.div>

        {/* Stats Row */}
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.05 }}
          >
            {devicesLoading ? (
              <div className="rounded-xl border bg-card p-6 shadow-sm">
                <Skeleton className="h-8 w-16" />
                <Skeleton className="mt-2 h-4 w-28" />
              </div>
            ) : (
              <StatCard value={String(deviceCount)} label={t("dashboard.registeredDevices")} icon={Smartphone} />
            )}
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            {ticketsLoading ? (
              <div className="rounded-xl border bg-card p-6 shadow-sm">
                <Skeleton className="h-8 w-16" />
                <Skeleton className="mt-2 h-4 w-24" />
              </div>
            ) : (
              <StatCard value={String(openTicketCount)} label={t("dashboard.openTickets")} icon={LayoutGrid} />
            )}
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 }}
          >
            {statusLoading ? (
              <div className="rounded-xl border bg-card p-6 shadow-sm">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="mt-3 h-5 w-16" />
              </div>
            ) : (
              <div className="rounded-xl border bg-card p-6 text-card-foreground shadow-sm transition-shadow hover:shadow-md h-full flex flex-col justify-between">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <p className="text-sm text-muted-foreground">{t("dashboard.onlinePortal")}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="relative flex h-2.5 w-2.5">
                        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${portalPingColor} opacity-75`} />
                        <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${portalPingColor}`} />
                      </span>
                      <span className={`text-sm font-semibold ${portalStatusColor}`}>{portalStatusLabel}</span>
                    </div>
                  </div>
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                    <Globe className="h-5 w-5" />
                  </div>
                </div>
              </div>
            )}
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
          >
            {changelogLoading ? (
              <div className="rounded-xl border bg-card p-6 shadow-sm">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="mt-3 h-6 w-20" />
              </div>
            ) : changelogError || !latestChangelogEntry ? (
              <div className="rounded-xl border bg-card p-6 text-card-foreground shadow-sm h-full flex flex-col justify-between">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <p className="text-sm text-muted-foreground">{t("dashboard.latestRelease")}</p>
                    <p className="text-sm text-muted-foreground">{t("dashboard.noReleaseData")}</p>
                  </div>
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                    <Rocket className="h-5 w-5" />
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border bg-card p-6 text-card-foreground shadow-sm transition-shadow hover:shadow-md h-full flex flex-col justify-between">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <p className="text-sm text-muted-foreground">{t("dashboard.latestRelease")}</p>
                    <p className="text-2xl font-bold tracking-tight">v{latestChangelogEntry.version}</p>
                    <p className="text-xs text-muted-foreground">{latestChangelogEntry.release_date}</p>
                  </div>
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-primary">
                    <Rocket className="h-5 w-5" />
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        </div>

        <Tabs defaultValue="overview" className="mt-10">
          <TabsList>
            <TabsTrigger value="overview">{t("dashboard.overview")}</TabsTrigger>
            <TabsTrigger value="activity">{t("dashboard.recentActivity")}</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-10">
            {/* Subscription Summary */}
            <div className="grid gap-6 md:grid-cols-3">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
              >
                {companyLoading ? (
                  <Card>
                    <CardHeader className="pb-3"><Skeleton className="h-4 w-32" /><Skeleton className="mt-2 h-5 w-40" /></CardHeader>
                    <CardContent><Skeleton className="h-5 w-16" /><Skeleton className="mt-2 h-4 w-36" /></CardContent>
                  </Card>
                ) : company?.subscription_tier ? (
                  <Card>
                    <CardHeader className="pb-3">
                      <CardDescription className="flex items-center gap-2">
                        <CreditCard className="h-4 w-4" /> {t("dashboard.subscription")}
                      </CardDescription>
                      <CardTitle className="text-lg">
                        {company.subscription_tier.charAt(0).toUpperCase() + company.subscription_tier.slice(1)} Plan
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Badge variant={company.is_active === false ? "secondary" : "success"}>
                        {company.is_active === false ? t("common.inactive") : t("common.active")}
                      </Badge>
                      <Button variant="link" className="mt-2 h-auto p-0" asChild>
                        <Link to="/dashboard/subscription">{t("dashboard.manageSubscription")} <ChevronRight className="ml-1 h-3 w-3" /></Link>
                      </Button>
                    </CardContent>
                  </Card>
                ) : (
                  <Card>
                    <CardContent className="p-6">
                      <EmptyState
                        icon={<CreditCard className="h-8 w-8" />}
                        title={t("dashboard.noSubscriptionData")}
                        description={t("dashboard.noSubscriptionDataDesc")}
                      />
                    </CardContent>
                  </Card>
                )}
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.15 }}
              >
                <Card>
                  <CardHeader className="pb-3">
                    <CardDescription className="flex items-center gap-2">
                      <Key className="h-4 w-4" /> {t("dashboard.license")}
                    </CardDescription>
                    <CardTitle className="text-lg">{t("dashboard.licensesUsed")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{t("dashboard.licensesAvailable")}</p>
                    <Button variant="link" className="mt-2 h-auto p-0" asChild>
                      <Link to="/dashboard/subscription">{t("dashboard.manageLicenses")} <ChevronRight className="ml-1 h-3 w-3" /></Link>
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
              >
                <Card>
                  <CardHeader className="pb-3">
                    <CardDescription className="flex items-center gap-2">
                      <Download className="h-4 w-4" /> {t("dashboard.latestVersion")}
                    </CardDescription>
                    <CardTitle className="text-lg">Operion {downloadConfig.latestVersion}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{t("dashboard.released")} {downloadConfig.releaseDate}</p>
                    <Button variant="link" className="mt-2 h-auto p-0" asChild>
                      <Link to="/dashboard/downloads">{t("common.download")} <ChevronRight className="ml-1 h-3 w-3" /></Link>
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* Quick Actions */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.25 }}
            >
              <h2 className="text-xl font-bold tracking-tight">{t("dashboard.quickActions")}</h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-3">
                {shortcuts.map((s) => (
                  <Link key={s.href} to={s.href}>
                    <Card className="h-full transition-shadow hover:shadow-md">
                      <CardContent className="flex items-center gap-4 p-5">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                          <s.icon className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium text-sm">{t(s.labelKey)}</p>
                          <p className="text-xs text-muted-foreground">{t(s.descriptionKey)}</p>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>
            </motion.div>

            {/* Two Column: Storage + Sessions */}
            <div className="grid gap-6 lg:grid-cols-2">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.3 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <HardDrive className="h-5 w-5" /> {t("dashboard.storageUsage")}
                    </CardTitle>
                    <CardDescription>{t("dashboard.storageDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <EmptyState
                      title={t("dashboard.noStorageData")}
                      description={t("dashboard.noStorageDataDesc")}
                    />
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.35 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Activity className="h-5 w-5" /> {t("dashboard.activeSessions")}
                    </CardTitle>
                    <CardDescription>{t("dashboard.sessionsDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <EmptyState
                      title={t("dashboard.noSessionData")}
                      description={t("dashboard.noSessionDataDesc")}
                    />
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* Documentation Shortcuts */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.4 }}
            >
              <h2 className="text-xl font-bold tracking-tight">{t("dashboard.documentation")}</h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                {docLinks.map((d) => (
                  <a key={d.href} href={d.href}>
                    <Card className="h-full transition-shadow hover:shadow-md">
                      <CardContent className="flex flex-col items-start gap-3 p-5">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                          <d.icon className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium text-sm">{t(d.labelKey)}</p>
                          <p className="text-xs text-muted-foreground">{t(d.descriptionKey)}</p>
                        </div>
                      </CardContent>
                    </Card>
                  </a>
                ))}
              </div>
            </motion.div>

            {/* Latest Release Highlight */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.45 }}
            >
              <h2 className="text-xl font-bold tracking-tight">{t("dashboard.latestRelease")}</h2>
              <div className="mt-4">
                {changelogLoading ? (
                  <Card>
                    <CardContent className="p-5 space-y-3">
                      <Skeleton className="h-5 w-48" />
                      <Skeleton className="h-4 w-32" />
                      <Skeleton className="h-4 w-full" />
                      <Skeleton className="h-4 w-3/4" />
                    </CardContent>
                  </Card>
                ) : changelogError || !latestRelease ? (
                  <Card>
                    <CardContent className="p-6">
                      <EmptyState
                        title={t("dashboard.noReleaseData")}
                        description={t("dashboard.noReleaseDataDesc")}
                      />
                    </CardContent>
                  </Card>
                ) : (
                  <ReleaseCard release={latestRelease} />
                )}
              </div>
            </motion.div>

            {/* Announcements */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.5 }}
            >
              <h2 className="text-xl font-bold tracking-tight">{t("dashboard.announcements")}</h2>
              <div className="mt-4 space-y-3">
                {announcementsLoading ? (
                  <>
                    <Card><CardContent className="p-5"><Skeleton className="h-5 w-64" /><Skeleton className="mt-2 h-4 w-full" /><Skeleton className="mt-2 h-3 w-24" /></CardContent></Card>
                    <Card><CardContent className="p-5"><Skeleton className="h-5 w-56" /><Skeleton className="mt-2 h-4 w-full" /><Skeleton className="mt-2 h-3 w-24" /></CardContent></Card>
                  </>
                ) : announcementsError ? (
                  <Card>
                    <CardContent className="p-6">
                      <EmptyState
                        icon={<AlertTriangle className="h-8 w-8" />}
                        title={t("dashboard.failedLoadAnnouncements")}
                        description={t("dashboard.failedLoadAnnouncementsDesc")}
                      />
                    </CardContent>
                  </Card>
                ) : !announcements || announcements.length === 0 ? (
                  <Card>
                    <CardContent className="p-6">
                      <EmptyState
                        icon={<Megaphone className="h-8 w-8" />}
                        title={t("dashboard.noAnnouncements")}
                        description={t("dashboard.noAnnouncementsDesc")}
                      />
                    </CardContent>
                  </Card>
                ) : (
                  announcements.map((a) => (
                    <Card key={a.id}>
                      <CardContent className="p-5">
                        <div className="flex items-start gap-3">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent">
                            <Megaphone className="h-4 w-4 text-primary" />
                          </div>
                          <div>
                            <h3 className="font-semibold text-sm">{a.title}</h3>
                            <p className="mt-1 text-xs text-muted-foreground">{a.content}</p>
                            <p className="mt-2 text-xs text-muted-foreground/60">{a.published_at}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </motion.div>
          </TabsContent>

          <TabsContent value="activity" className="space-y-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
            >
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Clock className="h-5 w-5" /> {t("dashboard.recentActivity")}
                  </CardTitle>
                  <CardDescription>{t("dashboard.activityDesc")}</CardDescription>
                </CardHeader>
                <CardContent>
                  <EmptyState
                    title={t("dashboard.noActivity")}
                    description={t("dashboard.noActivityDesc")}
                  />
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>
        </Tabs>
      </SectionWrapper>
    </>
  )
}
