import { SeoHead } from "@/components/seo/seo-head"
import { JsonLd, softwareApplicationSchema, organizationSchema, websiteSchema } from "@/components/seo/structured-data"
import { Link } from "react-router"
import { useLocale } from "@/i18n/locale-context"
import { motion } from "motion/react"
import {
  ArrowRight,
  BarChart3,
  Check,
  ChevronRight,
  DollarSign,
  FileText,
  LayoutDashboard,
  MapPin,
  Navigation,
  Play,
  Radio,
  Route,
  Send,
  Shield,
  Sparkles,
  Truck,
  Users,
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
import { TestimonialCard } from "@/components/shared/testimonial-card"
import { testimonials } from "@/config/site"
import { trackCTAClick } from "@/services/analytics"



export default function HomePage() {
  const { t } = useLocale()

  const features = [
    { icon: DollarSign, title: t("home.features.profitCalc.title"), description: t("home.features.profitCalc.desc") },
    { icon: Route, title: t("home.features.routePlanning.title"), description: t("home.features.routePlanning.desc") },
    { icon: Send, title: t("home.features.dispatch.title"), description: t("home.features.dispatch.desc") },
    { icon: Truck, title: t("home.features.fleet.title"), description: t("home.features.fleet.desc") },
    { icon: FileText, title: t("home.features.documents.title"), description: t("home.features.documents.desc") },
    { icon: BarChart3, title: t("home.features.analytics.title"), description: t("home.features.analytics.desc") },
    { icon: Sparkles, title: t("home.features.aiCopilot.title"), description: t("home.features.aiCopilot.desc") },
    { icon: Sparkles, title: t("home.features.aiWorkflow.title"), description: t("home.features.aiWorkflow.desc") },
  ]

  const benefits = [
    { icon: DollarSign, title: t("home.benefits.costs.title"), description: t("home.benefits.costs.desc") },
    { icon: Truck, title: t("home.benefits.speed.title"), description: t("home.benefits.speed.desc") },
    { icon: FileText, title: t("home.benefits.paperwork.title"), description: t("home.benefits.paperwork.desc") },
    { icon: Shield, title: t("home.benefits.scale.title"), description: t("home.benefits.scale.desc") },
  ]

  const stats = [
    { value: "6", label: t("home.stats.modules") },
    { value: t("home.stats.appsLabel"), label: t("home.stats.apps") },
    { value: t("home.stats.webLabel"), label: t("home.stats.web") },
    { value: t("home.stats.statusLabel"), label: t("home.stats.status") },
  ]

  const workflowSteps = [
    { icon: DollarSign, title: t("home.workflow.calculate.title"), description: t("home.workflow.calculate.desc") },
    { icon: Route, title: t("home.workflow.plan.title"), description: t("home.workflow.plan.desc") },
    { icon: Sparkles, title: t("home.workflow.ai.title"), description: t("home.workflow.ai.desc") },
    { icon: Send, title: t("home.workflow.dispatch.title"), description: t("home.workflow.dispatch.desc") },
  ]

  const roadmapItems = [
    { date: t("roadmap.completed"), title: t("home.roadmap.mobile.title"), description: t("home.roadmap.mobile.desc"), status: "current" as const },
    { date: t("roadmap.completed"), title: t("home.roadmap.ai.title"), description: t("home.roadmap.ai.desc"), status: "current" as const },
    { date: t("roadmap.inProgress"), title: t("home.roadmap.productization.title"), description: t("home.roadmap.productization.desc"), status: "current" as const },
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
      <SeoHead
        title={t("home.meta.title")}
        description={t("home.meta.description")}
        canonical="https://operionerp.xyz"
        ogImage="https://operionerp.xyz/logo3.png"
      />

      {/* Structured Data: SoftwareApplication + Organization + WebSite */}
      <JsonLd data={softwareApplicationSchema()} />
      <JsonLd data={organizationSchema()} />
      <JsonLd data={websiteSchema()} />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-background to-accent/20" />
        <div className="absolute inset-0 opacity-30">
          <div className="absolute -top-40 -right-40 h-80 w-80 rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 h-80 w-80 rounded-full bg-accent/20 blur-3xl" />
        </div>
        <div className="relative container-wide py-24 md:py-32 lg:py-40">
          <div className="mx-auto max-w-7xl grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              className="text-center lg:text-left flex flex-col items-center lg:items-start"
            >
              <div className="mb-6 flex flex-wrap items-center gap-3">
                <Badge variant="secondary" className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium bg-accent/10 border-accent/30">
                  <Sparkles className="h-3 w-3 text-accent-foreground" />
                  {t("home.hero.badgeAi")}
                </Badge>
              </div>
              <p className="mb-4 text-sm font-medium text-primary/80 tracking-wide uppercase">
                ARGO AI Engine
              </p>
              <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
                {t("home.hero.title")}
              </h1>
              <p className="mt-6 text-lg leading-relaxed text-muted-foreground sm:text-xl">
                {t("home.hero.subtitle")}
              </p>
              <ul className="mt-6 space-y-3">
                {[
                  "Smart Route Planning: AI handles multi-stop sequences, traffic, and driver hours automatically.",
                  "Assisted Dispatch: Single-instruction dispatch with automated driver checks and notifications.",
                  "Automated Documents: Instant generation of CMRs, invoices, and proformas with zero manual entry.",
                  "Multi-Platform Access: Desktop, mobile, and web access with transparent, affordable pricing.",
                ].map((text, i) => (
                  <motion.li
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.4, delay: 0.3 + i * 0.1, ease: [0.22, 1, 0.36, 1] }}
                    className="flex items-start gap-3"
                  >
                    <Check className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                        <span className="text-base text-foreground/80">{text}</span>
                  </motion.li>
                ))}
              </ul>
              <div className="mt-10 flex flex-col items-start gap-4 sm:flex-row">
                <Button size="xl" asChild>
                  <Link to="/waitlist" onClick={() => trackCTAClick("hero", "/")}>
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
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.85, duration: 0.5 }}
                className="mt-4 inline-flex items-center gap-2"
              >
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary/40 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-primary/60" />
                </span>
                <span className="text-xs text-muted-foreground/80">
                  {t("home.hero.trustSignal")}
                </span>
              </motion.div>
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.8, duration: 0.5 }}
                className="mt-4 text-sm text-muted-foreground"
              >
                {t("home.trustedBy")}
              </motion.p>
            </motion.div>

            {/* Right column: product visual mockup */}
            <div className="relative w-full max-w-xl mx-auto lg:max-w-none lg:mx-0 mt-12 lg:mt-0">
              <motion.div
                initial={{ opacity: 0, x: 40, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                transition={{ duration: 0.7, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
                className="relative w-full rounded-xl border border-slate-800 bg-card/60 backdrop-blur-sm shadow-2xl shadow-blue-500/10 overflow-hidden transition-all duration-500 hover:shadow-blue-500/20 hover:scale-[1.01]"
              >
                {/* Browser chrome bar */}
                <div className="h-8 flex items-center gap-2 px-3 border-b bg-muted/40">
                  <div className="flex gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground/20" />
                    <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground/20" />
                    <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground/20" />
                  </div>
                  <div className="mx-auto h-5 max-w-[140px] flex-1 rounded-md bg-muted/60 border border-border/50 flex items-center justify-center">
                    <span className="text-[10px] text-muted-foreground/50 font-mono">app.operionerp.xyz</span>
                  </div>
                </div>
                {/* Dashboard content */}
                <div className="flex">
                  {/* Left sidebar */}
                  <div className="w-10 border-r bg-muted/30 flex flex-col items-center py-4 gap-3 shrink-0">
                    <Truck className="h-4 w-4 p-0.5 bg-primary/20 text-primary rounded-md" />
                    <Route className="h-4 w-4 text-muted-foreground/60" />
                    <BarChart3 className="h-4 w-4 text-muted-foreground/60" />
                    <FileText className="h-4 w-4 text-muted-foreground/60" />
                  </div>
                  {/* Main content */}
                  <div className="flex-1 p-3 space-y-3">
                    {/* Header row */}
                    <div className="flex justify-between items-center">
                      <span className="text-[10px] font-semibold text-foreground/80 uppercase tracking-wider">Dashboard</span>
                      <div className="w-5 h-5 rounded-full bg-primary/30" />
                    </div>
                    {/* Metric cards */}
                    <div className="grid grid-cols-3 gap-2">
                      <div className="rounded-md border bg-muted/20 p-2">
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Active Routes</p>
                        <p className="text-sm font-bold text-primary">24</p>
                      </div>
                      <div className="rounded-md border bg-muted/20 p-2">
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider">On Time</p>
                        <p className="text-sm font-bold text-foreground">98%</p>
                      </div>
                      <div className="rounded-md border bg-muted/20 p-2">
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Pending</p>
                        <p className="text-sm font-bold text-foreground/80">3</p>
                      </div>
                    </div>
                    {/* Route map block */}
                    <div className="relative mx-1 flex-1 min-h-[100px] rounded-lg border bg-gradient-to-br from-primary/5 to-accent/10 overflow-hidden">
                      {/* Simple SVG route map */}
                      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 300 100" preserveAspectRatio="xMidYMid meet">
                        {/* Grid lines */}
                        <line x1="0" y1="25" x2="300" y2="25" stroke="currentColor" className="text-muted-foreground/25" strokeWidth="0.5" />
                        <line x1="0" y1="50" x2="300" y2="50" stroke="currentColor" className="text-muted-foreground/25" strokeWidth="0.5" />
                        <line x1="0" y1="75" x2="300" y2="75" stroke="currentColor" className="text-muted-foreground/25" strokeWidth="0.5" />
                        <line x1="75" y1="0" x2="75" y2="100" stroke="currentColor" className="text-muted-foreground/25" strokeWidth="0.5" />
                        <line x1="150" y1="0" x2="150" y2="100" stroke="currentColor" className="text-muted-foreground/25" strokeWidth="0.5" />
                        <line x1="225" y1="0" x2="225" y2="100" stroke="currentColor" className="text-muted-foreground/25" strokeWidth="0.5" />
                        {/* Route path */}
                        <path d="M 20 50 Q 80 20, 150 50 T 280 50" fill="none" stroke="currentColor" className="text-primary/80" strokeWidth="2" strokeDasharray="6 4">
                          <animate attributeName="stroke-dashoffset" from="0" to="-20" dur="3s" repeatCount="indefinite" />
                        </path>
                        {/* Nodes */}
                        <circle cx="20" cy="50" r="3" fill="currentColor" className="text-muted-foreground/50" />
                        <circle cx="280" cy="50" r="3" fill="currentColor" className="text-muted-foreground/50" />
                        {/* Moving truck indicator */}
                        <circle cx="150" cy="40" r="4" fill="currentColor" className="text-primary">
                          <animate attributeName="cx" values="80;230;80" dur="8s" repeatCount="indefinite" />
                          <animate attributeName="cy" values="30;60;30" dur="8s" repeatCount="indefinite" />
                        </circle>
                      </svg>
                      {/* Map label */}
                      <span className="absolute bottom-2 left-2 text-[9px] text-muted-foreground/80 font-mono">Bucharest → Cluj</span>
                    </div>
                    {/* Mini dispatch table */}
                    <div className="px-1 pb-2">
                      <div className="grid grid-cols-3 text-[9px] text-muted-foreground/70 uppercase tracking-wider border-b border-border/50 pb-1 mb-1">
                        <span>Route</span>
                        <span>Driver</span>
                        <span>Status</span>
                      </div>
                      <div className="grid grid-cols-3 items-center py-1 text-[10px]">
                        <span className="text-foreground/90">R-102</span>
                        <span className="text-muted-foreground/80">Ionescu M.</span>
                        <span className="bg-primary/30 text-primary border border-primary/20 text-[9px] px-1.5 py-0.5 rounded-full font-medium w-fit">In Transit</span>
                      </div>
                      <div className="grid grid-cols-3 items-center py-1 text-[10px]">
                        <span className="text-foreground/90">R-098</span>
                        <span className="text-muted-foreground/80">Popescu A.</span>
                        <span className="bg-amber-500/20 text-amber-300 border border-amber-500/20 text-[9px] px-1.5 py-0.5 rounded-full font-medium w-fit">Loading</span>
                      </div>
                      <div className="grid grid-cols-3 items-center py-1 text-[10px]">
                        <span className="text-foreground/90">R-105</span>
                        <span className="text-muted-foreground/80">Dumitru V.</span>
                        <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/20 text-[9px] px-1.5 py-0.5 rounded-full font-medium w-fit">Done</span>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>

          </div>
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
          {/* Route Planning mockup */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.0, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="rounded-lg border bg-card shadow-xl overflow-hidden group hover:shadow-primary/10 transition-shadow">
              {/* Browser chrome */}
              <div className="flex items-center gap-1.5 px-4 py-2 bg-muted/50 border-b">
                <div className="h-2.5 w-2.5 rounded-full bg-red-400" />
                <div className="h-2.5 w-2.5 rounded-full bg-yellow-400" />
                <div className="h-2.5 w-2.5 rounded-full bg-green-400" />
                <div className="ml-3 flex-1 max-w-[140px] rounded-md bg-background px-3 py-1 text-[10px] text-muted-foreground border">
                  app.operionerp.xyz/routes
                </div>
              </div>
              {/* Content */}
              <div className="p-3 space-y-2.5">
                <div className="flex items-center gap-2">
                  <Route className="h-4 w-4 text-primary" />
                  <span className="text-xs font-semibold">{t("home.screenshots.routePlanning")}</span>
                </div>
                {/* Mini SVG route map */}
                <div className="relative h-24 rounded-md border bg-gradient-to-br from-primary/5 to-accent/10 overflow-hidden">
                  <svg className="absolute inset-0 w-full h-full" viewBox="0 0 200 100" preserveAspectRatio="xMidYMid meet">
                    <line x1="0" y1="25" x2="200" y2="25" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
                    <line x1="0" y1="50" x2="200" y2="50" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
                    <line x1="0" y1="75" x2="200" y2="75" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
                    <line x1="50" y1="0" x2="50" y2="100" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
                    <line x1="100" y1="0" x2="100" y2="100" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
                    <line x1="150" y1="0" x2="150" y2="100" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
                    <path d="M 20 75 Q 60 25, 100 50 T 180 30" fill="none" stroke="currentColor" className="text-primary" strokeWidth="1.5" strokeDasharray="4 3">
                      <animate attributeName="stroke-dashoffset" from="0" to="-14" dur="3s" repeatCount="indefinite" />
                    </path>
                    <circle cx="20" cy="75" r="3" fill="currentColor" className="text-muted-foreground/50" />
                    <circle cx="100" cy="50" r="2.5" fill="currentColor" className="text-accent" />
                    <circle cx="180" cy="30" r="3" fill="currentColor" className="text-primary" />
                    <text x="12" y="86" className="fill-muted-foreground/50" fontSize="5">A</text>
                    <text x="174" y="24" className="fill-muted-foreground/50" fontSize="5">B</text>
                  </svg>
                </div>
                {/* Route stats */}
                <div className="grid grid-cols-2 gap-1.5">
                  <div className="rounded border bg-muted/20 p-1.5">
                    <p className="text-[9px] text-muted-foreground/70">Distance</p>
                    <p className="text-xs font-semibold">342 km</p>
                  </div>
                  <div className="rounded border bg-muted/20 p-1.5">
                    <p className="text-[9px] text-muted-foreground/70">Stops</p>
                    <p className="text-xs font-semibold">4</p>
                  </div>
                </div>
                {/* Route entry */}
                <div className="flex items-center justify-between border-t border-border/50 pt-2">
                  <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                    <MapPin className="h-3 w-3" />
                    <span>Bucharest → Cluj</span>
                  </div>
                  <Badge variant="outline" className="text-[8px] px-1.5 py-0 h-4">Optimized</Badge>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Fleet Dashboard mockup */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="rounded-lg border bg-card shadow-xl overflow-hidden group hover:shadow-primary/10 transition-shadow">
              {/* Browser chrome */}
              <div className="flex items-center gap-1.5 px-4 py-2 bg-muted/50 border-b">
                <div className="h-2.5 w-2.5 rounded-full bg-red-400" />
                <div className="h-2.5 w-2.5 rounded-full bg-yellow-400" />
                <div className="h-2.5 w-2.5 rounded-full bg-green-400" />
                <div className="ml-3 flex-1 max-w-[140px] rounded-md bg-background px-3 py-1 text-[10px] text-muted-foreground border">
                  app.operionerp.xyz/fleet
                </div>
              </div>
              {/* Content */}
              <div className="p-3 space-y-2.5">
                <div className="flex items-center gap-2">
                  <LayoutDashboard className="h-4 w-4 text-primary" />
                  <span className="text-xs font-semibold">{t("home.screenshots.fleetDashboard")}</span>
                </div>
                {/* Fleet stats row */}
                <div className="grid grid-cols-3 gap-1.5">
                  <div className="rounded border bg-muted/20 p-1.5 text-center">
                    <p className="text-[9px] text-muted-foreground/70">Active</p>
                    <p className="text-sm font-bold text-emerald-400">12</p>
                  </div>
                  <div className="rounded border bg-muted/20 p-1.5 text-center">
                    <p className="text-[9px] text-muted-foreground/70">On Route</p>
                    <p className="text-sm font-bold text-primary">8</p>
                  </div>
                  <div className="rounded border bg-muted/20 p-1.5 text-center">
                    <p className="text-[9px] text-muted-foreground/70">Idle</p>
                    <p className="text-sm font-bold text-amber-400">3</p>
                  </div>
                </div>
                {/* Vehicle list */}
                <div className="space-y-1">
                  {["TR-102", "TR-098", "TR-105"].map((truck, i) => (
                    <div key={truck} className="flex items-center justify-between rounded border bg-muted/10 p-1.5 text-[10px]">
                      <div className="flex items-center gap-1.5">
                        <Truck className="h-3 w-3 text-muted-foreground" />
                        <span className="font-medium">{truck}</span>
                      </div>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${
                        i === 0 ? "bg-emerald-500/20 text-emerald-300" :
                        i === 1 ? "bg-primary/20 text-primary" :
                        "bg-amber-500/20 text-amber-300"
                      }`}>
                        {i === 0 ? "Done" : i === 1 ? "In Transit" : "Loading"}
                      </span>
                    </div>
                  ))}
                </div>
                {/* Utilization bar */}
                <div className="pt-1">
                  <div className="flex justify-between text-[9px] text-muted-foreground mb-1">
                    <span>Fleet Utilization</span>
                    <span>72%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted/50 overflow-hidden">
                    <div className="h-full w-[72%] rounded-full bg-primary/60" />
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Dispatch Console mockup */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="rounded-lg border bg-card shadow-xl overflow-hidden group hover:shadow-primary/10 transition-shadow">
              {/* Browser chrome */}
              <div className="flex items-center gap-1.5 px-4 py-2 bg-muted/50 border-b">
                <div className="h-2.5 w-2.5 rounded-full bg-red-400" />
                <div className="h-2.5 w-2.5 rounded-full bg-yellow-400" />
                <div className="h-2.5 w-2.5 rounded-full bg-green-400" />
                <div className="ml-3 flex-1 max-w-[140px] rounded-md bg-background px-3 py-1 text-[10px] text-muted-foreground border">
                  app.operionerp.xyz/dispatch
                </div>
              </div>
              {/* Content */}
              <div className="p-3 space-y-2.5">
                <div className="flex items-center gap-2">
                  <Radio className="h-4 w-4 text-primary" />
                  <span className="text-xs font-semibold">{t("home.screenshots.dispatchConsole")}</span>
                </div>
                {/* Command input */}
                <div className="flex items-center gap-2 rounded-md border bg-muted/20 px-2.5 py-2 text-[10px] text-muted-foreground">
                  <Send className="h-3 w-3 shrink-0 text-muted-foreground/50" />
                  <span className="italic">Dispatch Truck 14 to Cluj...</span>
                </div>
                {/* Dispatch items */}
                <div className="space-y-1">
                  {[
                    { route: "R-102", driver: "Ionescu M.", status: "In Transit" as const },
                    { route: "R-098", driver: "Popescu A.", status: "Loading" as const },
                    { route: "R-105", driver: "Dumitru V.", status: "Done" as const },
                  ].map((d) => (
                    <div key={d.route} className="flex items-center justify-between rounded border bg-muted/10 p-1.5 text-[10px]">
                      <div className="flex items-center gap-2">
                        <Navigation className="h-3 w-3 text-muted-foreground/60" />
                        <span className="font-medium">{d.route}</span>
                        <span className="text-muted-foreground/60">{d.driver}</span>
                      </div>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${
                        d.status === "In Transit" ? "bg-primary/20 text-primary" :
                        d.status === "Loading" ? "bg-amber-500/20 text-amber-300" :
                        "bg-emerald-500/20 text-emerald-300"
                      }`}>{d.status}</span>
                    </div>
                  ))}
                </div>
                {/* Quick stats */}
                <div className="flex items-center justify-between border-t border-border/50 pt-2 text-[9px] text-muted-foreground">
                  <span>Pending: 2</span>
                  <span>Active: 5</span>
                  <span className="text-emerald-400">Completed: 18</span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </SectionWrapper>


      {/* Early Access Feedback */}
      <SectionWrapper className="bg-muted/30">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center"
          >
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("home.testimonials.title")}</h2>
            <p className="mt-4 text-muted-foreground">{t("home.testimonials.subtitle")}</p>
          </motion.div>
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {testimonials.map((item, i) => (
              <TestimonialCard
                key={item.name}
                quote={item.quote}
                name={item.name}
                role={item.role}
                company={item.company}
                index={i}
              />
            ))}
          </div>
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


      {/* Waitlist CTA */}
      <SectionWrapper className="bg-gradient-to-br from-primary/5 via-background to-accent/10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center"
        >
          <div className="rounded-2xl border bg-background/80 p-8 md:p-12 shadow-lg backdrop-blur-sm">
            <Users className="mx-auto h-10 w-10 text-primary mb-4" />
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("home.waitlistCta.title")}</h2>
            <p className="mt-4 text-lg text-muted-foreground max-w-xl mx-auto">
              {t("home.waitlistCta.desc")}
            </p>
            <Button size="xl" className="mt-8" asChild>
              <Link to="/waitlist" onClick={() => trackCTAClick("waitlist_section", "/")}>
                {t("home.waitlistCta.button")}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </motion.div>
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
        primaryHref="/features"
        secondaryLabel={t("home.ctaSection.secondary")}
        secondaryHref="/features"
      />
    </>
  )
}
