import { useState } from "react"
import { motion } from "motion/react"
import { SeoHead } from "@/components/seo/seo-head"
import { useLocale } from "@/i18n/locale-context"
import {
  Activity,
  Shield,
  Lock,
  Eye,
  Clock,
  Server,
  Network,
  Radar,
  Fingerprint,
  Search,
  HardDrive,
  Database,
  Trash2,
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
import { FaqAccordion } from "@/components/shared/faq-accordion"
import { Callout } from "@/components/ui/callout"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { CtaBanner } from "@/components/shared/cta-banner"

const trustFaq = [
  {
    questionKey: "trustCenter.faq1.q",
    answerKey: "trustCenter.faq1.a",
  },
  {
    questionKey: "trustCenter.faq2.q",
    answerKey: "trustCenter.faq2.a",
  },
  {
    questionKey: "trustCenter.faq3.q",
    answerKey: "trustCenter.faq3.a",
  },
  {
    questionKey: "trustCenter.faq4.q",
    answerKey: "trustCenter.faq4.a",
  },
  {
    questionKey: "trustCenter.faq5.q",
    answerKey: "trustCenter.faq5.a",
  },
]

export default function TrustCenterPage() {
  const { t } = useLocale()
  const [activeTab, setActiveTab] = useState("infrastructure")
  const faqItems = trustFaq.map((faq) => ({
    question: t(faq.questionKey),
    answer: t(faq.answerKey),
  }))

  return (
    <>
      <SeoHead title={t("trustCenter.pageTitle")} description={t("trustCenter.metaDesc")} canonical="https://operionerp.xyz/trust-center" />

      <HeroSection
        title={t("trust.title")}
        description={t("trustCenter.heroDesc")}
        align="center"
        size="large"
      />

      {/* Stats Banner */}
      <SectionWrapper className="pt-0">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-5xl"
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard value={t("trust.stat1.value")} label={t("trust.stat1.label")} icon={Eye} />
            <StatCard value={t("trust.stat2.value")} label={t("trust.stat2.label")} icon={HardDrive} />
            <StatCard value={t("trustCenter.stat3.value")} label={t("trustCenter.stat3.label")} icon={Activity} />
            <StatCard value={t("trust.stat3.value")} label={t("trust.stat3.label")} icon={Clock} />
          </div>
        </motion.div>
      </SectionWrapper>

      {/* Tabs Section */}
      <SectionWrapper className="bg-muted/30">
        <div className="mx-auto max-w-5xl">
          <Tabs defaultValue="infrastructure" value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-8 flex w-full flex-wrap justify-center gap-1">
              <TabsTrigger value="infrastructure">{t("trustCenter.tab.infrastructure")}</TabsTrigger>
              <TabsTrigger value="security">{t("trust.security")}</TabsTrigger>
              <TabsTrigger value="compliance">{t("trust.compliance")}</TabsTrigger>
              <TabsTrigger value="privacy">{t("trust.privacy")}</TabsTrigger>
              <TabsTrigger value="reliability">{t("trustCenter.tab.reliability")}</TabsTrigger>
            </TabsList>

            {/* Infrastructure */}
            <TabsContent value="infrastructure">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                  <FeatureCard
                    icon={Server}
                    title={t("trustCenter.infrastructure1.title")}
                    description={t("trustCenter.infrastructure1.desc")}
                    index={0}
                  />
                  <FeatureCard
                    icon={Network}
                    title={t("trustCenter.infrastructure2.title")}
                    description={t("trustCenter.infrastructure2.desc")}
                    index={1}
                  />
                  <FeatureCard
                    icon={Radar}
                    title={t("trustCenter.infrastructure3.title")}
                    description={t("trustCenter.infrastructure3.desc")}
                    index={2}
                  />
                  <FeatureCard
                    icon={HardDrive}
                    title={t("trustCenter.infrastructure4.title")}
                    description={t("trustCenter.infrastructure4.desc")}
                    index={3}
                  />
                </div>
                <div className="mt-8">
                  <Callout variant="info" title={t("trustCenter.infrastructureStatus")}>
                    <p>
                      {t("trustCenter.infrastructureStatusDesc")}
                    </p>
                  </Callout>
                </div>
              </motion.div>
            </TabsContent>

            {/* Security */}
            <TabsContent value="security">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="grid gap-6 sm:grid-cols-2">
                  <Card className="h-full">
                    <CardContent className="p-6">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-4">
                        <Lock className="h-5 w-5 text-primary" />
                      </div>
                      <h3 className="font-semibold">{t("trustCenter.security1.title")}</h3>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {t("trustCenter.security1.desc")}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="h-full">
                    <CardContent className="p-6">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-4">
                        <Fingerprint className="h-5 w-5 text-primary" />
                      </div>
                      <h3 className="font-semibold">{t("trustCenter.security2.title")}</h3>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {t("trustCenter.security2.desc")}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="h-full">
                    <CardContent className="p-6">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-4">
                        <Shield className="h-5 w-5 text-primary" />
                      </div>
                      <h3 className="font-semibold">{t("trustCenter.security3.title")}</h3>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {t("trustCenter.security3.desc")}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="h-full">
                    <CardContent className="p-6">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-4">
                        <Search className="h-5 w-5 text-primary" />
                      </div>
                      <h3 className="font-semibold">{t("trustCenter.security4.title")}</h3>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {t("trustCenter.security4.desc")}
                      </p>
                    </CardContent>
                  </Card>
                </div>

                {/* Security Features Table */}
                <div className="mt-10">
                  <h3 className="mb-6 text-lg font-semibold tracking-tight">{t("security.featuresTitle")}</h3>
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
                </div>
              </motion.div>
            </TabsContent>

            {/* Compliance */}
            <TabsContent value="compliance">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <Card>
                  <CardContent className="p-8 text-center">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 mb-6">
                      <Shield className="h-7 w-7 text-primary" />
                    </div>
                    <h3 className="text-lg font-semibold tracking-tight mb-3">{t("trust.complianceTitle")}</h3>
                    <p className="text-muted-foreground max-w-lg mx-auto">
                      {t("trust.complianceText")}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            </TabsContent>

            {/* Privacy */}
            <TabsContent value="privacy">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="grid gap-6 sm:grid-cols-2 mb-8">
                  <Card className="h-full">
                    <CardContent className="p-6">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-4">
                        <Database className="h-5 w-5 text-primary" />
                      </div>
                      <h3 className="font-semibold">{t("trustCenter.privacy1.title")}</h3>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {t("trustCenter.privacy1.desc")}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="h-full">
                    <CardContent className="p-6">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-4">
                        <Eye className="h-5 w-5 text-primary" />
                      </div>
                      <h3 className="font-semibold">{t("trustCenter.privacy2.title")}</h3>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {t("trustCenter.privacy2.desc")}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="h-full">
                    <CardContent className="p-6">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-4">
                        <Clock className="h-5 w-5 text-primary" />
                      </div>
                      <h3 className="font-semibold">{t("trustCenter.privacy3.title")}</h3>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {t("trustCenter.privacy3.desc")}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="h-full">
                    <CardContent className="p-6">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-4">
                        <Trash2 className="h-5 w-5 text-primary" />
                      </div>
                      <h3 className="font-semibold">{t("trustCenter.privacy4.title")}</h3>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {t("trustCenter.privacy4.desc")}
                      </p>
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardContent className="p-8 text-center">
                    <p className="text-muted-foreground">
                      {t("trust.subprocessorsText")}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            </TabsContent>

            {/* Reliability */}
            <TabsContent value="reliability">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <Card>
                  <CardContent className="p-8 text-center">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 mb-6">
                      <Activity className="h-7 w-7 text-primary" />
                    </div>
                    <h3 className="text-lg font-semibold tracking-tight mb-3">{t("trustCenter.reliability.title")}</h3>
                    <p className="text-muted-foreground max-w-lg mx-auto">
                      {t("trustCenter.reliability.desc")}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            </TabsContent>
          </Tabs>
        </div>
      </SectionWrapper>

      {/* FAQ */}
      <SectionWrapper>
        <SectionHeader
          title={t("trustCenter.faqTitle")}
          description={t("trustCenter.faqDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <FaqAccordion items={faqItems} />
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
          <Callout variant="warning" title={t("trust.reportVuln")}>
            <p className="mb-3">
              {t("trust.reportVulnText1")}{" "}
              <a href="mailto:security@operionerp.xyz" className="underline underline-offset-4">
                security@operionerp.xyz
              </a>
              {t("trust.reportVulnText2")}
            </p>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">{t("trust.badge48h")}</Badge>
              <Badge variant="secondary">{t("trust.badgeSafeHarbor")}</Badge>
              <Badge variant="secondary">{t("trust.badgeNoLegal")}</Badge>
            </div>
          </Callout>
        </motion.div>
      </SectionWrapper>

      {/* CTA Banner */}
      <SectionWrapper className="pb-24">
        <CtaBanner
          title={t("trustCenter.ctaTitle")}
          description={t("trustCenter.ctaDesc")}
          buttonText={t("trustCenter.ctaButton")}
          buttonHref="mailto:security@operionerp.xyz"
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}


