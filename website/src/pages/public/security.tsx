import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { Lock, ShieldCheck, Server, FileCheck, Mail, Bug } from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { FeatureCard } from "@/components/shared/feature-card"
import { FaqAccordion } from "@/components/shared/faq-accordion"
import { Callout } from "@/components/ui/callout"
import { CtaBanner } from "@/components/shared/cta-banner"

const securityPractices = [
  {
    icon: Lock,
    titleKey: "security.encryption",
    descKey: "security.encryptionDesc",
  },
  {
    icon: ShieldCheck,
    titleKey: "security.accessControl",
    descKey: "security.accessControlDesc",
  },
  {
    icon: Server,
    titleKey: "security.secureDev",
    descKey: "security.secureDevDesc",
  },
  {
    icon: FileCheck,
    titleKey: "security.futureCompliance",
    descKey: "security.futureComplianceDesc",
  },
]

const securityFaq = [
  {
    questionKey: "security.faq1.q",
    answerKey: "security.faq1.a",
  },
  {
    questionKey: "security.faq2.q",
    answerKey: "security.faq2.a",
  },
  {
    questionKey: "security.faq3.q",
    answerKey: "security.faq3.a",
  },
  {
    questionKey: "security.faq4.q",
    answerKey: "security.faq4.a",
  },
  {
    questionKey: "security.faq5.q",
    answerKey: "security.faq5.a",
  },
  {
    questionKey: "security.faq6.q",
    answerKey: "security.faq6.a",
  },
]

const secTimelineItems = [
  { labelKey: "security.timeline1.label", valueKey: "security.timeline1.value" },
  { labelKey: "security.timeline2.label", valueKey: "security.timeline2.value" },
  { labelKey: "security.timeline3.label", valueKey: "security.timeline3.value" },
]

export default function SecurityPage() {
  const { t } = useLocale()
  const faqItems = securityFaq.map((faq) => ({
    question: t(faq.questionKey),
    answer: t(faq.answerKey),
  }))

  return (
    <>
      <Helmet>
        <title>{t("security.pageTitle")}</title>
        <meta name="description" content={t("security.metaDesc")} />
      </Helmet>

      <HeroSection
        title={t("security.title")}
        description={t("security.heroDesc")}
        align="center"
        size="large"
      />

      {/* Security Practices */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("security.practices")}
          description={t("security.practicesDesc")}
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {securityPractices.map((practice, i) => (
            <FeatureCard key={practice.titleKey} icon={practice.icon} title={t(practice.titleKey)} description={t(practice.descKey)} index={i} />
          ))}
        </div>
      </SectionWrapper>

      {/* Responsible Disclosure */}
      <SectionWrapper>
        <SectionHeader
          title={t("trust.disclosure")}
          description={t("security.disclosureDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <Callout variant="info" title={t("security.disclosureCalloutTitle")}>
            <p className="mb-3">
              {t("security.disclosureCalloutText")}
            </p>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
              <a
                href="mailto:security@operion.com"
                className="inline-flex items-center gap-2 text-sm font-medium underline underline-offset-4"
              >
                <Mail className="h-4 w-4" />
                security@operion.com
              </a>
              <span className="hidden sm:inline text-muted-foreground">|</span>
              <span className="text-sm text-muted-foreground">{t("security.expectedResponse")}</span>
            </div>
          </Callout>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {secTimelineItems.map((item) => (
              <div key={item.labelKey} className="rounded-xl border bg-card p-4 text-center shadow-sm">
                <p className="text-2xl font-bold tracking-tight">{t(item.valueKey)}</p>
                <p className="mt-1 text-sm text-muted-foreground">{t(item.labelKey)}</p>
              </div>
            ))}
          </div>
        </motion.div>
      </SectionWrapper>

      {/* Security FAQ */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("security.faq")}
          description={t("security.faqDesc")}
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

      {/* Bug Bounty Program */}
      <SectionWrapper>
        <SectionHeader
          title={t("security.bugBounty")}
          description={t("security.bugBountyDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center"
        >
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
            <Bug className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="mt-6 text-xl font-semibold tracking-tight">{t("security.comingSoon")}</h3>
          <p className="mt-3 text-muted-foreground">
            {t("security.bugBountyText")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* CTA Banner */}
      <SectionWrapper className="pb-24">
        <CtaBanner
          title={t("security.ctaTitle")}
          description={t("security.ctaDesc")}
          buttonText={t("security.ctaButton")}
          buttonHref="/contact"
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
