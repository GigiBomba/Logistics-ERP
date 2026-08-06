import { SeoHead } from "@/components/seo/seo-head"
import { JsonLd, productSchema, faqSchema } from "@/components/seo/structured-data"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { PageHeader, SectionHeader } from "@/components/shared/page-header"
import { CtaSection } from "@/components/shared/cta-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { FaqAccordion } from "@/components/shared/faq-accordion"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

const pricingFaqs = [
  {
    questionKey: "pricing.faq1.q",
    answerKey: "pricing.faq1.a",
  },
  {
    questionKey: "pricing.faq2.q",
    answerKey: "pricing.faq2.a",
  },
  {
    questionKey: "pricing.faq3.q",
    answerKey: "pricing.faq3.a",
  },
  {
    questionKey: "pricing.faq4.q",
    answerKey: "pricing.faq4.a",
  },
]

export default function PricingPage() {
  const { t } = useLocale()
  const faqItems = pricingFaqs.map((faq) => ({
    question: t(faq.questionKey),
    answer: t(faq.answerKey),
  }))

  return (
    <>
      <SeoHead
        title={t("pricing.pageTitle")}
        description={t("pricing.metaDesc")}
        canonical="https://operionerp.xyz/pricing"
      />

      {/* Structured Data: Product + FAQ */}
      <JsonLd
        data={productSchema({
          name: "Operion ERP",
          description: "Logistics operations platform for transport companies — route planning, fleet management, dispatch, and document generation.",
          url: "https://operionerp.xyz/pricing",
          price: "0",
          priceCurrency: "EUR",
          category: "BusinessApplication",
          offers: [
            {
              name: "Early Access (Free)",
              price: "0",
              priceCurrency: "EUR",
              description: "Free during productization phase — all major features complete",
            },
          ],
        })}
      />
      <JsonLd data={faqSchema(faqItems)} />

      <PageHeader
        title={t("pricing.title")}
        description={t("pricing.headerDesc")}
      />

      {/* Main CTA Card */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl"
        >
          <Card className="border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-background text-center">
            <CardContent className="p-8 md:p-12">
              <h2 className="text-3xl font-bold tracking-tight">{t("pricing.comingSoon")}</h2>
              <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
                {t("pricing.devMessage")}
              </p>
              <div className="mt-8">
                <Button size="lg" asChild>
                  <a href="/register">{t("pricing.earlyAccess")}</a>
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Pricing FAQ */}
      <SectionWrapper>
        <SectionHeader
          title={t("pricing.faq")}
          description={t("pricing.faqDesc")}
          className="mb-12"
        />
        <div className="mx-auto max-w-3xl">
          <FaqAccordion items={faqItems} />
        </div>
      </SectionWrapper>

      <CtaSection
        title={t("pricing.ctaTitle")}
        description={t("pricing.ctaDesc")}
        primaryLabel={t("pricing.ctaLabel")}
        primaryHref="/register"
      />
    </>
  )
}
