import { motion } from "motion/react"
import { SeoHead } from "@/components/seo/seo-head"
import { useLocale } from "@/i18n/locale-context"
import {
  Lightbulb,
  Users,
  Target,
  Sprout,
  Globe,
  Clock,
  HeartPulse,
  Coffee,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { CtaBanner } from "@/components/shared/cta-banner"
import { FeatureCard } from "@/components/shared/feature-card"
import { careersConfig } from "@/config/site"

const CULTURE_VALUES = [
  {
    icon: Lightbulb,
    titleKey: "careers.values.innovation",
    descKey: "careers.values.innovationDesc",
  },
  {
    icon: Users,
    titleKey: "careers.values.collaboration",
    descKey: "careers.values.collaborationDesc",
  },
  {
    icon: Target,
    titleKey: "careers.values.impact",
    descKey: "careers.values.impactDesc",
  },
  {
    icon: Sprout,
    titleKey: "careers.values.growth",
    descKey: "careers.values.growthDesc",
  },
]

const BENEFITS = [
  { icon: Globe, labelKey: "careers.benefits.remote", descKey: "careers.benefits.remoteDesc" },
  { icon: Clock, labelKey: "careers.benefits.flexible", descKey: "careers.benefits.flexibleDesc" },
  { icon: HeartPulse, labelKey: "careers.benefits.health", descKey: "careers.benefits.healthDesc" },
  { icon: Coffee, labelKey: "careers.benefits.stipend", descKey: "careers.benefits.stipendDesc" },
]

export default function CareersPage() {
  const { t } = useLocale()
  return (
    <>
      <SeoHead title={t("careers.pageTitle")} description={t("careers.metaDesc")} canonical="https://operionerp.xyz/careers" />

      <HeroSection
        title={t("careers.title")}
        description={t("careers.heroDesc")}
        size="large"
        align="center"
      />

      <SectionWrapper>
        <div className="mb-4 text-center">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("careers.culture")}</h2>
          <p className="mt-2 text-muted-foreground">
            {t("careers.cultureDesc")}
          </p>
        </div>
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {CULTURE_VALUES.map((value, i) => (
            <FeatureCard
              key={value.titleKey}
              icon={value.icon}
              title={t(value.titleKey)}
              description={t(value.descKey)}
              index={i}
            />
          ))}
        </div>
      </SectionWrapper>

      <SectionWrapper className="bg-accent/30">
        <div className="mb-4 text-center">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("careers.whyUs")}</h2>
          <p className="mt-2 text-muted-foreground">
            {t("careers.whyUsDesc")}
          </p>
        </div>
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          {BENEFITS.map((benefit, i) => (
            <motion.div
              key={benefit.labelKey}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
              className="rounded-xl border bg-card p-5 text-card-foreground shadow-sm"
            >
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-primary">
                <benefit.icon className="h-4 w-4" />
              </div>
              <h3 className="text-sm font-semibold">{t(benefit.labelKey)}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{t(benefit.descKey)}</p>
            </motion.div>
          ))}
        </motion.div>
      </SectionWrapper>

      <SectionWrapper>
        <div className="mb-4 text-center">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("careers.openings")}</h2>
          <p className="mt-2 text-muted-foreground">
            {t("careers.openingsDesc")}
          </p>
        </div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl py-8 text-center"
        >
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
            <Users className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="mt-6 text-xl font-semibold tracking-tight">{t("careers.noOpenings")}</h3>
          <p className="mt-3 leading-relaxed text-muted-foreground">
            {t("careers.noOpeningsDesc")}{" "}
            <a
              href={`mailto:${careersConfig.contactEmail}`}
              className="font-medium text-primary underline underline-offset-4"
            >
              {careersConfig.contactEmail}
            </a>
            .
          </p>
        </motion.div>
      </SectionWrapper>

      <SectionWrapper className="pt-0">
        <CtaBanner
          title={t("careers.ctaTitle")}
          description={t("careers.ctaDesc")}
          buttonText={t("careers.ctaButton")}
          buttonHref={`mailto:${careersConfig.contactEmail}`}
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
