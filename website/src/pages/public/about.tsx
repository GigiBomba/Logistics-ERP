import { SeoHead } from "@/components/seo/seo-head"
import { Link } from "react-router"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { HeartHandshake, Shield, Lightbulb, Eye, Lock, Handshake, Code, UserCheck, Cpu, Database, Cloud, Sparkles, Layers, ArrowRight } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { FeatureCard } from "@/components/shared/feature-card"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Timeline } from "@/components/shared/timeline"



export default function AboutPage() {
  const { t } = useLocale()

  const values = [
    { icon: HeartHandshake, title: t("about.values.realNeeds"), description: t("about.values.realNeedsDesc") },
    { icon: Shield, title: t("about.values.reliability"), description: t("about.values.reliabilityDesc") },
    { icon: Lightbulb, title: t("about.values.innovation"), description: t("about.values.innovationDesc") },
    { icon: Eye, title: t("about.values.open"), description: t("about.values.openDesc") },
    { icon: Lock, title: t("about.values.local"), description: t("about.values.localDesc") },
    { icon: Handshake, title: t("about.values.simple"), description: t("about.values.simpleDesc") },
  ]

  const technologyStack = [
    { icon: Cpu, title: t("about.tech.python.title"), description: t("about.tech.python.desc") },
    { icon: Database, title: t("about.tech.sqlite.title"), description: t("about.tech.sqlite.desc") },
    { icon: Cloud, title: t("about.tech.graphhopper.title"), description: t("about.tech.graphhopper.desc") },
    { icon: Layers, title: t("about.tech.architecture.title"), description: t("about.tech.architecture.desc") },
  ]

  const philosophyItems = [
    { icon: Sparkles, title: t("about.philosophy.quality.title"), description: t("about.philosophy.quality.desc") },
    { icon: UserCheck, title: t("about.philosophy.iterative.title"), description: t("about.philosophy.iterative.desc") },
    { icon: Code, title: t("about.philosophy.architecture.title"), description: t("about.philosophy.architecture.desc") },
  ]

  const timelineItems = [
    { date: "April 2026", title: t("about.timeline.started"), description: t("about.timeline.startedDesc"), status: "completed" as const },
    { date: "May 2026", title: t("about.timeline.routing"), description: t("about.timeline.routingDesc"), status: "completed" as const },
    { date: "June 2026", title: t("about.timeline.fleet"), description: t("about.timeline.fleetDesc"), status: "completed" as const },
    { date: "June 2026", title: t("about.timeline.documents"), description: t("about.timeline.documentsDesc"), status: "completed" as const },
    { date: "July 2026", title: t("about.timeline.dispatch"), description: t("about.timeline.dispatchDesc"), status: "completed" as const },
    { date: "July 2026", title: t("about.timeline.refactor"), description: t("about.timeline.refactorDesc"), status: "completed" as const },
    { date: "July 2026", title: t("about.timeline.ai"), description: t("about.timeline.aiDesc"), status: "completed" as const },
    { date: "July 2026", title: t("about.timeline.mobile"), description: t("about.timeline.mobileDesc"), status: "completed" as const },
    { date: t("about.timeline.inProgress"), title: t("about.timeline.productization"), description: t("about.timeline.productizationDesc"), status: "current" as const },
    { date: t("about.timeline.planned"), title: t("about.timeline.postgres"), description: t("about.timeline.postgresDesc"), status: "upcoming" as const },
  ]

  return (
    <>
      <SeoHead
        title={t("about.meta.title")}
        description={t("about.meta.description")}
        canonical="https://operionerp.xyz/about"
      />
      <PageHeader title={t("about.title")} description={t("about.subtitle")} />

      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <h2 className="text-2xl font-bold tracking-tight">{t("about.story")}</h2>
          <p className="mt-4 leading-relaxed text-foreground/80">
            {t("about.story.p1")}
          </p>
          <p className="mt-4 leading-relaxed text-foreground/80">
            {t("about.story.p2")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* Our Mission */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center"
        >
          <h2 className="text-3xl font-bold tracking-tight">{t("about.mission")}</h2>
          <p className="mt-4 leading-relaxed text-foreground/80 max-w-2xl mx-auto">
            {t("about.mission.text")}
          </p>
          <Button variant="outline" size="lg" className="mt-6" asChild>
            <Link to="/mission">
              {t("about.mission.cta")}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </motion.div>
      </SectionWrapper>

      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center mb-12"
        >
          <h2 className="text-3xl font-bold tracking-tight">{t("about.values")}</h2>
          <p className="mt-4 text-muted-foreground">{t("about.values.subtitle")}</p>
        </motion.div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {values.map((v, i) => (
            <FeatureCard key={v.title} {...v} index={i} />
          ))}
        </div>
      </SectionWrapper>

      {/* Technology Stack */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center mb-12"
        >
          <h2 className="text-3xl font-bold tracking-tight">{t("about.techStack")}</h2>
          <p className="mt-4 text-muted-foreground">{t("about.techStack.desc")}</p>
        </motion.div>
        <div className="mx-auto max-w-4xl grid gap-6 sm:grid-cols-2">
          {technologyStack.map((tech, i) => (
            <motion.div
              key={tech.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="h-full">
                <CardContent className="p-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-4">
                    <tech.icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="font-semibold">{tech.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{tech.description}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Development Philosophy */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <h2 className="text-3xl font-bold tracking-tight text-center">{t("about.philosophy")}</h2>
          <div className="mt-8 space-y-6">
            {philosophyItems.map((item, i) => (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                <Card>
                  <CardContent className="flex gap-4 p-5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                      <item.icon className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <h3 className="font-semibold">{item.title}</h3>
                      <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </SectionWrapper>

      {/* Company Timeline */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center mb-12"
        >
          <h2 className="text-3xl font-bold tracking-tight">{t("about.timeline")}</h2>
          <p className="mt-2 text-muted-foreground">{t("about.timeline.subtitle")}</p>
        </motion.div>
        <div className="mx-auto max-w-xl">
          <Timeline items={timelineItems} />
        </div>
      </SectionWrapper>

      {/* Our Team */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center"
        >
          <h2 className="text-2xl font-bold tracking-tight">{t("about.team")}</h2>
          <p className="mt-4 leading-relaxed text-foreground/80">
            {t("about.team.text")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* CTA Section */}
      <SectionWrapper>
        <Card className="border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-background">
          <CardContent className="p-12 text-center">
            <h2 className="text-3xl font-bold tracking-tight">{t("about.cta.title")}</h2>
            <p className="mt-4 text-muted-foreground max-w-lg mx-auto">
              {t("about.cta.text")}
            </p>
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Button size="xl" asChild>
                <Link to="/register">
                  {t("about.cta.primary")}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button variant="outline" size="xl" asChild>
                <Link to="/contact">{t("about.cta.secondary")}</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </SectionWrapper>
    </>
  )
}
