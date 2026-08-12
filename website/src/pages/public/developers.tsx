import { Link } from "react-router"
import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { Wrench, BookOpen, Code, Puzzle, Webhook, Users, ArrowRight, Key, Terminal, Zap } from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CtaBanner } from "@/components/shared/cta-banner"

const resources = [
  {
    icon: Wrench,
    titleKey: "developers.toolkit",
    descKey: "developers.toolkitDesc",
    href: "/developers/toolkit",
    available: true,
  },
  {
    icon: BookOpen,
    titleKey: "developers.apiRef",
    descKey: "developers.apiRefDesc",
    href: "#",
    available: false,
  },
  {
    icon: Code,
    titleKey: "developers.sdk",
    descKey: "developers.sdkDesc",
    href: "#",
    available: false,
  },
  {
    icon: Puzzle,
    titleKey: "developers.integrationGuides",
    descKey: "developers.integrationGuidesDesc",
    href: "#",
    available: false,
  },
  {
    icon: Webhook,
    titleKey: "integrations.webhooks",
    descKey: "developers.webhooksDesc",
    href: "#",
    available: false,
  },
  {
    icon: Users,
    titleKey: "developers.community",
    descKey: "developers.communityDesc",
    href: "#",
    available: false,
  },
]

const quickStartSteps = [
  {
    icon: Key,
    titleKey: "developers.quickStart",
    descKey: "developers.quickStartDesc",
  },
  {
    icon: Terminal,
    titleKey: "developers.install",
    descKey: "developers.installDesc",
  },
  {
    icon: Zap,
    titleKey: "developers.firstRequest",
    descKey: "developers.firstRequestDesc",
  },
]

export default function DevelopersPage() {
  const { t } = useLocale()
  return (
    <>
      <SeoHead title={t("developers.pageTitle")} description={t("developers.metaDesc")} canonical="https://operionerp.xyz/developers" />

      <HeroSection
        title={t("developers.title")}
        description={t("developers.heroDesc")}
        align="center"
        size="large"
      />

      {/* Resource Cards */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("developers.resources")}
          description={t("developers.resourcesDesc")}
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {resources.map((resource, i) => (
            <motion.div
              key={resource.titleKey}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
            >
              <Card className="group h-full transition-shadow hover:shadow-md">
                <CardHeader>
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                    <resource.icon className="h-5 w-5" />
                  </div>
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-lg">{t(resource.titleKey)}</CardTitle>
                    {!resource.available && (
                      <Badge variant="secondary" className="text-[10px]">{t("common.comingSoon")}</Badge>
                    )}
                  </div>
                  <CardDescription className="text-sm leading-relaxed">{t(resource.descKey)}</CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  <Button
                    variant={resource.available ? "default" : "outline"}
                    size="sm"
                    asChild
                    className="mt-2"
                  >
                    <Link to={resource.href}>
                      {resource.available ? t("developers.exploreDocs") : t("common.learnMore")}
                      <ArrowRight className="ml-1 h-4 w-4" />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Quick Start */}
      <SectionWrapper>
        <SectionHeader
          title={t("developers.quickStartSection")}
          description={t("developers.quickStartSectionDesc")}
          className="mb-12"
        />
        <div className="mx-auto max-w-4xl">
          <div className="grid gap-8 md:grid-cols-3">
            {quickStartSteps.map((step, i) => (
              <motion.div
                key={step.titleKey}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.15, ease: [0.22, 1, 0.36, 1] }}
                className="relative"
              >
                <div className="flex flex-col items-center text-center">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                    {i + 1}
                  </div>
                  {i < quickStartSteps.length - 1 && (
                    <div className="absolute top-6 left-[calc(50%+24px)] hidden h-px w-[calc(100%-48px)] bg-border md:block" />
                  )}
                  <div className="mt-4 flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary">
                    <step.icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold tracking-tight">{t(step.titleKey)}</h3>
                  <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{t(step.descKey)}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </SectionWrapper>

      {/* CTA Banner */}
      <SectionWrapper className="pb-24">
        <CtaBanner
          title={t("developers.ctaTitle")}
          description={t("developers.ctaDesc")}
          buttonText={t("developers.ctaButton")}
          buttonHref="/docs"
          variant="outline"
        />
      </SectionWrapper>
    </>
  )
}
