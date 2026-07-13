import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { Mail, Check } from "lucide-react"
import { useLocale } from "@/i18n/locale-context"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { CtaBanner } from "@/components/shared/cta-banner"
import { enterpriseConfig } from "@/config/site"

const enterpriseFeatureKeys = [
  "enterprise.feature1",
  "enterprise.feature2",
  "enterprise.feature3",
  "enterprise.feature4",
  "enterprise.feature5",
  "enterprise.feature6",
]

export default function EnterprisePage() {
  const { t } = useLocale()

  return (
    <>
      <Helmet>
        <title>{t("enterprise.pageTitle")}</title>
        <meta name="description" content={t("enterprise.metaDesc")} />
      </Helmet>

      <HeroSection
        title={t("enterprise.title")}
        description={t("enterprise.subtitle")}
        align="center"
        size="large"
      />

      {/* Enterprise Status */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center"
        >
          <p className="text-lg leading-relaxed text-muted-foreground">
            {t("enterprise.statusMessage")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* Planned Features */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("enterprise.planned")}
          description={t("enterprise.plannedDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl"
        >
          <Card>
            <CardContent className="p-6">
              <ul className="space-y-3">
                {enterpriseFeatureKeys.map((key, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm text-muted-foreground">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <span>{t(key)}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
          <p className="mt-6 text-center text-sm text-muted-foreground">
            {t("enterprise.ctaText")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* Get in Touch */}
      <SectionWrapper>
        <SectionHeader
          title={t("enterprise.getInTouch")}
          description={t("enterprise.getInTouchDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-background">
              <CardContent className="p-8">
                <h3 className="text-xl font-semibold tracking-tight">{t("enterprise.contactSales")}</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  {t("enterprise.contactSalesDesc")}
                </p>
                <div className="mt-6 space-y-4">
                  <div className="flex items-center gap-3 text-sm">
                    <Mail className="h-4 w-4 text-primary" />
                    <a href={`mailto:${enterpriseConfig.contactEmail}`} className="underline underline-offset-4">
                      {enterpriseConfig.contactEmail}
                    </a>
                  </div>
                </div>
                <Button size="lg" className="mt-8 w-full">
                  <Mail className="mr-2 h-4 w-4" />
                  {t("enterprise.requestConsultation")}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-8">
                <h3 className="text-xl font-semibold tracking-tight">{t("enterprise.inquiry")}</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  {t("enterprise.inquiryDesc")}
                </p>
                <div className="mt-6 space-y-4">
                  {[
                    "enterprise.inquiryItem1",
                    "enterprise.inquiryItem2",
                    "enterprise.inquiryItem3",
                    "enterprise.inquiryItem4",
                  ].map((key) => (
                    <div key={key} className="flex items-start gap-3 text-sm">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-green-600" />
                      <span className="text-muted-foreground">{t(key)}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-6 rounded-lg border bg-muted p-4 text-center text-sm text-muted-foreground">
                  {t("enterprise.formPlaceholder")}
                </div>
              </CardContent>
            </Card>
          </div>
        </motion.div>
      </SectionWrapper>

      <SectionWrapper className="pb-24">
        <CtaBanner
          title={t("enterprise.ctaBannerTitle")}
          description={t("enterprise.ctaBannerDesc")}
          buttonText={t("enterprise.ctaBannerButton")}
          buttonHref="/contact"
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
