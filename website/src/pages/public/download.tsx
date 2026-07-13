import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { Download, Monitor, HardDrive, Cpu, Shield, ArrowLeftRight, BookOpen, Wrench, Zap, Mail } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Callout } from "@/components/ui/callout"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { CtaBanner } from "@/components/shared/cta-banner"
import { downloadConfig, toolkitConfig } from "@/config/site"

export default function DownloadPage() {
  const { t } = useLocale()
  const [activeTab, setActiveTab] = useState("stable")
  const [betaEmail, setBetaEmail] = useState("")

  return (
    <>
      <Helmet>
        <title>{t("download.pageTitle")}</title>
        <meta name="description" content={t("download.metaDesc")} />
        <link rel="canonical" href="https://operion.com/download" />
      </Helmet>
      <PageHeader
        title={t("download.title")}
        description={t("download.headerDesc")}
      />

      {/* Primary Download */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl"
        >
          <Card className="border-primary/30 bg-muted/30">
            <CardContent className="p-8">
              <div className="flex flex-col items-center text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-6">
                  <Download className="h-8 w-8 text-primary" />
                </div>
                <Badge variant="success" className="mb-3">{t("download.latestRelease")}</Badge>
                <h2 className="text-2xl font-bold">Operion ERP {downloadConfig.latestVersion}</h2>
                <p className="mt-2 text-sm text-muted-foreground">{t("download.released")} {downloadConfig.releaseDate}</p>
                <p className="mt-1 text-sm text-muted-foreground">{downloadConfig.fileSize} — {t("download.winRequirement")}</p>
                <Button size="xl" className="mt-6" disabled>
                  <Download className="mr-2 h-4 w-4" />
                  {t("download.notAvailable")}
                </Button>
                <p className="mt-4 text-xs text-muted-foreground">{t("download.otherOs")}</p>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* System Requirements */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center mb-12"
        >
          <h2 className="text-3xl font-bold tracking-tight">{t("download.systemRequirements")}</h2>
        </motion.div>
        <div className="mx-auto max-w-3xl grid gap-4 sm:grid-cols-2">
          {[
            { icon: Monitor, labelKey: "download.reqOs", value: downloadConfig.systemRequirements.os.join(", ") },
            { icon: Cpu, labelKey: "download.reqProcessor", value: downloadConfig.systemRequirements.processor },
            { icon: HardDrive, labelKey: "download.reqRamStorage", value: `${downloadConfig.systemRequirements.ram}, ${downloadConfig.systemRequirements.storage}` },
            { icon: Shield, labelKey: "download.reqAdditional", value: downloadConfig.systemRequirements.additional },
          ].map((req, i) => (
            <motion.div
              key={req.labelKey}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="h-full">
                <CardContent className="flex gap-3 p-5">
                  <req.icon className="mt-0.5 h-5 w-5 text-muted-foreground shrink-0" />
                  <div>
                    <p className="text-sm font-medium">{t(req.labelKey)}</p>
                    <p className="text-xs text-muted-foreground">{req.value}</p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Installation Instructions */}
      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-10"
          >
            <h2 className="text-3xl font-bold tracking-tight">{t("download.installation")}</h2>
            <p className="mt-2 text-muted-foreground">{t("download.installationDesc")}</p>
          </motion.div>
          <div className="space-y-6">
            {[
              { step: 1, titleKey: "download.installStep1Title", descKey: "download.installStep1Desc" },
              { step: 2, titleKey: "download.installStep2Title", descKey: "download.installStep2Desc" },
              { step: 3, titleKey: "download.installStep3Title", descKey: "download.installStep3Desc" },
              { step: 4, titleKey: "download.installStep4Title", descKey: "download.installStep4Desc" },
            ].map((item) => (
              <motion.div
                key={item.step}
                initial={{ opacity: 0, x: -10 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: item.step * 0.1 }}
              >
                <Card>
                  <CardContent className="flex gap-5 p-5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                      {item.step}
                    </div>
                    <div>
                      <h3 className="font-semibold">{t(item.titleKey)}</h3>
                      <p className="mt-1 text-sm text-muted-foreground">{t(item.descKey)}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </SectionWrapper>

      {/* Uninstallation Instructions */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <h2 className="text-3xl font-bold tracking-tight text-center mb-6">{t("download.uninstallation")}</h2>
          <Card>
            <CardContent className="p-6">
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t("download.uninstallText")}
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Release Channels Tabs */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <Tabs defaultValue="stable" value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="stable">{t("download.tabs.stable")}</TabsTrigger>
              <TabsTrigger value="beta">{t("download.tabs.beta")}</TabsTrigger>
              <TabsTrigger value="nightly">{t("download.tabs.nightly")}</TabsTrigger>
              <TabsTrigger value="legacy">{t("download.tabs.legacy")}</TabsTrigger>
            </TabsList>

            {/* Stable Tab */}
            <TabsContent value="stable" className="space-y-10 mt-6">
              <div>
                <div className="text-center mb-6">
                  <h2 className="text-2xl font-bold tracking-tight">{t("download.releaseHistory")}</h2>
                  <p className="mt-2 text-muted-foreground">{t("download.releaseHistoryDesc")}</p>
                </div>
                <div className="space-y-6">
                  <Card className="border-dashed">
                    <CardContent className="p-8 text-center">
                      <p className="text-sm text-muted-foreground">
                        {t("download.releaseHistoryPlaceholder")}
                      </p>
                    </CardContent>
                  </Card>
                </div>
              </div>

            </TabsContent>

            {/* Beta Tab */}
            <TabsContent value="beta" className="mt-6">
              <Card className="border-dashed">
                <CardContent className="p-8 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-amber-100 text-amber-600 mx-auto mb-4">
                    <Zap className="h-7 w-7" />
                  </div>
                  <h3 className="text-lg font-semibold">{t("download.betaTitle")}</h3>
                  <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
                    {t("download.betaDesc")}
                  </p>
                  <div className="mt-6 flex flex-col sm:flex-row gap-2 max-w-sm mx-auto">
                    <Input
                      type="email"
                      placeholder={t("common.search")}
                      value={betaEmail}
                      onChange={(e) => setBetaEmail(e.target.value)}
                    />
                    <Button
                      onClick={() => {
                        alert(t("download.betaAlert"))
                        setBetaEmail("")
                      }}
                    >
                      <Mail className="mr-2 h-4 w-4" />
                      {t("download.requestAccess")}
                    </Button>
                  </div>
                  <p className="mt-4 text-xs text-muted-foreground">{t("download.betaComingSoon")}</p>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Nightly Tab */}
            <TabsContent value="nightly" className="mt-6">
              <Card className="border-dashed">
                <CardContent className="p-8 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-purple-100 text-purple-600 mx-auto mb-4">
                    <Zap className="h-7 w-7" />
                  </div>
                  <h3 className="text-lg font-semibold">{t("download.nightlyTitle")}</h3>
                  <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
                    {t("download.nightlyDesc")}
                  </p>
                  <Callout variant="warning" className="mt-6 max-w-md mx-auto text-left">
                    <p className="text-sm">
                      {t("download.nightlyWarning")}
                    </p>
                  </Callout>
                  <p className="mt-4 text-xs text-muted-foreground">{t("download.nightlyComingSoon")}</p>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Legacy Tab */}
            <TabsContent value="legacy" className="mt-6">
              <div>
                <div className="text-center mb-6">
                  <h2 className="text-2xl font-bold tracking-tight">{t("download.previousVersions")}</h2>
                  <p className="mt-2 text-muted-foreground">{t("download.previousVersionsDesc")}</p>
                </div>
                <div className="space-y-3">
                  <Card className="border-dashed">
                    <CardContent className="p-8 text-center">
                      <p className="text-sm text-muted-foreground">
                        {t("download.legacyPlaceholder")}
                      </p>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </motion.div>
      </SectionWrapper>

      {/* Migration Guides */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center"
        >
          <div className="flex justify-center mb-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10">
              <ArrowLeftRight className="h-7 w-7 text-primary" />
            </div>
          </div>
          <h2 className="text-2xl font-bold tracking-tight">{t("download.migrationGuides")}</h2>
          <p className="mt-2 text-muted-foreground">
            {t("download.migrationDesc")}
          </p>
          <Callout variant="info" className="mt-6 text-left max-w-lg mx-auto">
            {t("download.migrationCallout")}
          </Callout>
        </motion.div>
      </SectionWrapper>

      {/* Documentation Bundle */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold tracking-tight">{t("download.documentation")}</h2>
            <p className="mt-2 text-muted-foreground">{t("download.docsDesc")}</p>
          </div>
          <Card className="border-dashed">
            <CardContent className="p-6 sm:p-8">
              <div className="flex flex-col items-center text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 mb-4">
                  <BookOpen className="h-7 w-7 text-primary" />
                </div>
                <h3 className="text-lg font-semibold">{t("download.docsOffline")}</h3>
                <p className="mt-2 text-sm text-muted-foreground max-w-md">
                  {t("download.docsOfflineDesc")}
                </p>
                <Button variant="outline" className="mt-6 inline-flex items-center" onClick={() => alert(t("download.docsBundleAlert"))}>
                  <Download className="mr-2 h-4 w-4" />
                  {t("download.downloadDocsBundle")}
                </Button>
                <p className="mt-3 text-xs text-muted-foreground">{t("download.docsFormats")}</p>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Auto-Update Settings */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <Callout variant="info">
            <p className="font-medium">{t("download.autoUpdates")}</p>
            <p className="text-sm text-muted-foreground">
              {t("download.autoUpdatesDesc")}
            </p>
          </Callout>
        </motion.div>
      </SectionWrapper>

      {/* Toolkit */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold tracking-tight">{t("download.toolkit")}</h2>
            <p className="mt-2 text-muted-foreground">{t("download.toolkitDesc")}</p>
          </div>
          <Card>
            <CardContent className="p-6 sm:p-8">
              <div className="flex flex-col items-center text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 mb-4">
                  <Wrench className="h-7 w-7 text-primary" />
                </div>
                <h3 className="text-lg font-semibold">Toolkit v{toolkitConfig.latestVersion}</h3>
                <p className="mt-2 text-sm text-muted-foreground max-w-md">
                  {t("download.toolkitDesc2")}
                </p>
                <div className="mt-6 flex flex-col sm:flex-row gap-3">
                  <Button asChild>
                    <a href={toolkitConfig.downloadUrl}>
                      <Download className="mr-2 h-4 w-4" />
                      {t("download.downloadToolkit")}
                    </a>
                  </Button>
                  <Button variant="outline" asChild>
                    <Link to="/developers/toolkit">
                      <BookOpen className="mr-2 h-4 w-4" />
                      {t("common.documentation")}
                    </Link>
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* CTA Banner */}
      <SectionWrapper className="bg-muted/30">
        <CtaBanner
          title={t("download.ctaTitle")}
          description={t("download.ctaDesc")}
          buttonText={t("download.ctaButton")}
          buttonHref="/register"
        />
      </SectionWrapper>
    </>
  )
}
