import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { Bell, ChevronRight, Package, Monitor, HardDrive, Cpu, ExternalLink } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Callout } from "@/components/ui/callout"
import { downloadConfig } from "@/config/site"
import { useLocale } from "@/i18n/locale-context"
import { trackCTAClick } from "@/services/analytics"

export default function DashboardDownloadsPage() {
  const { t } = useLocale()
  return (
    <>
      <Helmet><title>{t("dashboard.downloadsTitle")}</title></Helmet>
      <SectionWrapper>
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h1 className="text-3xl font-bold tracking-tight">{t("dashboard.downloads")}</h1>
          <p className="mt-2 text-muted-foreground">{t("dashboard.downloadDesc")}</p>
        </motion.div>

        <div className="mt-8 grid gap-8 lg:grid-cols-3">
          {/* Desktop Installer — Pre-release / Waitlist */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }} className="lg:col-span-2">
            <Card className="border-primary/30 bg-muted/20">
              <CardContent className="p-8">
                <div className="flex flex-col items-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-6">
                    <Bell className="h-8 w-8 text-primary" />
                  </div>
                  <Badge variant="secondary" className="mb-3">{t("dashboard.prerelease")}</Badge>
                  <h2 className="text-2xl font-bold">{t("dashboard.erpComingSoon")}</h2>
                  <p className="mt-3 max-w-md text-sm text-muted-foreground">
                    {t("dashboard.erpInDevelopment")}
                  </p>
                  <Callout variant="info" className="mt-4 max-w-md text-left">
                    <p className="text-sm">
                      <strong>{t("dashboard.minRequirements")}:</strong>{" "}
                      {t("dashboard.minRequirementsList")}
                    </p>
                  </Callout>
                  <div className="mt-6 flex flex-col items-center gap-3 sm:flex-row">
                    <Button size="xl" asChild>
                      <Link to="/waitlist" onClick={() => trackCTAClick("downloads", "/dashboard/downloads")}>
                        <Bell className="mr-2 h-4 w-4" />
                        {t("dashboard.joinWaitlist")}
                      </Link>
                    </Button>
                    <Button variant="outline" size="xl" asChild>
                      <a href="mailto:contact@operionerp.xyz?subject=Early%20access%20request%20—%20Operion%20ERP%20desktop%20app">
                        <ExternalLink className="mr-2 h-4 w-4" />
                        {t("dashboard.contactUs")}
                      </a>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* System Requirements */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t("dashboard.systemRequirements")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  { icon: Monitor, label: t("dashboard.reqOs"), val: downloadConfig.systemRequirements.os[0] },
                  { icon: Cpu, label: t("dashboard.reqProcessor"), val: "Intel Core i5+" },
                  { icon: HardDrive, label: t("dashboard.reqRamStorage"), val: "8 GB (16 GB rec.)" },
                ].map((r) => (
                  <div key={r.label} className="flex items-center gap-2 text-sm">
                    <r.icon className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">{r.label}:</span>
                    <span className="font-medium">{r.val}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </motion.div>

          {/* Previous Versions */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t("dashboard.previousVersions")}</CardTitle>
                <CardDescription>{t("dashboard.earlierReleases")}</CardDescription>
              </CardHeader>
              <CardContent>
                <EmptyState title={t("dashboard.noPrevVersions")} description={t("dashboard.prevReleases")} />
              </CardContent>
            </Card>
          </motion.div>

          {/* Toolkit */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.25 }}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><Package className="h-4 w-4" /> {t("dashboard.toolkit")}</CardTitle>
                <CardDescription>{t("dashboard.toolkitDesc")}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center">
                  <Package className="mx-auto h-8 w-8 text-muted-foreground/40" />
                  <p className="mt-3 text-sm font-medium">{t("common.comingSoon")}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{t("dashboard.toolkitSoon")}</p>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Release Notes */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.3 }}>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t("dashboard.releaseNotes")}</CardTitle>
                <CardDescription>{t("dashboard.releaseNotesSoon")}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{t("dashboard.releaseNotesBody")}</p>
                <Button variant="link" className="mt-2 h-auto p-0" asChild>
                  <Link to="/download">{t("dashboard.viewFullReleaseNotes")} <ChevronRight className="ml-1 h-3 w-3" /></Link>
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>
    </>
  )
}
