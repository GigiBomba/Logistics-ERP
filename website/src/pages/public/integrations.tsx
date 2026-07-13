import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion, AnimatePresence } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import {
  Truck,
  Calculator,
  MessageSquare,
  BarChart3,
  Building2,
  Webhook,
  Zap,
  Code2,
  Puzzle,
  ExternalLink,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CtaBanner } from "@/components/shared/cta-banner"

const categories = ["All", "Telematics", "Accounting", "Communication", "Analytics", "ERP"]

const integrations = [
  {
    name: "Google Maps",
    initials: "GM",
    color: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
    description: "Route visualization, geocoding, and distance matrix for accurate ETAs.",
    category: "Telematics",
    status: "Available",
    statusVariant: "success" as const,
  },
  {
    name: "TomTom",
    initials: "TT",
    color: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
    description: "Traffic-aware routing and real-time road intelligence for fleet optimization.",
    category: "Telematics",
    status: "Available",
    statusVariant: "success" as const,
  },
  {
    name: "HERE Maps",
    initials: "HE",
    color: "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300",
    description: "Precise mapping and truck-specific routing with height and weight restrictions.",
    category: "Telematics",
    status: "Available",
    statusVariant: "success" as const,
  },
  {
    name: "Geotab",
    initials: "GT",
    color: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
    description: "Vehicle telematics integration for diagnostics, fuel usage, and driver safety.",
    category: "Telematics",
    status: "Beta",
    statusVariant: "secondary" as const,
  },
  {
    name: "Garmin",
    initials: "GA",
    color: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
    description: "Fleet device management and in-cab navigation for commercial drivers.",
    category: "Telematics",
    status: "Planned",
    statusVariant: "outline" as const,
  },
  {
    name: "QuickBooks",
    initials: "QB",
    color: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
    description: "Sync invoices, expenses, and payroll data directly into your accounting flow.",
    category: "Accounting",
    status: "Available",
    statusVariant: "success" as const,
  },
  {
    name: "Xero",
    initials: "XE",
    color: "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300",
    description: "Cloud accounting integration for real-time financial visibility across jobs.",
    category: "Accounting",
    status: "Planned",
    statusVariant: "outline" as const,
  },
  {
    name: "SAP",
    initials: "SP",
    color: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
    description: "Enterprise resource planning sync for procurement, inventory, and fulfillment.",
    category: "ERP",
    status: "Planned",
    statusVariant: "outline" as const,
  },
  {
    name: "Slack",
    initials: "SL",
    color: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300",
    description: "Dispatch alerts, delivery notifications, and team coordination in channels.",
    category: "Communication",
    status: "Available",
    statusVariant: "success" as const,
  },
  {
    name: "Microsoft Teams",
    initials: "MT",
    color: "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
    description: "Operational updates and driver check-ins delivered to your team workspace.",
    category: "Communication",
    status: "Planned",
    statusVariant: "outline" as const,
  },
  {
    name: "Power BI",
    initials: "PB",
    color: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
    description: "Export fleet metrics and operational KPIs into interactive business reports.",
    category: "Analytics",
    status: "Beta",
    statusVariant: "secondary" as const,
  },
  {
    name: "Tableau",
    initials: "TB",
    color: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
    description: "Advanced data visualization and custom dashboards for logistics insights.",
    category: "Analytics",
    status: "Planned",
    statusVariant: "outline" as const,
  },
]

const categoryIcons: Record<string, React.ReactNode> = {
  All: <Puzzle className="h-4 w-4" />,
  Telematics: <Truck className="h-4 w-4" />,
  Accounting: <Calculator className="h-4 w-4" />,
  Communication: <MessageSquare className="h-4 w-4" />,
  Analytics: <BarChart3 className="h-4 w-4" />,
  ERP: <Building2 className="h-4 w-4" />,
}

export default function IntegrationsPage() {
  const { t } = useLocale()
  const [activeCategory, setActiveCategory] = useState("All")

  const filtered =
    activeCategory === "All"
      ? integrations
      : integrations.filter((i) => i.category === activeCategory)

  return (
    <>
      <Helmet>
        <title>{t("integrations.pageTitle")}</title>
        <meta
          name="description"
          content={t("integrations.metaDesc")}
        />
      </Helmet>

      <HeroSection
        title={t("integrations.title")}
        description={t("integrations.heroDesc")}
        align="center"
        size="large"
      />

      {/* Category Filter */}
      <SectionWrapper className="pb-8">
        <div className="flex flex-wrap items-center justify-center gap-2">
          {categories.map((cat) => (
            <Button
              key={cat}
              variant={activeCategory === cat ? "default" : "outline"}
              size="sm"
              onClick={() => setActiveCategory(cat)}
              className="gap-1.5"
            >
              {categoryIcons[cat]}
              {t(`integrations.category.${cat.toLowerCase()}`)}
            </Button>
          ))}
        </div>
      </SectionWrapper>

      {/* Integration Grid */}
      <SectionWrapper className="bg-muted/30 pt-0">
        <SectionHeader
          title={t("integrations.connected")}
          description={t("integrations.connectedDesc")}
          className="mb-12"
        />
        <motion.div layout className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <AnimatePresence mode="popLayout">
            {filtered.map((integration, i) => (
              <motion.div
                key={integration.name}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.3, delay: i * 0.05, ease: [0.22, 1, 0.36, 1] }}
              >
                <Card className="group h-full transition-shadow hover:shadow-md">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold ${integration.color}`}
                        >
                          {integration.initials}
                        </div>
                        <div>
                          <CardTitle className="text-base">{integration.name}</CardTitle>
                          <p className="text-xs text-muted-foreground">{t(`integrations.category.${integration.category.toLowerCase()}`)}</p>
                        </div>
                      </div>
                      <Badge variant={integration.statusVariant} className="text-[10px]">
                        {t(`integrations.status.${integration.status.toLowerCase()}`)}
                      </Badge>
                    </div>
                    <CardDescription className="mt-3 text-sm leading-relaxed">
                      {integration.description}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <Button variant="ghost" size="sm" className="px-0 text-primary hover:bg-transparent hover:underline">
                      {t("common.learnMore")}
                      <ExternalLink className="ml-1 h-3.5 w-3.5" />
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
        </motion.div>
      </SectionWrapper>

      {/* Future Integrations */}
      <SectionWrapper>
        <SectionHeader
          title={t("integrations.future")}
          description={t("integrations.futureDesc")}
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              icon: Webhook,
              titleKey: "integrations.webhooks",
              descKey: "integrations.webhooksDesc",
            },
            {
              icon: Code2,
              titleKey: "integrations.restApi",
              descKey: "integrations.restApiDesc",
            },
            {
              icon: Puzzle,
              titleKey: "integrations.sdk",
              descKey: "integrations.sdkDesc",
            },
            {
              icon: Zap,
              titleKey: "integrations.zapier",
              descKey: "integrations.zapierDesc",
            },
          ].map((item, i) => (
            <motion.div
              key={item.titleKey}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
            >
              <Card className="h-full">
                <CardHeader>
                  <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-base">{t(item.titleKey)}</CardTitle>
                  <CardDescription className="text-sm leading-relaxed">
                    {t(item.descKey)}
                  </CardDescription>
                </CardHeader>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* CTA Banner */}
      <SectionWrapper className="pb-24">
        <CtaBanner
          title={t("integrations.ctaTitle")}
          description={t("integrations.ctaDesc")}
          buttonText={t("integrations.ctaButton")}
          buttonHref="/contact"
          variant="outline"
        />
      </SectionWrapper>
    </>
  )
}
