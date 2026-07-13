import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { Target, Zap, Leaf, Sparkles, TrendingUp, Eye, Code, Shield, HeartHandshake } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { CtaSection } from "@/components/shared/cta-section"
import { Card, CardContent } from "@/components/ui/card"

export default function MissionPage() {
  const { t } = useLocale()

  const beliefs = [
    { icon: Zap, title: t("mission.belief.empower"), description: t("mission.belief.empowerDesc") },
    { icon: Leaf, title: t("mission.belief.efficiency"), description: t("mission.belief.efficiencyDesc") },
    { icon: Sparkles, title: t("mission.belief.tools"), description: t("mission.belief.toolsDesc") },
    { icon: TrendingUp, title: t("mission.belief.data"), description: t("mission.belief.dataDesc") },
  ]

  const stats = [
    { label: t("mission.stat.development"), value: t("mission.stat.developmentValue") },
    { label: t("mission.stat.platforms"), value: t("mission.stat.platformsValue") },
    { label: t("mission.stat.community"), value: t("mission.stat.communityValue") },
    { label: t("mission.stat.headquarters"), value: t("mission.stat.headquartersValue") },
  ]

  const coreValues = [
    { icon: Eye, title: t("mission.values.transparency"), description: t("mission.values.transparencyDesc") },
    { icon: Code, title: t("mission.values.excellence"), description: t("mission.values.excellenceDesc") },
    { icon: Shield, title: t("mission.values.trust"), description: t("mission.values.trustDesc") },
    { icon: HeartHandshake, title: t("mission.values.partnership"), description: t("mission.values.partnershipDesc") },
  ]

  const commitments = [
    {
      title: t("mission.commitment.customers"),
      items: [
        t("mission.commitment.customers1"),
        t("mission.commitment.customers2"),
        t("mission.commitment.customers3"),
      ],
    },
    {
      title: t("mission.commitment.technology"),
      items: [
        t("mission.commitment.technology1"),
        t("mission.commitment.technology2"),
        t("mission.commitment.technology3"),
      ],
    },
    {
      title: t("mission.commitment.security"),
      items: [
        t("mission.commitment.security1"),
        t("mission.commitment.security2"),
        t("mission.commitment.security3"),
      ],
    },
    {
      title: t("mission.commitment.community"),
      items: [
        t("mission.commitment.community1"),
        t("mission.commitment.community2"),
        t("mission.commitment.community3"),
      ],
    },
  ]

  return (
    <>
      <Helmet>
        <title>{t("mission.meta.title")}</title>
        <meta name="description" content={t("mission.meta.description")} />
        <link rel="canonical" href="https://operion.com/mission" />
      </Helmet>
      <PageHeader title={t("mission.title")} description={t("mission.subtitle")} />

      {/* Mission Statement */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center"
        >
          <div className="flex justify-center mb-8">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
              <Target className="h-8 w-8 text-primary" />
            </div>
          </div>
          <blockquote className="text-2xl font-bold tracking-tight sm:text-3xl lg:text-4xl">
            &ldquo;{t("mission.quote")}&rdquo;
          </blockquote>
        </motion.div>
      </SectionWrapper>

      {/* Our Vision */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center"
        >
          <h2 className="text-3xl font-bold tracking-tight">{t("mission.vision")}</h2>
          <p className="mt-4 leading-relaxed text-muted-foreground max-w-2xl mx-auto">
            {t("mission.vision.p1")}
          </p>
          <p className="mt-4 leading-relaxed text-muted-foreground max-w-2xl mx-auto">
            {t("mission.vision.p2")}
          </p>
        </motion.div>
      </SectionWrapper>

      {/* What We Believe */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center mb-12"
        >
          <h2 className="text-3xl font-bold tracking-tight">{t("mission.beliefs")}</h2>
          <p className="mt-2 text-muted-foreground">{t("mission.beliefsSubtitle")}</p>
        </motion.div>
        <div className="mx-auto max-w-4xl grid gap-6 sm:grid-cols-2">
          {beliefs.map((b, i) => (
            <motion.div
              key={b.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="h-full">
                <CardContent className="p-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent mb-4">
                    <b.icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="font-semibold">{b.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{b.description}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Core Values */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl text-center mb-12"
        >
          <h2 className="text-3xl font-bold tracking-tight">{t("mission.values")}</h2>
          <p className="mt-2 text-muted-foreground">{t("mission.valuesSubtitle")}</p>
        </motion.div>
        <div className="mx-auto max-w-4xl grid gap-6 sm:grid-cols-2">
          {coreValues.map((v, i) => (
            <motion.div
              key={v.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="h-full">
                <CardContent className="p-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 mb-4">
                    <v.icon className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="text-lg font-semibold">{v.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{v.description}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Our Commitments */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <h2 className="text-2xl font-bold tracking-tight text-center">{t("mission.commitments")}</h2>
          <p className="mt-2 text-center text-muted-foreground">{t("mission.commitmentsSubtitle")}</p>
          <div className="mt-10 space-y-6">
            {commitments.map((commitment, i) => (
              <motion.div
                key={commitment.title}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                <Card>
                  <CardContent className="p-6">
                    <h3 className="text-lg font-semibold mb-3">{commitment.title}</h3>
                    <ul className="space-y-2">
                      {commitment.items.map((item, j) => (
                        <li key={j} className="flex items-start gap-3 text-sm text-muted-foreground">
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/60" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </SectionWrapper>

      {/* Our Commitment */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          <h2 className="text-2xl font-bold tracking-tight text-center">{t("mission.commitment")}</h2>
          <p className="mt-4 text-center text-muted-foreground leading-relaxed">
            {t("mission.commitmentText")}
          </p>
        </motion.div>
        <div className="mt-12 grid gap-6 grid-cols-2 sm:grid-cols-4">
          {stats.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="text-center">
                <CardContent className="p-6">
                  <p className="text-3xl font-bold text-primary">{s.value}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{s.label}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      <CtaSection
        title={t("mission.cta.title")}
        description={t("mission.cta.text")}
        primaryLabel={t("mission.cta.primary")}
        primaryHref="/register"
      />
    </>
  )
}
