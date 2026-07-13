import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { useLocale } from "@/i18n/locale-context"
import { motion } from "motion/react"
import {
  ArrowRight,
  BarChart3,
  ChevronRight,
  DollarSign,
  FileText,
  LayoutDashboard,
  Play,
  Radio,
  Rocket,
  Route,
  Send,
  Shield,
  Truck,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { FeatureCard } from "@/components/shared/feature-card"
import { CtaSection } from "@/components/shared/cta-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { StatCard } from "@/components/shared/stat-card"
import { FaqAccordion } from "@/components/shared/faq-accordion"
import { Timeline } from "@/components/shared/timeline"



export default function HomePage() {
  const { t } = useLocale()

  const features = [
    { icon: DollarSign, title: t("home.features.profitCalc.title"), description: t("home.features.profitCalc.desc") },
    { icon: Route, title: t("home.features.routePlanning.title"), description: t("home.features.routePlanning.desc") },
    { icon: Send, title: t("home.features.dispatch.title"), description: t("home.features.dispatch.desc") },
    { icon: Truck, title: t("home.features.fleet.title"), description: t("home.features.fleet.desc") },
    { icon: FileText, title: t("home.features.documents.title"), description: t("home.features.documents.desc") },
    { icon: BarChart3, title: t("home.features.analytics.title"), description: t("home.features.analytics.desc") },
  ]

  const benefits = [
    { icon: DollarSign, title: t("home.benefits.costs.title"), description: t("home.benefits.costs.desc") },
    { icon: Truck, title: t("home.benefits.speed.title"), description: t("home.benefits.speed.desc") },
    { icon: FileText, title: t("home.benefits.paperwork.title"), description: t("home.benefits.paperwork.desc") },
    { icon: Shield, title: t("home.benefits.scale.title"), description: t("home.benefits.scale.desc") },
  ]

  const stats = [
    { value: "5", label: t("home.stats.modules") },
    { value: t("home.stats.desktopLabel"), label: t("home.stats.desktop") },
    { value: t("home.stats.webLabel"), label: t("home.stats.web") },
    { value: t("home.stats.statusLabel"), label: t("home.stats.status") },
  ]

  const workflowSteps = [
    { icon: DollarSign, title: t("home.workflow.calculate.title"), description: t("home.workflow.calculate.desc") },
    { icon: Route, title: t("home.workflow.plan.title"), description: t("home.workflow.plan.desc") },
    { icon: Send, title: t("home.workflow.dispatch.title"), description: t("home.workflow.dispatch.desc") },
  ]

  const screenshotCategories = [
    { label: t("home.screenshots.routePlanning"), icon: Route, gradient: "from-primary/20 to-primary/5" },
    { label: t("home.screenshots.fleetDashboard"), icon: LayoutDashboard, gradient: "from-accent/30 to-accent/10" },
    { label: t("home.screenshots.dispatchConsole"), icon: Radio, gradient: "from-primary/10 to-accent/20" },
  ]

  const roadmapItems = [
    { date: t("roadmap.inProgress"), title: t("home.roadmap.maintenance.title"), description: t("home.roadmap.maintenance.desc"), status: "current" as const },
    { date: t("roadmap.planned"), title: t("home.roadmap.postgres.title"), description: t("home.roadmap.postgres.desc"), status: "upcoming" as const },
    { date: t("roadmap.planned"), title: t("home.roadmap.mobile.title"), description: t("home.roadmap.mobile.desc"), status: "upcoming" as const },
  ]

  const faqItems = [
    { question: t("home.faq1.q"), answer: t("home.faq1.a") },
    { question: t("home.faq2.q"), answer: t("home.faq2.a") },
    { question: t("home.faq3.q"), answer: t("home.faq3.a") },
    { question: t("home.faq4.q"), answer: t("home.faq4.a") },
    { question: t("home.faq5.q"), answer: t("home.faq5.a") },
  ]

  return (
    <>
      <Helmet>
        <title>{t("home.meta.title")}</title>
        <meta name="description" content={t("home.meta.description")} />
        <link rel="canonical" href="https://operion.com" />
      </Helmet>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-background to-accent/20" />
        <div className="absolute inset-0 opacity-30">
          <div className="absolute -top-40 -right-40 h-80 w-80 rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 h-80 w-80 rounded-full bg-accent/20 blur-3xl" />
        </div>
        <div className="relative container-wide py-24 md:py-32 lg:py-40">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto max-w-3xl text-center"
          >
            <Badge variant="secondary" className="mb-6 inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium">
              <Rocket className="h-3 w-3" />
              {t("home.hero.badge")}
            </Badge>
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
              {t("home.hero.title")}
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-muted-foreground sm:text-xl">
              {t("home.hero.subtitle")}
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button size="xl" asChild>
                <Link to="/register">
                  {t("home.hero.cta")}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button variant="outline" size="xl" asChild>
                <Link to="/features">
                  <Play className="mr-2 h-4 w-4" />
                  {t("home.hero.secondary")}
                </Link>
              </Button>
            </div>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4, duration: 0.5 }}
              className="mt-6 text-sm text-muted-foreground"
            >
              {t("home.trustedBy")}
            </motion.p>
          </motion.div>
        </div>
      </section>

      {/* Statistics */}
      <SectionWrapper className="bg-muted/30">
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
            >
              <StatCard value={s.value} label={s.label} />
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Features */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center"
        >
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("home.features.title")}</h2>
          <p className="mt-4 text-muted-foreground">{t("home.features.subtitle")}</p>
        </motion.div>
        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <FeatureCard key={f.title} {...f} index={i} />
          ))}
        </div>
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="mt-12 text-center"
        >
          <Button variant="ghost" asChild>
            <Link to="/features" className="inline-flex items-center gap-1 text-sm font-medium">
              {t("home.features.seeAll")}
              <ChevronRight className="h-4 w-4" />
            </Link>
          </Button>
        </motion.div>
      </SectionWrapper>

      {/* Workflow */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center"
        >
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("home.howItWorks")}</h2>
          <p className="mt-4 text-muted-foreground">{t("home.workflow.subtitle")}</p>
        </motion.div>
        <div className="mt-16 grid gap-8 md:grid-cols-3">
          {workflowSteps.map((step, i) => (
            <motion.div
              key={step.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.15, ease: [0.22, 1, 0.36, 1] }}
              className="relative"
            >
              <Card className="h-full">
                <CardContent className="flex flex-col items-center p-6 text-center">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                    <step.icon className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold">{step.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{step.description}</p>
                </CardContent>
              </Card>
              {i < workflowSteps.length - 1 && (
                <div className="absolute -right-4 top-1/2 hidden -translate-y-1/2 text-muted-foreground/40 md:block">
                  <ArrowRight className="h-6 w-6" />
                </div>
              )}
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Benefits */}
      <SectionWrapper>
        <div className="mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-2xl text-center"
          >
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("home.whyOperion")}</h2>
          </motion.div>
          <div className="mt-16 grid gap-8 sm:grid-cols-2">
            {benefits.map((b, i) => (
              <motion.div
                key={b.title}
                initial={{ opacity: 0, x: i % 2 === 0 ? -20 : 20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className="flex gap-4"
              >
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                  <b.icon className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold">{b.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{b.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </SectionWrapper>


      {/* Screenshots Placeholder */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center"
        >
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("home.cta.title")}</h2>
          <p className="mt-4 text-muted-foreground">{t("home.screenshots.subtitle")}</p>
        </motion.div>
        <div className="mt-16 grid gap-6 sm:grid-cols-3">
          {screenshotCategories.map((cat, i) => (
            <motion.div
              key={cat.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
            >
              <Card className="group overflow-hidden">
                <div className={`aspect-video w-full bg-gradient-to-br ${cat.gradient} flex flex-col items-center justify-center gap-3 transition-transform duration-300 group-hover:scale-105`}>
                  <cat.icon className="h-10 w-10 text-primary/60" />
                  <span className="text-sm font-semibold text-foreground/70">{cat.label}</span>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>


      {/* Mission Summary */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center"
        >
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("home.mission.title")}</h2>
          <p className="mt-6 text-lg leading-relaxed text-muted-foreground">
            {t("home.mission.text")}
          </p>
          <Button variant="outline" className="mt-8" asChild>
            <Link to="/mission">{t("home.mission.cta")}</Link>
          </Button>
        </motion.div>
      </SectionWrapper>

      {/* Roadmap Preview */}
      <SectionWrapper className="bg-muted/30">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center"
          >
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("home.roadmap.title")}</h2>
            <p className="mt-4 text-muted-foreground">{t("home.roadmap.subtitle")}</p>
          </motion.div>
          <div className="mt-12">
            <Timeline items={roadmapItems} />
          </div>
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="mt-8 text-center"
          >
            <Button variant="ghost" asChild>
              <Link to="/roadmap" className="inline-flex items-center gap-1 text-sm font-medium">
                {t("home.roadmap.viewFull")}
                <ChevronRight className="h-4 w-4" />
              </Link>
            </Button>
          </motion.div>
        </div>
      </SectionWrapper>


      {/* FAQ Preview */}
      <SectionWrapper className="bg-muted/30">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center"
          >
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("home.faq")}</h2>
            <p className="mt-4 text-muted-foreground">{t("home.faqSubtitle")}</p>
          </motion.div>
          <div className="mt-12">
            <FaqAccordion items={faqItems} />
          </div>
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="mt-8 text-center"
          >
            <Button variant="ghost" asChild>
              <Link to="/faq" className="inline-flex items-center gap-1 text-sm font-medium">
                {t("home.faq.viewAll")}
                <ChevronRight className="h-4 w-4" />
              </Link>
            </Button>
          </motion.div>
        </div>
      </SectionWrapper>

      {/* Footer CTA */}
      <CtaSection
        title={t("home.ctaSection.title")}
        description={t("home.ctaSection.text")}
        primaryLabel={t("home.ctaSection.primary")}
        primaryHref="/roadmap"
        secondaryLabel={t("home.ctaSection.secondary")}
        secondaryHref="/features"
      />
    </>
  )
}
