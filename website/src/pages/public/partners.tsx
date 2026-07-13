import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import {
  Globe,
  Mail,
  TrendingUp,
  Megaphone,
  Sparkles,
  HeadphonesIcon,
  BadgeCheck,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { FeatureCard } from "@/components/shared/feature-card"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { CtaBanner } from "@/components/shared/cta-banner"
import { partnerConfig } from "@/config/site"

const partnerBenefits = [
  {
    icon: TrendingUp,
    titleKey: "partners.benefits.revenue",
    descKey: "partners.benefits.revenueDesc",
  },
  {
    icon: Megaphone,
    titleKey: "partners.benefits.comarketing",
    descKey: "partners.benefits.comarketingDesc",
  },
  {
    icon: Sparkles,
    titleKey: "partners.benefits.earlyAccess",
    descKey: "partners.benefits.earlyAccessDesc",
  },
  {
    icon: HeadphonesIcon,
    titleKey: "partners.benefits.priority",
    descKey: "partners.benefits.priorityDesc",
  },
]

export default function PartnersPage() {
  const { t } = useLocale()
  return (
    <>
      <Helmet>
        <title>{t("partners.pageTitle")}</title>
        <meta name="description" content={t("partners.metaDesc")} />
      </Helmet>

      <HeroSection
        title={t("partners.title")}
        description={t("partners.heroDesc")}
        align="center"
        size="large"
      />

      {/* Partner listings — coming soon */}
      <SectionWrapper>
        <SectionHeader
          title={t("partners.ourPartners")}
          description={t("partners.ourPartnersDesc")}
          className="mb-10"
        />

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl py-8 text-center"
        >
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
            <Globe className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="mt-6 text-xl font-semibold tracking-tight">{t("partners.comingSoon")}</h3>
          <p className="mt-3 leading-relaxed text-muted-foreground">
            {t("partners.comingSoonDesc")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* Become a Partner */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("partners.become")}
          description={t("partners.becomeDesc")}
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {partnerBenefits.map((benefit, i) => (
            <FeatureCard key={benefit.titleKey} icon={benefit.icon} title={t(benefit.titleKey)} description={t(benefit.descKey)} index={i} />
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto mt-12 max-w-xl text-center"
        >
          <Button size="lg" asChild>
            <a href={`mailto:${partnerConfig.contactEmail}`}>
              <Mail className="mr-2 h-4 w-4" />
              {t("partners.apply")}
            </a>
          </Button>
          <p className="mt-3 text-sm text-muted-foreground">
            {t("partners.orEmail")}{" "}
            <a href={`mailto:${partnerConfig.contactEmail}`} className="underline underline-offset-4">
              {partnerConfig.contactEmail}
            </a>
          </p>
        </motion.div>
      </SectionWrapper>

      {/* Partner Program */}
      <SectionWrapper>
        <SectionHeader
          title={t("partners.program")}
          description={t("partners.programDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <Card className="border-dashed">
            <CardContent className="p-10 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                <BadgeCheck className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="mt-6 text-xl font-semibold tracking-tight">{t("partners.resellerTitle")}</h3>
              <p className="mt-3 text-muted-foreground max-w-lg mx-auto">
                {t("partners.resellerDesc")}
              </p>
              <Button variant="outline" size="lg" className="mt-6">
                <Globe className="mr-2 h-4 w-4" />
                {t("partners.getNotified")}
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      <SectionWrapper className="pb-24">
        <CtaBanner
          title={t("partners.ctaBannerTitle")}
          description={t("partners.ctaBannerDesc")}
          buttonText={t("partners.ctaBannerButton")}
          buttonHref={`mailto:${partnerConfig.contactEmail}`}
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
