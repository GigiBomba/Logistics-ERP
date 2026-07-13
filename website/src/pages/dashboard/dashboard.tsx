import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { Download, BookOpen, LifeBuoy, ChevronRight, CreditCard, Key, Megaphone, Activity, HardDrive, Globe, Zap, FileText, Map, Radio, Puzzle, Code, Rocket, Clock, Shield, CheckCircle2 } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { ReleaseCard } from "@/components/shared/release-card"
import { StatCard } from "@/components/shared/stat-card"
import { downloadConfig } from "@/config/site"
import type { Release } from "@/components/shared/release-card"
import { useLocale } from "@/i18n/locale-context"

const shortcuts = [
  { icon: Download, labelKey: "dashboard.downloads", descriptionKey: "dashboard.downloadsDesc", href: "/dashboard/downloads" },
  { icon: BookOpen, labelKey: "dashboard.documentation", descriptionKey: "dashboard.documentationDesc", href: "/dashboard/docs" },
  { icon: LifeBuoy, labelKey: "dashboard.support", descriptionKey: "dashboard.supportDesc", href: "/dashboard/support" },
]

const announcements = [
  { title: "Operion 1.0 launching September 2026", date: "July 2026", description: "We're preparing for our first major release. Early access available for beta testers." },
  { title: "New documentation center now live", date: "June 2026", description: "Explore our comprehensive guides, tutorials, and API references." },
]

const activities = [
  { icon: CheckCircle2, text: "You logged in from Bucharest, Romania", time: "2 minutes ago", type: "success" as const },
  { icon: Zap, text: "New release v1.0.0 is available for download", time: "3 hours ago", type: "info" as const },
  { icon: Shield, text: "Security alert: password changed successfully", time: "2 days ago", type: "warning" as const },
  { icon: CreditCard, text: "Subscription renewed — Professional Plan", time: "5 days ago", type: "success" as const },
  { icon: FileText, text: "Invoice #INV-2026-001 paid", time: "1 week ago", type: "success" as const },
]

const docLinks = [
  { icon: Rocket, labelKey: "dashboard.gettingStarted", descriptionKey: "dashboard.gettingStartedDesc", href: "/docs/getting-started" },
  { icon: Map, labelKey: "dashboard.routePlanning", descriptionKey: "dashboard.routePlanningDesc", href: "/docs/route-planning" },
  { icon: Radio, labelKey: "dashboard.dispatch", descriptionKey: "dashboard.dispatchDesc", href: "/docs/dispatch" },
  { icon: Puzzle, labelKey: "dashboard.integrations", descriptionKey: "dashboard.integrationsDesc", href: "/docs/integrations" },
  { icon: Code, labelKey: "dashboard.apiReference", descriptionKey: "dashboard.apiReferenceDesc", href: "/docs/api-reference" },
]

const latestRelease: Release = {
  version: "1.0.0",
  release_date: "2026-09-01",
  type: "app",
  size_mb: 245,
  downloads_url: "/dashboard/downloads",
  sections: [
    {
      title: "New Features",
      items: [
        "Fleet management dashboard with real-time tracking",
        "Advanced route optimization with multi-stop support",
        "Dispatch console for live coordination",
      ],
    },
    {
      title: "Improvements",
      items: [
        "Improved performance for large vehicle fleets",
        "Enhanced reporting with exportable PDF summaries",
        "Better integration with third-party logistics providers",
      ],
    },
  ],
}

export default function DashboardPage() {
  const { t } = useLocale()
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
            <StatCard value="5" label={t("dashboard.activeLicenses")} icon={Key} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <StatCard value="12" label={t("dashboard.teamMembers")} icon={Globe} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 }}
          >
            <StatCard value="3" label={t("dashboard.activeSessions")} icon={Activity} trend={{ direction: "up", value: "+1" }} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
          >
            <StatCard value="2.3 GB" label={t("dashboard.storageUsed")} icon={HardDrive} trend={{ direction: "up", value: "+0.4 GB" }} />
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
                <Card>
                  <CardHeader className="pb-3">
                    <CardDescription className="flex items-center gap-2">
                      <CreditCard className="h-4 w-4" /> {t("dashboard.subscription")}
                    </CardDescription>
                    <CardTitle className="text-lg">{t("dashboard.professionalPlan")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Badge variant="success">{t("common.active")}</Badge>
                    <p className="mt-2 text-sm text-muted-foreground">{t("dashboard.renewsOn")} Sep 1, 2026</p>
                    <Button variant="link" className="mt-2 h-auto p-0" asChild>
                      <Link to="/dashboard/subscription">{t("dashboard.manageSubscription")} <ChevronRight className="ml-1 h-3 w-3" /></Link>
                    </Button>
                  </CardContent>
                </Card>
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
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("dashboard.used")}</span>
                      <span className="font-medium">2.3 GB / 10 GB</span>
                    </div>
                    <Progress value={23} />
                    <p className="text-xs text-muted-foreground">{t("dashboard.storageWarning")}</p>
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
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
                          <Globe className="h-4 w-4 text-primary" />
                        </div>
                        <div>
                          <p className="text-sm font-medium">{t("dashboard.sessionCount")}</p>
                          <p className="text-xs text-muted-foreground">Windows · Chrome · Bucharest</p>
                        </div>
                      </div>
                      <Badge variant="success">{t("common.current")}</Badge>
                    </div>
                    <Button variant="outline" size="sm" className="w-full" asChild>
                      <Link to="/dashboard/profile">{t("dashboard.manageSessions")}</Link>
                    </Button>
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
                <ReleaseCard release={latestRelease} />
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
                {announcements.map((a) => (
                  <Card key={a.title}>
                    <CardContent className="p-5">
                      <div className="flex items-start gap-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent">
                          <Megaphone className="h-4 w-4 text-primary" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-sm">{a.title}</h3>
                          <p className="mt-1 text-xs text-muted-foreground">{a.description}</p>
                          <p className="mt-2 text-xs text-muted-foreground/60">{a.date}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
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
                  <div className="space-y-0">
                    {activities.map((activity, i) => (
                      <div
                        key={i}
                        className="relative flex gap-4 pb-6 last:pb-0"
                      >
                        {!activities[i + 1] ? null : (
                          <div className="absolute left-[15px] top-8 h-full w-px bg-border" />
                        )}
                        <div className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent">
                          <activity.icon className="h-4 w-4 text-primary" />
                        </div>
                        <div className="flex-1 space-y-1 pt-0.5">
                          <p className="text-sm font-medium">{activity.text}</p>
                          <p className="text-xs text-muted-foreground">{activity.time}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>
        </Tabs>
      </SectionWrapper>
    </>
  )
}
