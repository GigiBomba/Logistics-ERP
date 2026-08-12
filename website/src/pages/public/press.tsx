import { motion } from "motion/react"
import { SeoHead } from "@/components/seo/seo-head"
import { useLocale } from "@/i18n/locale-context"
import {
  ArrowRight,
  Calendar,
  Download,
  Palette,
  Mail,
  FileText,
  Image,
  Users,
  Building,
  Globe,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { CtaBanner } from "@/components/shared/cta-banner"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { pressConfig } from "@/config/site"

const BRAND_COLORS = [
  { name: "Primary", hex: "#0f172a", usage: "Headings, primary buttons, dark backgrounds" },
  { name: "Accent", hex: "#3b82f6", usage: "Links, interactive elements, highlights" },
  { name: "Secondary", hex: "#64748b", usage: "Body text, captions, muted UI" },
  { name: "Background", hex: "#f8fafc", usage: "Page backgrounds, cards, surfaces" },
]

const BRAND_ASSETS = [
  { name: "Full Logo (Light)", format: "SVG / PNG", size: "24 KB" },
  { name: "Full Logo (Dark)", format: "SVG / PNG", size: "22 KB" },
  { name: "Icon Only", format: "SVG / PNG", size: "8 KB" },
  { name: "Social Media Kit", format: "PNG", size: "156 KB" },
]

export default function PressPage() {
  const { t } = useLocale()
  const { companyFacts, contactEmail } = pressConfig

  return (
    <>
      <SeoHead title={t("press.pageTitle")} description={t("press.metaDesc")} canonical="https://operionerp.xyz/press" />

      <HeroSection
        title={t("press.title")}
        description={t("press.heroDesc")}
        size="large"
        align="center"
      />

      <SectionWrapper>
        <Tabs defaultValue="press-releases">
          <TabsList className="mb-8">
            <TabsTrigger value="press-releases">{t("press.releases")}</TabsTrigger>
            <TabsTrigger value="media-kit">{t("press.mediaKit")}</TabsTrigger>
          </TabsList>

          <TabsContent value="press-releases">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="mx-auto max-w-2xl py-12 text-center"
            >
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                <FileText className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="mt-6 text-xl font-semibold tracking-tight">{t("press.title")}</h3>
              <p className="mt-3 leading-relaxed text-muted-foreground">
                {t("press.noReleases")}{" "}
                <a
                  href={`mailto:${pressConfig.contactEmail}`}
                  className="font-medium text-primary underline underline-offset-4"
                >
                  {pressConfig.contactEmail}
                </a>
              </p>
            </motion.div>
          </TabsContent>

          <TabsContent value="media-kit">
            <div className="grid gap-6 lg:grid-cols-3">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="lg:col-span-2"
              >
                <Card>
                  <CardHeader>
                    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary">
                      <Building className="h-5 w-5" />
                    </div>
                    <CardTitle>{t("press.companyFacts")}</CardTitle>
                    <CardDescription>{t("press.companyFactsDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="flex items-center gap-3 rounded-lg border p-4">
                        <Calendar className="h-5 w-5 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-medium">{t("press.founded")}</p>
                          <p className="text-sm text-muted-foreground">{companyFacts.founded}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 rounded-lg border p-4">
                        <Globe className="h-5 w-5 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-medium">{t("press.headquarters")}</p>
                          <p className="text-sm text-muted-foreground">{companyFacts.headquarters}</p>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
              >
                <Card className="h-full">
                  <CardHeader>
                    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary">
                      <Mail className="h-5 w-5" />
                    </div>
                    <CardTitle>{t("press.pressContact")}</CardTitle>
                    <CardDescription>{t("press.pressContactDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <a
                      href={`mailto:${contactEmail}`}
                      className="text-sm font-medium text-primary hover:underline"
                    >
                      {contactEmail}
                    </a>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {t("press.responseTime")}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.15 }}
                className="lg:col-span-3"
              >
                <Card>
                  <CardHeader>
                    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary">
                      <Image className="h-5 w-5" />
                    </div>
                    <CardTitle>{t("press.brandAssets")}</CardTitle>
                    <CardDescription>
                      {t("press.brandAssetsDesc")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <p className="mb-6 text-sm text-muted-foreground">
                      {t("press.brandAssetsNotAvailable")}
                    </p>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      {BRAND_ASSETS.map((asset) => (
                        <div
                          key={asset.name}
                          className="flex flex-col gap-3 rounded-lg border p-4 opacity-60"
                        >
                          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-accent text-primary">
                            <FileText className="h-5 w-5" />
                          </div>
                          <div>
                            <p className="text-sm font-medium">{asset.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {asset.format} · {asset.size}
                            </p>
                          </div>
                          <Button variant="outline" size="sm" className="mt-auto w-full" disabled>
                            <Download className="mr-2 h-4 w-4" />
                            {t("common.comingSoon")}
                          </Button>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
                className="lg:col-span-2"
              >
                <Card>
                  <CardHeader>
                    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary">
                      <Palette className="h-5 w-5" />
                    </div>
                    <CardTitle>{t("press.brandColors")}</CardTitle>
                    <CardDescription>{t("press.brandColorsDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      {BRAND_COLORS.map((color) => (
                        <div key={color.name} className="rounded-lg border p-4">
                          <div
                            className="mb-3 h-16 w-full rounded-md border"
                            style={{ backgroundColor: color.hex }}
                          />
                          <p className="text-sm font-medium">{color.name}</p>
                          <p className="text-xs font-mono text-muted-foreground">{color.hex}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{color.usage}</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.25 }}
              >
                <Card className="h-full">
                  <CardHeader>
                    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary">
                      <Users className="h-5 w-5" />
                    </div>
                    <CardTitle>{t("press.executiveBios")}</CardTitle>
                    <CardDescription>{t("press.executiveBiosDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {t("press.executiveBiosText")}
                    </p>
                    <Button variant="outline" size="sm" className="mt-4 w-full" asChild>
                      <a href={`mailto:${contactEmail}?subject=Executive%20Bio%20Request`}>
                        {t("press.requestBios")}
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </a>
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </TabsContent>
        </Tabs>
      </SectionWrapper>

      <SectionWrapper className="pt-0">
        <CtaBanner
          title={t("press.ctaTitle")}
          description={t("press.ctaDesc")}
          buttonText={t("press.ctaButton")}
          buttonHref={`mailto:${contactEmail}`}
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
