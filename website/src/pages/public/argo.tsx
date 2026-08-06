import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { Cpu, Bot, Layers, Users, ArrowRight, Zap, FileText, BarChart3, Globe, CheckCircle, Navigation, Gauge, HeartHandshake } from "lucide-react"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export default function ArgoPage() {
  const { t } = useLocale()

  const problems = [
    t("argo.slide2.problems.0"),
    t("argo.slide2.problems.1"),
    t("argo.slide2.problems.2"),
    t("argo.slide2.problems.3"),
    t("argo.slide2.problems.4"),
    t("argo.slide2.problems.5"),
    t("argo.slide2.problems.6"),
    t("argo.slide2.problems.7"),
    t("argo.slide2.problems.8"),
  ]

  const traditionalSteps = [
    { icon: Globe, label: t("argo.slide3.steps.0") },
    { icon: FileText, label: t("argo.slide3.steps.1") },
    { icon: BarChart3, label: t("argo.slide3.steps.2") },
    { icon: Users, label: t("argo.slide3.steps.3") },
    { icon: FileText, label: t("argo.slide3.steps.4") },
    { icon: Layers, label: t("argo.slide3.steps.5") },
    { icon: FileText, label: t("argo.slide3.steps.6") },
    { icon: BarChart3, label: t("argo.slide3.steps.7") },
  ]

  const argoActions = [
    t("argo.slide4.actions.0"),
    t("argo.slide4.actions.1"),
    t("argo.slide4.actions.2"),
    t("argo.slide4.actions.3"),
    t("argo.slide4.actions.4"),
    t("argo.slide4.actions.5"),
    t("argo.slide4.actions.6"),
    t("argo.slide4.actions.7"),
    t("argo.slide4.actions.8"),
    t("argo.slide4.actions.9"),
  ]

  const autoPrepared = [
    t("argo.slide5.prepared.0"),
    t("argo.slide5.prepared.1"),
    t("argo.slide5.prepared.2"),
    t("argo.slide5.prepared.3"),
    t("argo.slide5.prepared.4"),
    t("argo.slide5.prepared.5"),
    t("argo.slide5.prepared.6"),
  ]

  const examples = [
    t("argo.slide7.examples.0"),
    t("argo.slide7.examples.1"),
    t("argo.slide7.examples.2"),
    t("argo.slide7.examples.3"),
    t("argo.slide7.examples.4"),
    t("argo.slide7.examples.5"),
  ]

  const exchanges = [
    t("argo.slide8.exchanges.0"),
    t("argo.slide8.exchanges.1"),
    t("argo.slide8.exchanges.2"),
    t("argo.slide8.exchanges.3"),
    t("argo.slide8.exchanges.4"),
    t("argo.slide8.exchanges.5"),
  ]

  const evaluationFactors = [
    t("argo.slide9.factors.0"),
    t("argo.slide9.factors.1"),
    t("argo.slide9.factors.2"),
    t("argo.slide9.factors.3"),
    t("argo.slide9.factors.4"),
    t("argo.slide9.factors.5"),
    t("argo.slide9.factors.6"),
  ]

  const pillars = [
    { icon: Bot, title: t("argo.slide10.pillars.0.title"), desc: t("argo.slide10.pillars.0.desc") },
    { icon: HeartHandshake, title: t("argo.slide10.pillars.1.title"), desc: t("argo.slide10.pillars.1.desc") },
    { icon: Zap, title: t("argo.slide10.pillars.2.title"), desc: t("argo.slide10.pillars.2.desc") },
    { icon: Gauge, title: t("argo.slide10.pillars.3.title"), desc: t("argo.slide10.pillars.3.desc") },
  ]

  const argoCan = [
    t("argo.slide11.argoCan.0"),
    t("argo.slide11.argoCan.1"),
    t("argo.slide11.argoCan.2"),
    t("argo.slide11.argoCan.3"),
    t("argo.slide11.argoCan.4"),
    t("argo.slide11.argoCan.5"),
  ]

  const humanMust = [
    t("argo.slide11.humanMust.0"),
    t("argo.slide11.humanMust.1"),
    t("argo.slide11.humanMust.2"),
    t("argo.slide11.humanMust.3"),
  ]

  const futureQueries = [
    t("argo.slide13.future.0"),
    t("argo.slide13.future.1"),
    t("argo.slide13.future.2"),
    t("argo.slide13.future.3"),
  ]

  return (
    <>
      <SeoHead
        title={t("argo.meta.title")}
        description={t("argo.meta.description")}
        canonical="https://operionerp.xyz/argo"
      />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-background to-accent/20" />
        <div className="absolute inset-0 opacity-20">
          <div className="absolute -top-40 -right-40 h-80 w-80 rounded-full bg-accent/30 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 h-80 w-80 rounded-full bg-primary/20 blur-3xl" />
        </div>
        <div className="relative container-wide py-20 md:py-28 lg:py-32">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto max-w-4xl text-center"
          >
            <Badge variant="secondary" className="mb-4 inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium">
              <Cpu className="h-3 w-3" />
              {t("argo.hero.badge")}
            </Badge>
            <h1 className="text-5xl font-bold tracking-tight sm:text-6xl lg:text-7xl">
              ARGO
            </h1>
            <p className="mt-4 text-xl font-semibold text-muted-foreground sm:text-2xl">
              {t("argo.hero.tagline")}
            </p>
            <p className="mt-6 text-lg leading-relaxed text-muted-foreground max-w-2xl mx-auto">
              {t("argo.hero.subtitle")}
            </p>
          </motion.div>
        </div>
      </section>

      {/* Slide 2 — Why ARGO Exists */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <Badge className="mb-4">01</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide2.title")}</h2>
          <p className="mt-4 text-lg text-muted-foreground">{t("argo.slide2.intro")}</p>
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {problems.map((p, i) => (
              <motion.div
                key={p}
                initial={{ opacity: 0, x: -10 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="flex items-center gap-2 rounded-lg border bg-background/80 px-4 py-2.5 text-sm"
              >
                <span className="text-muted-foreground">•</span>
                <span>{p}</span>
              </motion.div>
            ))}
          </div>
          <p className="mt-6 text-muted-foreground border-l-2 border-primary/40 pl-4 italic">
            {t("argo.slide2.stats")}
          </p>
          <p className="mt-4 font-medium text-foreground">{t("argo.slide2.closing")}</p>
        </motion.div>
      </SectionWrapper>

      {/* Slide 3 — The Problem */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <Badge className="mb-4">02</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide3.title")}</h2>
          <p className="mt-4 text-muted-foreground text-lg">{t("argo.slide3.subtitle")}</p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            {traditionalSteps.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, scale: 0.95 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="flex items-center gap-2 rounded-lg border bg-card px-4 py-2.5 text-sm font-medium shadow-sm"
              >
                <s.icon className="h-4 w-4 text-primary" />
                <span>{s.label}</span>
                {i < traditionalSteps.length - 1 && (
                  <ArrowRight className="ml-1 h-3 w-3 text-muted-foreground/40" />
                )}
              </motion.div>
            ))}
          </div>
          <p className="mt-8 text-center text-muted-foreground border-t pt-6">
            {t("argo.slide3.closing")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* Slide 4 — The ARGO Workflow */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <Badge className="mb-4">03</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide4.title")}</h2>
          <div className="mt-6 rounded-xl border bg-card p-6 shadow-sm">
            <p className="text-lg font-medium italic text-muted-foreground">
              <span className="text-primary">&ldquo;</span>
              {t("argo.slide4.request")}
              <span className="text-primary">&rdquo;</span>
            </p>
          </div>
          <p className="mt-6 text-muted-foreground font-medium">{t("argo.slide4.autoLabel")}</p>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {argoActions.map((a, i) => (
              <motion.div
                key={a}
                initial={{ opacity: 0, y: 5 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.03 }}
                className="flex items-center gap-2 rounded-lg bg-background/80 px-4 py-2 text-sm"
              >
                <CheckCircle className="h-4 w-4 shrink-0 text-primary" />
                <span>{a}</span>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </SectionWrapper>

      {/* Slide 5 — Example Outcome */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <Badge className="mb-4">04</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide5.title")}</h2>
          <Card className="mt-8 border-primary/20 bg-gradient-to-br from-primary/5 via-background to-accent/10">
            <CardContent className="p-6 md:p-8">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-sm text-muted-foreground">{t("argo.slide5.truckLabel")}</p>
                  <p className="font-semibold">{t("argo.slide5.truckValue")}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t("argo.slide5.unloadLabel")}</p>
                  <p className="font-semibold">{t("argo.slide5.unloadValue")}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t("argo.slide5.loadLabel")}</p>
                  <p className="font-semibold">{t("argo.slide5.loadValue")}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t("argo.slide5.emptyLabel")}</p>
                  <p className="font-semibold">{t("argo.slide5.emptyValue")}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t("argo.slide5.profitLabel")}</p>
                  <p className="font-semibold text-green-600 dark:text-green-400">{t("argo.slide5.profitValue")}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t("argo.slide5.reloadLabel")}</p>
                  <p className="font-semibold">{t("argo.slide5.reloadValue")}</p>
                </div>
                <div className="sm:col-span-2">
                  <p className="text-sm text-muted-foreground">{t("argo.slide5.legalLabel")}</p>
                  <p className="font-semibold text-green-600 dark:text-green-400">{t("argo.slide5.legalValue")}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <div className="mt-6">
            <p className="font-medium mb-3">{t("argo.slide5.autoHeading")}</p>
            <div className="flex flex-wrap gap-2">
              {autoPrepared.map((item) => (
                <Badge key={item} variant="secondary" className="gap-1.5 py-1.5">
                  <CheckCircle className="h-3 w-3 text-primary" />
                  {item}
                </Badge>
              ))}
            </div>
          </div>
          <p className="mt-6 text-center text-sm font-medium border-t pt-6 text-muted-foreground">
            {t("argo.slide5.humanNote")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* Slide 6 — What Makes ARGO Different */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <Badge className="mb-4">05</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide6.title")}</h2>
          <p className="mt-4 text-lg text-muted-foreground">{t("argo.slide6.intro")}</p>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            <Card className="border-muted">
              <CardContent className="p-6">
                <h3 className="text-lg font-semibold text-muted-foreground">{t("argo.slide6.tmsTitle")}</h3>
                <ul className="mt-4 space-y-2">
                  <li className="flex items-center gap-2 text-sm">• {t("argo.slide6.tms1")}</li>
                  <li className="flex items-center gap-2 text-sm">• {t("argo.slide6.tms2")}</li>
                  <li className="flex items-center gap-2 text-sm">• {t("argo.slide6.tms3")}</li>
                </ul>
              </CardContent>
            </Card>
            <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-background">
              <CardContent className="p-6">
                <h3 className="text-lg font-semibold text-primary">ARGO</h3>
                <ul className="mt-4 space-y-2">
                  <li className="flex items-center gap-2 text-sm">• {t("argo.slide6.argo1")}</li>
                  <li className="flex items-center gap-2 text-sm">• {t("argo.slide6.argo2")}</li>
                  <li className="flex items-center gap-2 text-sm">• {t("argo.slide6.argo3")}</li>
                </ul>
              </CardContent>
            </Card>
          </div>
          <p className="mt-8 text-center font-medium text-muted-foreground">
            {t("argo.slide6.closing")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* Slide 7 — Natural Language Operations */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <Badge className="mb-4">06</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide7.title")}</h2>
          <p className="mt-4 text-lg text-muted-foreground">{t("argo.slide7.intro")}</p>
          <div className="mt-8 grid gap-3 sm:grid-cols-2">
            {examples.map((ex, i) => (
              <motion.div
                key={ex}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="rounded-lg border bg-card px-5 py-4 shadow-sm"
              >
                <p className="text-sm font-medium italic text-muted-foreground">
                  <span className="text-primary">&ldquo;</span>{ex}<span className="text-primary">&rdquo;</span>
                </p>
              </motion.div>
            ))}
          </div>
          <p className="mt-6 text-center text-muted-foreground">{t("argo.slide7.closing")}</p>
        </motion.div>
      </SectionWrapper>

      {/* Slide 8 — Freight Exchange Intelligence */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <Badge className="mb-4">07</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide8.title")}</h2>
          <p className="mt-4 text-lg text-muted-foreground">{t("argo.slide8.intro")}</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            {exchanges.map((ex) => (
              <Badge key={ex} variant="outline" className="px-4 py-2 text-sm font-medium">
                {ex}
              </Badge>
            ))}
          </div>
          <p className="mt-6 text-muted-foreground">{t("argo.slide8.closing")}</p>
        </motion.div>
      </SectionWrapper>

      {/* Slide 9 — The Empty Kilometer Mission */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <Badge className="mb-4">08</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide9.title")}</h2>
          <p className="mt-4 text-lg text-muted-foreground">{t("argo.slide9.intro")}</p>
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {evaluationFactors.map((f, i) => (
              <motion.div
                key={f}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="flex items-center gap-2 rounded-lg border bg-background/80 px-4 py-2.5 text-sm"
              >
                <Navigation className="h-4 w-4 shrink-0 text-primary" />
                <span>{f}</span>
              </motion.div>
            ))}
          </div>
          <p className="mt-6 text-muted-foreground border-l-2 border-primary/40 pl-4 italic">
            {t("argo.slide9.closing")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* Slide 10 — The Four Pillars of Operion */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <Badge className="mb-4">09</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide10.title")}</h2>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            {pillars.map((p, i) => (
              <motion.div
                key={p.title}
                initial={{ opacity: 0, y: 15 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                <Card className="h-full">
                  <CardContent className="p-6">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-4">
                      <p.icon className="h-5 w-5 text-primary" />
                    </div>
                    <h3 className="font-semibold">{p.title}</h3>
                    <p className="mt-2 text-sm text-muted-foreground">{p.desc}</p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
          <p className="mt-6 text-center text-sm font-medium text-muted-foreground italic">
            {t("argo.slide10.closing")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* Slide 11 — Human-in-the-Loop */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <Badge className="mb-4">10</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide11.title")}</h2>
          <p className="mt-4 text-lg text-muted-foreground">{t("argo.slide11.intro")}</p>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            <Card>
              <CardContent className="p-6">
                <h3 className="font-semibold text-primary">{t("argo.slide11.argoTitle")}</h3>
                <ul className="mt-4 space-y-2">
                  {argoCan.map((item) => (
                    <li key={item} className="flex items-center gap-2 text-sm">
                      <CheckCircle className="h-4 w-4 shrink-0 text-primary" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
            <Card className="border-amber-200 dark:border-amber-800">
              <CardContent className="p-6">
                <h3 className="font-semibold text-amber-600 dark:text-amber-400">{t("argo.slide11.humanTitle")}</h3>
                <ul className="mt-4 space-y-2">
                  {humanMust.map((item) => (
                    <li key={item} className="flex items-center gap-2 text-sm">
                      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-amber-400 text-xs text-amber-600 dark:text-amber-400">!</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>
          <p className="mt-6 text-center text-muted-foreground">{t("argo.slide11.closing")}</p>
        </motion.div>
      </SectionWrapper>

      {/* Slide 12 — The Bigger Vision */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl text-center"
        >
          <Badge className="mb-4">11</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide12.title")}</h2>
          <p className="mt-4 text-lg text-muted-foreground">{t("argo.slide12.intro")}</p>
          <div className="mt-10 rounded-xl border-2 border-primary/30 bg-gradient-to-br from-primary/5 via-background to-accent/10 p-8 md:p-12">
            <p className="text-2xl font-bold tracking-tight sm:text-3xl leading-relaxed">
              {t("argo.slide12.vision")}
            </p>
          </div>
          <p className="mt-6 text-muted-foreground">{t("argo.slide12.closing")}</p>
        </motion.div>
      </SectionWrapper>

      {/* Slide 13 — The Future */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-4xl"
        >
          <Badge className="mb-4">12</Badge>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("argo.slide13.title")}</h2>
          <p className="mt-4 text-lg text-muted-foreground">{t("argo.slide13.intro")}</p>
          <div className="mt-8 space-y-3">
            {futureQueries.map((q, i) => (
              <motion.div
                key={q}
                initial={{ opacity: 0, x: -10 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="rounded-lg border bg-card px-5 py-4 shadow-sm"
              >
                <p className="text-sm font-medium italic text-muted-foreground">
                  <span className="text-primary">&ldquo;</span>{q}<span className="text-primary">&rdquo;</span>
                </p>
              </motion.div>
            ))}
          </div>
          <p className="mt-6 text-center text-muted-foreground">{t("argo.slide13.closing")}</p>
        </motion.div>
      </SectionWrapper>

      {/* Slide 14 — Closing */}
      <SectionWrapper className="bg-gradient-to-br from-primary/10 via-background to-accent/20">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center"
        >
          <Badge className="mb-4">13</Badge>
          <p className="text-2xl font-semibold italic text-muted-foreground">
            {t("argo.slide14.tagline")}
          </p>
          <div className="mt-10 grid gap-4 sm:grid-cols-4">
            <div className="rounded-lg border bg-background/80 px-4 py-3 text-sm font-medium">
              {t("argo.slide14.item1")}
            </div>
            <div className="rounded-lg border bg-background/80 px-4 py-3 text-sm font-medium">
              {t("argo.slide14.item2")}
            </div>
            <div className="rounded-lg border bg-background/80 px-4 py-3 text-sm font-medium">
              {t("argo.slide14.item3")}
            </div>
            <div className="rounded-lg border bg-background/80 px-4 py-3 text-sm font-medium">
              {t("argo.slide14.item4")}
            </div>
          </div>
          <p className="mt-10 text-lg text-muted-foreground">
            {t("argo.slide14.closing")}
          </p>
          <p className="mt-8 text-2xl font-bold tracking-tight">
            {t("argo.slide14.final")}
          </p>
        </motion.div>
      </SectionWrapper>
    </>
  )
}

