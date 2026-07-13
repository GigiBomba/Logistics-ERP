import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import {
  ArrowRight,
  MessageCircle,
  Code2,
  Vote,
  Sparkles,
  Calendar,
  BookOpen,
  ShieldCheck,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CtaBanner } from "@/components/shared/cta-banner"

const announcements = [
  {
    titleKey: "community.announce1.title",
    dateKey: "community.announce1.date",
    descKey: "community.announce1.desc",
    tagKey: "community.announce1.tag",
    tagVariant: "default" as const,
  },
  {
    titleKey: "community.announce2.title",
    dateKey: "community.announce2.date",
    descKey: "community.announce2.desc",
    tagKey: "community.announce2.tag",
    tagVariant: "success" as const,
  },
  {
    titleKey: "community.announce3.title",
    dateKey: "community.announce3.date",
    descKey: "community.announce3.desc",
    tagKey: "community.announce3.tag",
    tagVariant: "secondary" as const,
  },
  {
    titleKey: "community.announce4.title",
    dateKey: "community.announce4.date",
    descKey: "community.announce4.desc",
    tagKey: "community.announce4.tag",
    tagVariant: "outline" as const,
  },
]

const guidelines = [
  "community.guideline1",
  "community.guideline2",
  "community.guideline3",
  "community.guideline4",
  "community.guideline5",
]

const getInvolved = [
  {
    icon: Code2,
    titleKey: "community.github",
    descKey: "community.githubDesc",
    href: "https://github.com/operion",
    statusKey: "community.statusAvailable",
    statusVariant: "success" as const,
    buttonKey: "community.joinNow",
  },
  {
    icon: MessageCircle,
    titleKey: "community.discord",
    descKey: "community.discordDesc",
    href: "#",
    statusKey: "community.statusComingSoon",
    statusVariant: "secondary" as const,
    buttonKey: "common.comingSoon",
  },
  {
    icon: Vote,
    titleKey: "community.voting",
    descKey: "community.votingDesc",
    href: "#",
    statusKey: "community.statusComingSoon",
    statusVariant: "secondary" as const,
    buttonKey: "common.comingSoon",
  },
]

export default function CommunityPage() {
  const { t } = useLocale()
  return (
    <>
      <Helmet>
        <title>{t("community.pageTitle")}</title>
        <meta
          name="description"
          content={t("community.metaDesc")}
        />
      </Helmet>

      <HeroSection
        title={t("community.title")}
        description={t("community.heroDesc")}
        align="center"
        size="large"
      />

      {/* Announcements */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("community.announcements")}
          description={t("community.announcementsDesc")}
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {announcements.map((item, i) => (
            <motion.div
              key={item.titleKey}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
            >
              <Card className="group h-full transition-shadow hover:shadow-md">
                <CardHeader>
                  <div className="mb-2 flex items-center gap-2">
                    <Badge variant={item.tagVariant} className="text-[10px]">
                      {t(item.tagKey)}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{t(item.dateKey)}</span>
                  </div>
                  <CardTitle className="text-base leading-snug">{t(item.titleKey)}</CardTitle>
                  <CardDescription className="text-sm leading-relaxed">
                    {t(item.descKey)}
                  </CardDescription>
                </CardHeader>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Community Guidelines */}
      <SectionWrapper>
        <SectionHeader
          title={t("community.guidelines")}
          description={t("community.guidelinesDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <Card>
            <CardContent className="p-8 md:p-10">
              <div className="grid gap-4 md:grid-cols-2">
                {guidelines.map((line, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                    <p className="text-sm leading-relaxed text-muted-foreground">{t(line)}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Get Involved */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("community.getInvolved")}
          description={t("community.getInvolvedDesc")}
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {getInvolved.map((item, i) => (
            <motion.div
              key={item.titleKey}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
            >
              <Card className="group h-full transition-shadow hover:shadow-md">
                <CardHeader>
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-lg">{t(item.titleKey)}</CardTitle>
                    <Badge variant={item.statusVariant} className="text-[10px]">
                      {t(item.statusKey)}
                    </Badge>
                  </div>
                  <CardDescription className="text-sm leading-relaxed">
                    {t(item.descKey)}
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  <Button
                    variant={item.href === "#" ? "outline" : "default"}
                    size="sm"
                    asChild
                    className="mt-2"
                  >
                    <Link to={item.href} target={item.href.startsWith("http") ? "_blank" : undefined}>
                      {t(item.buttonKey)}
                      <ArrowRight className="ml-1 h-4 w-4" />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Showcase */}
      <SectionWrapper>
        <SectionHeader
          title={t("community.showcase")}
          description={t("community.showcaseDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center gap-4 p-12 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-accent text-primary">
                <Sparkles className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-lg font-semibold tracking-tight">{t("community.showcaseComing")}</h3>
                <p className="mt-2 max-w-md text-sm text-muted-foreground">
                  {t("community.showcaseComingDesc")}
                </p>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link to="/customers">
                  {t("community.viewCustomers")}
                  <ArrowRight className="ml-1 h-4 w-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Events */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title={t("community.events")}
          description={t("community.eventsDesc")}
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center gap-4 p-12 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-accent text-primary">
                <Calendar className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-lg font-semibold tracking-tight">{t("community.eventsComing")}</h3>
                <p className="mt-2 max-w-md text-sm text-muted-foreground">
                  {t("community.eventsComingDesc")}
                </p>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link to="/blog">
                  {t("common.readMore")}
                  <BookOpen className="ml-1 h-4 w-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* CTA Banner */}
      <SectionWrapper className="pb-24">
        <CtaBanner
          title={t("community.ctaTitle")}
          description={t("community.ctaDesc")}
          buttonText={t("community.ctaButton")}
          buttonHref="/blog"
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
