import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import {
  MapPin,
  Radio,
  Send,
  Scan,
  BarChart3,
  Users,
  FileText,
  Settings,
  TrendingUp,
  UserCheck,
  Calendar,
  Wrench,
  ImageIcon,
  Plug,
} from "lucide-react"
import { PageHeader, SectionHeader } from "@/components/shared/page-header"
import { FeatureCard } from "@/components/shared/feature-card"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { FaqAccordion } from "@/components/shared/faq-accordion"
import { CtaBanner } from "@/components/shared/cta-banner"
import { Badge } from "@/components/ui/badge"

function ScreenshotPlaceholder({ name }: { name: string }) {
  const { t } = useLocale()
  return (
    <div className="mt-8 rounded-xl border border-dashed bg-muted/30 p-10 text-center">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-muted">
        <ImageIcon className="h-7 w-7 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium text-muted-foreground">{t("features.screenshot")}: {name}</p>
      <p className="mt-1 text-xs text-muted-foreground/70">{t("features.screenshotComingSoon")}</p>
    </div>
  )
}



export default function FeaturesPage() {
  const { t } = useLocale()

  const categories = [
    {
      title: t("features.route.heading"),
      problem: t("features.route.problem"),
      screenshot: "Route Planning Dashboard",
      integrations: t("features.route.integrations"),
      items: [
        { icon: MapPin, title: t("features.route.planning.title"), description: t("features.route.planning.desc") },
        { icon: TrendingUp, title: t("features.route.optimization.title"), description: t("features.route.optimization.desc") },
        { icon: Radio, title: t("features.route.traffic.title"), description: t("features.route.traffic.desc") },
      ],
    },
    {
      title: t("features.fleet.heading"),
      problem: t("features.fleet.problem"),
      screenshot: "Fleet Live Map",
      integrations: t("features.fleet.integrations"),
      items: [
        { icon: Radio, title: t("features.fleet.gps.title"), description: t("features.fleet.gps.desc") },
        { icon: Wrench, title: t("features.fleet.maintenance.title"), description: t("features.fleet.maintenance.desc") },
        { icon: MapPin, title: t("features.fleet.geofencing.title"), description: t("features.fleet.geofencing.desc") },
      ],
    },
    {
      title: t("features.dispatch.heading"),
      problem: t("features.dispatch.problem"),
      screenshot: "Dispatch Console",
      integrations: t("features.dispatch.integrations"),
      items: [
        { icon: Send, title: t("features.dispatch.jobs.title"), description: t("features.dispatch.jobs.desc") },
        { icon: FileText, title: t("features.dispatch.pod.title"), description: t("features.dispatch.pod.desc") },
        { icon: TrendingUp, title: t("features.dispatch.status.title"), description: t("features.dispatch.status.desc") },
      ],
    },
    {
      title: t("features.documents.heading"),
      problem: t("features.documents.problem"),
      screenshot: "OCR Document Scanner",
      integrations: t("features.documents.integrations"),
      items: [
        { icon: Scan, title: t("features.documents.ocr.title"), description: t("features.documents.ocr.desc") },
        { icon: FileText, title: t("features.documents.archive.title"), description: t("features.documents.archive.desc") },
        { icon: Settings, title: t("features.documents.invoicing.title"), description: t("features.documents.invoicing.desc") },
      ],
    },
    {
      title: t("features.analytics.heading"),
      problem: t("features.analytics.problem"),
      screenshot: "Analytics Dashboard",
      integrations: t("features.analytics.integrations"),
      items: [
        { icon: BarChart3, title: t("features.analytics.dashboards.title"), description: t("features.analytics.dashboards.desc") },
        { icon: TrendingUp, title: t("features.analytics.kpi.title"), description: t("features.analytics.kpi.desc") },
        { icon: Send, title: t("features.analytics.export.title"), description: t("features.analytics.export.desc") },
      ],
    },
    {
      title: t("features.driver.heading"),
      problem: t("features.driver.problem"),
      screenshot: "Driver Schedule View",
      integrations: t("features.driver.integrations"),
      items: [
        { icon: Users, title: t("features.driver.profiles.title"), description: t("features.driver.profiles.desc") },
        { icon: UserCheck, title: t("features.driver.performance.title"), description: t("features.driver.performance.desc") },
        { icon: Calendar, title: t("features.driver.schedule.title"), description: t("features.driver.schedule.desc") },
      ],
    },
  ]

  const featureFaqs = [
    { question: t("features.faq1.q"), answer: t("features.faq1.a") },
    { question: t("features.faq2.q"), answer: t("features.faq2.a") },
    { question: t("features.faq3.q"), answer: t("features.faq3.a") },
    { question: t("features.faq4.q"), answer: t("features.faq4.a") },
    { question: t("features.faq5.q"), answer: t("features.faq5.a") },
  ]

  return (
    <>
      <Helmet>
        <title>{t("features.meta.title")}</title>
        <meta
          name="description"
          content={t("features.meta.description")}
        />
        <link rel="canonical" href="https://operion.com/features" />
      </Helmet>
      <PageHeader
        title={t("features.title")}
        description={t("features.subtitle")}
      />
      {categories.map((category, ci) => (
        <SectionWrapper
          key={category.title}
          className={ci % 2 === 1 ? "bg-muted/30" : ""}
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-10"
          >
            <Badge
              variant="outline"
              className="mb-3 text-xs uppercase tracking-wider"
            >
              {t("features.section.problem")}
            </Badge>
            <h2 className="text-2xl font-bold tracking-tight">
              {category.title}
            </h2>
            <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground">
              {category.problem}
            </p>
          </motion.div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {category.items.map((item, i) => (
              <FeatureCard key={item.title} {...item} index={i} />
            ))}
          </div>
          {category.integrations && (
            <div className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
              <Plug className="h-4 w-4 shrink-0" />
              <span>{t("features.integrations")}: {category.integrations}</span>
            </div>
          )}
          <ScreenshotPlaceholder name={category.screenshot} />
        </SectionWrapper>
      ))}

      {/* FAQ */}
      <SectionWrapper>
        <SectionHeader
          title={t("features.faq")}
          description={t("features.faqSubtitle")}
          className="mb-12"
        />
        <div className="mx-auto max-w-3xl">
          <FaqAccordion items={featureFaqs} />
        </div>
      </SectionWrapper>

      {/* CTA Banner */}
      <SectionWrapper className="pb-8 md:pb-12">
        <CtaBanner
          title={t("features.cta.title")}
          description={t("features.cta.text")}
          buttonText={t("features.cta.button")}
          buttonHref="/register"
        />
      </SectionWrapper>
    </>
  )
}
