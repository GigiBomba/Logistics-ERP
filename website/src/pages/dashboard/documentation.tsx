import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { BookOpen, MapPin, Radio, Send, Scan, BarChart3, Users, FileText, ChevronRight, Search } from "lucide-react"

import { useLocale } from "@/i18n/locale-context"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { SectionWrapper } from "@/components/shared/section-wrapper"

const categories = [
  { icon: BookOpen, titleKey: "dashboard.docsGettingStarted", descriptionKey: "dashboard.docsGettingStartedDesc", count: 5, href: "/docs/getting-started" },
  { icon: MapPin, titleKey: "dashboard.docsRoutePlanning", descriptionKey: "dashboard.docsRoutePlanningDesc", count: 8, href: "/docs/route-planning" },
  { icon: Radio, titleKey: "dashboard.docsFleetTracking", descriptionKey: "dashboard.docsFleetTrackingDesc", count: 6, href: "/docs/fleet-tracking" },
  { icon: Send, titleKey: "dashboard.docsDispatch", descriptionKey: "dashboard.docsDispatchDesc", count: 7, href: "/docs/dispatch" },
  { icon: Scan, titleKey: "dashboard.docsOcr", descriptionKey: "dashboard.docsOcrDesc", count: 4, href: "/docs/ocr" },
  { icon: BarChart3, titleKey: "dashboard.docsAnalytics", descriptionKey: "dashboard.docsAnalyticsDesc", count: 5, href: "/docs/analytics" },
  { icon: Users, titleKey: "dashboard.docsAdministration", descriptionKey: "dashboard.docsAdministrationDesc", count: 6, href: "/docs/administration" },
  { icon: FileText, titleKey: "dashboard.docsApi", descriptionKey: "dashboard.docsApiDesc", count: 3, href: "/docs/api" },
]

export default function DocumentationPage() {
  const { t } = useLocale()
  return (
    <>
      <Helmet><title>{t("dashboard.documentationTitle")}</title></Helmet>
      <SectionWrapper>
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h1 className="text-3xl font-bold tracking-tight">{t("dashboard.documentation")}</h1>
          <p className="mt-2 text-muted-foreground">{t("dashboard.learnMore")}</p>
        </motion.div>

        {/* Search Placeholder */}
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }} className="mt-8">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input className="pl-10" placeholder={t("common.searchDocumentation")} disabled />
          </div>
        </motion.div>

        {/* Categories */}
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {categories.map((cat, i) => (
            <motion.div
              key={cat.titleKey}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 + i * 0.05 }}
            >
              <Link to={cat.href}>
                <Card className="h-full transition-shadow hover:shadow-md">
                  <CardContent className="p-5">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent mb-4">
                      <cat.icon className="h-5 w-5 text-primary" />
                    </div>
                    <h3 className="font-semibold text-sm">{t(cat.titleKey)}</h3>
                    <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{t(cat.descriptionKey)}</p>
                    <div className="mt-3 flex items-center justify-between">
                      <Badge variant="secondary" className="text-xs">{cat.count} {t("dashboard.articles")}</Badge>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </motion.div>
          ))}
        </div>

        {/* Tutorials Placeholder */}
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.5 }} className="mt-12">
          <Card>
            <CardHeader>
              <CardTitle>{t("dashboard.videoTutorials")}</CardTitle>
              <CardDescription>{t("dashboard.videoTutorialsDesc")}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8">
                <BookOpen className="mx-auto h-10 w-10 text-muted-foreground/40" />
                <p className="mt-3 text-sm font-medium">{t("common.comingSoon")}</p>
                <p className="mt-1 text-xs text-muted-foreground">{t("dashboard.videoTutorialsComing")}</p>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
