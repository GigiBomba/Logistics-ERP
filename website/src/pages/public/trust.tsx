import { Link } from "react-router"
import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import {
  Activity,
  Shield,
  Lock,
  Eye,
  FileCheck,
  Clock,
  Bug,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Fingerprint,
  Search,
  Users,
  Cookie,
  Bot,
  Key,
  FileSearch,
  Wifi,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { FeatureCard } from "@/components/shared/feature-card"
import { StatCard } from "@/components/shared/stat-card"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { CtaBanner } from "@/components/shared/cta-banner"

const securityOverview = [
  {
    icon: Lock,
    titleKey: "trust.securityOverview1.title",
    descKey: "trust.securityOverview1.desc",
  },
  {
    icon: Fingerprint,
    titleKey: "trust.securityOverview2.title",
    descKey: "trust.securityOverview2.desc",
  },
  {
    icon: Eye,
    titleKey: "trust.securityOverview3.title",
    descKey: "trust.securityOverview3.desc",
  },
  {
    icon: Search,
    titleKey: "trust.securityOverview4.title",
    descKey: "trust.securityOverview4.desc",
  },
]

const privacyItems = [
  { titleKey: "trust.privacy1.title", descKey: "trust.privacy1.desc" },
  { titleKey: "trust.privacy2.title", descKey: "trust.privacy2.desc" },
  { titleKey: "trust.privacy3.title", descKey: "trust.privacy3.desc" },
  { titleKey: "trust.privacy4.title", descKey: "trust.privacy4.desc" },
]

export default function TrustPage() {
  const { t } = useLocale()
  return (
    <>
      <SeoHead title={t("trust.pageTitle")} description={t("trust.pageDesc")} canonical="https://operionerp.xyz/trust" />

      <HeroSection
        title={t("trust.title")}
        description={t("trust.heroDesc")}
        align="center"
        size="large"
      />

      {/* Development Status */}
      <SectionWrapper>
        <SectionHeader
          title={t("trust.development")}
          description={t("trust.developmentDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <div className="grid gap-6 sm:grid-cols-3">
            <StatCard
              value={t("trust.stat1.value")}
              label={t("trust.stat1.label")}
              icon={Activity}
            />
            <StatCard
              value={t("trust.stat2.value")}
              label={t("trust.stat2.label")}
              icon={Lock}
            />
            <StatCard
              value={t("trust.stat3.value")}
              label={t("trust.stat3.label")}
              icon={Clock}
            />
          </div>
        </motion.div>
      </SectionWrapper>

      {/* Security */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("trust.security")}
          description={t("trust.securityDesc")}
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {securityOverview.map((item, i) => (
            <FeatureCard key={item.titleKey} icon={item.icon} title={t(item.titleKey)} description={t(item.descKey)} index={i} />
          ))}
        </div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto mt-10 max-w-2xl text-center"
        >
          <Button variant="outline" asChild>
            <Link to="/security">
              <Shield className="mr-2 h-4 w-4" />
              {t("trust.exploreSecurity")}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </motion.div>
      </SectionWrapper>

      {/* Security Features Table */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("security.featuresTitle")}
          description={t("security.featuresDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-5xl"
        >
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="px-5 py-4 text-left font-semibold text-muted-foreground">{t("security.features.table.feature")}</th>
                      <th className="px-5 py-4 text-left font-semibold text-muted-foreground">{t("security.features.table.status")}</th>
                      <th className="px-5 py-4 text-left font-semibold text-muted-foreground">{t("security.features.table.management")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {([
                      { icon: Fingerprint, featureKey: "security.features.mfa", descKey: "security.features.mfaDesc", manageKey: "security.features.mfaManage" },
                      { icon: Users, featureKey: "security.features.rbac", descKey: "security.features.rbacDesc", manageKey: "security.features.rbacManage" },
                      { icon: Cookie, featureKey: "security.features.cookies", descKey: "security.features.cookiesDesc", manageKey: "security.features.cookiesManage" },
                      { icon: Bot, featureKey: "security.features.bot", descKey: "security.features.botDesc", manageKey: "security.features.botManage" },
                      { icon: Shield, featureKey: "security.features.headers", descKey: "security.features.headersDesc", manageKey: "security.features.headersManage" },
                      { icon: Key, featureKey: "security.features.tokens", descKey: "security.features.tokensDesc", manageKey: "security.features.tokensManage" },
                      { icon: FileSearch, featureKey: "security.features.audit", descKey: "security.features.auditDesc", manageKey: "security.features.auditManage" },
                      { icon: Wifi, featureKey: "security.features.api", descKey: "security.features.apiDesc", manageKey: "security.features.apiManage" },
                    ]).map((row, i) => {
                      const Icon = row.icon
                      return (
                        <tr key={row.featureKey} className={i < 7 ? "border-b border-border" : ""}>
                          <td className="px-5 py-4">
                            <div className="flex items-start gap-3">
                              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                                <Icon className="h-4 w-4 text-primary" />
                              </div>
                              <div>
                                <p className="font-medium text-foreground">{t(row.featureKey)}</p>
                                <p className="mt-1 text-xs text-muted-foreground leading-relaxed">{t(row.descKey)}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-5 py-4 align-middle">
                            <Badge variant="default" className="bg-green-600/15 text-green-700 dark:text-green-400 hover:bg-green-600/20">{t("security.statusActive")}</Badge>
                          </td>
                          <td className="px-5 py-4 align-middle text-sm text-muted-foreground">{t(row.manageKey)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Privacy */}
      <SectionWrapper>
        <SectionHeader
          title={t("trust.privacy")}
          description={t("trust.privacyDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <Card>
            <CardContent className="p-6">
              <div className="space-y-6">
                {privacyItems.map((item) => (
                  <div key={item.titleKey} className="flex gap-4">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
                      <CheckCircle2 className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-sm">{t(item.titleKey)}</h3>
                      <p className="mt-1 text-sm text-muted-foreground">{t(item.descKey)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          <div className="mt-8 text-center">
            <Button variant="outline" asChild>
              <Link to="/privacy">
                {t("trust.readPrivacy")}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </motion.div>
      </SectionWrapper>

      {/* Data Processing Agreement */}
      <SectionWrapper id="dpa" className="bg-muted/30">
        <SectionHeader
          title={t("trust.dpaTitle")}
          description=""
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <Card>
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <FileCheck className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold">{t("trust.dpaTitle")}</h3>
                  <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                    {t("trust.dpaContent")}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Data Retention */}
      <SectionWrapper>
        <SectionHeader
          title={t("trust.dataRetention")}
          description={t("trust.dataRetentionDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="px-6 py-3 text-left font-semibold text-muted-foreground">{t("trust.retentionDataType")}</th>
                      <th className="px-6 py-3 text-left font-semibold text-muted-foreground">{t("trust.retentionPeriod")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {([
                      { dataKey: "trust.retentionAccountData", periodKey: "trust.retentionAccountPeriod" },
                      { dataKey: "trust.retentionAuditLogs", periodKey: "trust.retentionAuditPeriod" },
                      { dataKey: "trust.retentionBackup", periodKey: "trust.retentionBackupPeriod" },
                      { dataKey: "trust.retentionDeleted", periodKey: "trust.retentionDeletedPeriod" },
                    ]).map((row, i) => (
                      <tr key={row.dataKey} className={i < 3 ? "border-b border-border" : ""}>
                        <td className="px-6 py-3 text-foreground font-medium">{t(row.dataKey)}</td>
                        <td className="px-6 py-3 text-muted-foreground">{t(row.periodKey)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Compliance */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("trust.compliance")}
          description={t("trust.complianceDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl"
        >
          <Card>
            <CardContent className="p-8 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 mb-6">
                <FileCheck className="h-7 w-7 text-primary" />
              </div>
              <h3 className="text-lg font-semibold tracking-tight mb-3">{t("trust.complianceTitle")}</h3>
              <p className="text-muted-foreground">
                {t("trust.complianceText")}
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Incident History */}
      <SectionWrapper>
        <SectionHeader
          title={t("trust.incidents")}
          description={t("trust.incidentsDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl"
        >
          <Card className="border-dashed">
            <CardContent className="p-10 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="mt-6 text-xl font-semibold tracking-tight">{t("trust.noIncidents")}</h3>
              <p className="mt-3 text-muted-foreground max-w-md mx-auto">
                {t("trust.noIncidentsDesc")}
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Audit Reports */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("trust.audits")}
          description={t("trust.auditsDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center"
        >
          <Card>
            <CardContent className="p-8">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <FileCheck className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="mt-4 text-lg font-semibold">{t("trust.comingBeforeLaunch")}</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {t("trust.auditsText")}
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Subprocessors */}
      <SectionWrapper>
        <SectionHeader
          title={t("trust.subprocessors")}
          description={t("trust.subprocessorsDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <Card>
            <CardContent className="p-8 text-center">
              <p className="text-muted-foreground">
                {t("trust.subprocessorsText")}
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Responsible Disclosure */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("trust.disclosure")}
          description={t("trust.disclosureDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <Card>
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900/30">
                  <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <h3 className="font-semibold">{t("trust.reportVuln")}</h3>
                  <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                    {t("trust.reportVulnText1")}{" "}
                    <a href="mailto:security@operionerp.xyz" className="underline underline-offset-4">
                      security@operionerp.xyz
                    </a>
                    {t("trust.reportVulnText2")}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Badge variant="secondary">{t("trust.badge48h")}</Badge>
                    <Badge variant="secondary">{t("trust.badgeSafeHarbor")}</Badge>
                    <Badge variant="secondary">{t("trust.badgeNoLegal")}</Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          <div className="mt-8 text-center">
            <Button variant="outline" asChild>
              <Link to="/security">
                <Bug className="mr-2 h-4 w-4" />
                {t("trust.fullSecurityDetails")}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </motion.div>
      </SectionWrapper>

      <SectionWrapper className="pb-24">
        <CtaBanner
          title={t("trust.ctaTitle")}
          description={t("trust.ctaDesc")}
          buttonText={t("trust.ctaButton")}
          buttonHref="mailto:security@operionerp.xyz"
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
