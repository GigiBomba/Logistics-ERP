import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { CtaBanner } from "@/components/shared/cta-banner"

export default function CustomersPage() {
  const { t } = useLocale()
  return (
    <>
      <SeoHead title={t("customers.title")} description={t("customers.metaDesc")} canonical="https://operionerp.xyz/customers" />

      <HeroSection
        title={t("customers.title")}
        description={t("customers.heroDesc")}
        size="large"
        align="center"
      />

      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl py-12 text-center"
        >
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("common.comingSoon")}</h2>
          <p className="mt-4 leading-relaxed text-muted-foreground">
            {t("customers.comingSoonDesc")}
          </p>
        </motion.div>
      </SectionWrapper>

      <SectionWrapper className="pt-0">
        <CtaBanner
          title={t("customers.ctaTitle")}
          description={t("customers.ctaDesc")}
          buttonText={t("common.contactUs")}
          buttonHref="/contact"
          variant="outline"
        />
      </SectionWrapper>
    </>
  )
}
