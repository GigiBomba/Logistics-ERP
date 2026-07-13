import { useState, useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { Lightbulb, Target, Calendar, Trophy, Filter } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { formatDate } from "@/lib/utils"

type RoadmapStatus = "planned" | "in_progress" | "completed"

interface RoadmapItem {
  id: string
  title: string
  description: string
  status: RoadmapStatus
  category: string
  targetDate?: string
  quarter?: string
}

const roadmapData: RoadmapItem[] = [
  {
    id: "1",
    title: "PostgreSQL / Multi-DB Support",
    description: "Adding PostgreSQL as an alternative to SQLite for production deployments with larger datasets and concurrent users.",
    status: "planned",
    category: "Architecture",
    quarter: "Q4 2026",
  },
  {
    id: "2",
    title: "Public API Stabilization",
    description: "Stabilizing the public REST API with comprehensive endpoint documentation, rate limiting, and versioning for third-party integrations.",
    status: "planned",
    category: "Integrations",
    quarter: "Q4 2026",
  },
  {
    id: "3",
    title: "Docker / Containerized Deployment",
    description: "Containerized deployment with Docker Compose for easy self-hosting, CI/CD pipelines, and production environments.",
    status: "in_progress",
    category: "DevOps",
    quarter: "Q3 2026",
  },
  {
    id: "4",
    title: "Mobile Driver Companion App",
    description: "Native mobile app for drivers with turn-by-turn navigation, proof of delivery capture, and real-time status updates.",
    status: "planned",
    category: "Mobile",
    quarter: "Q1 2027",
  },
  {
    id: "5",
    title: "FastAPI Backend Decoupling",
    description: "Decoupling the monolithic desktop app into a client-server architecture with FastAPI routers, Pydantic schemas, and a clean repository layer.",
    status: "in_progress",
    category: "Architecture",
    quarter: "Q3 2026",
  },
]

const statusFilters = [
  { value: "All", labelKey: "common.viewAll" },
  { value: "planned", labelKey: "roadmap.planned" },
  { value: "in_progress", labelKey: "roadmap.inProgress" },
  { value: "completed", labelKey: "roadmap.completed" },
] as const
const categoryFilters = ["All", "Architecture", "DevOps", "Integrations", "Mobile"] as const

const statusConfig: Record<RoadmapStatus, { labelKey: string; className: string }> = {
  planned: { labelKey: "roadmap.planned", className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" },
  in_progress: { labelKey: "roadmap.inProgress", className: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" },
  completed: { labelKey: "roadmap.completed", className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300" },
}

const statusColumnConfig: Record<RoadmapStatus, { titleKey: string; descKey: string }> = {
  planned: { titleKey: "roadmap.planned", descKey: "roadmap.plannedDesc" },
  in_progress: { titleKey: "roadmap.inProgress", descKey: "roadmap.inProgressDesc" },
  completed: { titleKey: "roadmap.completed", descKey: "roadmap.completedDesc" },
}

const categoryBadgeColors: Record<string, string> = {
  Architecture: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  DevOps: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300",
  Integrations: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  Mobile: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
}

function RoadmapCard({ item, index, t }: { item: RoadmapItem; index: number; t: (key: string) => string }) {
  const status = statusConfig[item.status]
  const categoryClass = categoryBadgeColors[item.category] || "bg-muted text-muted-foreground"

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.35, delay: index * 0.05, ease: [0.22, 1, 0.36, 1] }}
    >
      <Card className="h-full">
        <CardHeader className="p-4 pb-2">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-sm font-semibold">{item.title}</CardTitle>
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium shrink-0",
                status.className
              )}
            >
              {t(status.labelKey)}
            </span>
          </div>
        </CardHeader>
        <CardContent className="p-4 pt-2">
          <CardDescription className="text-xs leading-relaxed">
            {item.description}
          </CardDescription>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <Badge variant="outline" className={cn("text-[11px] font-medium", categoryClass)}>
              {item.category}
            </Badge>
            {item.quarter && (
              <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5">
                <Calendar className="h-3 w-3" />
                {item.quarter}
              </span>
            )}
            {item.targetDate && (
              <span className="inline-flex items-center gap-1">
                <Target className="h-3 w-3" />
                {formatDate(item.targetDate)}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

export default function RoadmapPage() {
  const { t } = useLocale()
  const [activeStatusFilter, setActiveStatusFilter] = useState<string>("All")
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string>("All")

  const filteredItems = useMemo(() => {
    let items = roadmapData
    if (activeStatusFilter !== "All") {
      items = items.filter(
        (item) => item.status === activeStatusFilter
      )
    }
    if (activeCategoryFilter !== "All") {
      items = items.filter((item) => item.category === activeCategoryFilter)
    }
    return items
  }, [activeStatusFilter, activeCategoryFilter])

  const plannedItems = filteredItems.filter((item) => item.status === "planned")
  const inProgressItems = filteredItems.filter((item) => item.status === "in_progress")
  const completedItems = filteredItems.filter((item) => item.status === "completed")

  const recentlyCompleted = roadmapData
    .filter((item) => item.status === "completed")
    .slice(0, 3)

  const showColumnLayout = activeStatusFilter === "All" && activeCategoryFilter === "All"

  return (
    <>
      <Helmet>
        <title>{t("roadmap.pageTitle")}</title>
        <meta name="description" content={t("roadmap.metaDesc")} />
        <link rel="canonical" href="https://operion.com/roadmap" />
      </Helmet>

      <PageHeader
        title={t("roadmap.title")}
        description={t("roadmap.pageDesc")}
      />

      {/* Recently Completed */}
      {recentlyCompleted.length > 0 && (
        <SectionWrapper className="py-0 md:py-0">
          <div className="mx-auto max-w-5xl">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="rounded-xl border bg-green-50 dark:bg-green-950/20 p-5"
            >
              <div className="flex items-center gap-2 mb-4">
                <Trophy className="h-5 w-5 text-green-600 dark:text-green-400" />
                <h2 className="text-sm font-semibold text-green-800 dark:text-green-300">{t("roadmap.recentlyCompleted")}</h2>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {recentlyCompleted.map((item, i) => (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, y: 10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.1 }}
                  >
                    <Card className="h-full bg-background">
                      <CardContent className="p-4">
                        <Badge variant="outline" className={cn("text-[11px] mb-2", categoryBadgeColors[item.category])}>
                          {item.category}
                        </Badge>
                        <p className="text-sm font-medium">{item.title}</p>
                        {item.quarter && (
                          <p className="mt-1 text-xs text-muted-foreground">{item.quarter}</p>
                        )}
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </div>
        </SectionWrapper>
      )}

      {/* Filters */}
      <SectionWrapper className="py-0 md:py-0">
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            {/* Status filter */}
            <div className="flex items-center gap-1 rounded-lg border bg-muted/30 p-1 flex-1">
              {statusFilters.map((filter) => (
                <button
                  key={filter.value}
                  onClick={() => setActiveStatusFilter(filter.value)}
                  className={cn(
                    "flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    activeStatusFilter === filter.value
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {t(filter.labelKey)}
                </button>
              ))}
            </div>

            {/* Category filter */}
            <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <select
                value={activeCategoryFilter}
                onChange={(e) => setActiveCategoryFilter(e.target.value)}
                className="bg-transparent text-sm font-medium text-foreground outline-none"
              >
                {categoryFilters.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </SectionWrapper>

      {/* Grid / Column Layout */}
      <SectionWrapper>
        {showColumnLayout ? (
          <div className="mx-auto max-w-5xl">
            <div className="grid gap-8 lg:grid-cols-3">
              {/* Planned Column */}
              <div>
                <div className="mb-4 flex items-center gap-2">
                  <div className="h-2.5 w-2.5 rounded-full bg-blue-500" />
                  <h3 className="text-sm font-semibold">{t(statusColumnConfig.planned.titleKey)}</h3>
                  <span className="text-xs text-muted-foreground">({plannedItems.length})</span>
                </div>
                <p className="mb-5 text-xs text-muted-foreground">{t(statusColumnConfig.planned.descKey)}</p>
                <div className="space-y-3">
                  {plannedItems.map((item, i) => (
                    <RoadmapCard key={item.id} item={item} index={i} t={t} />
                  ))}
                </div>
              </div>

              {/* In Progress Column */}
              <div>
                <div className="mb-4 flex items-center gap-2">
                  <div className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                  <h3 className="text-sm font-semibold">{t(statusColumnConfig.in_progress.titleKey)}</h3>
                  <span className="text-xs text-muted-foreground">({inProgressItems.length})</span>
                </div>
                <p className="mb-5 text-xs text-muted-foreground">{t(statusColumnConfig.in_progress.descKey)}</p>
                <div className="space-y-3">
                  {inProgressItems.map((item, i) => (
                    <RoadmapCard key={item.id} item={item} index={i} t={t} />
                  ))}
                </div>
              </div>

              {/* Completed Column */}
              <div>
                <div className="mb-4 flex items-center gap-2">
                  <div className="h-2.5 w-2.5 rounded-full bg-green-500" />
                  <h3 className="text-sm font-semibold">{t(statusColumnConfig.completed.titleKey)}</h3>
                  <span className="text-xs text-muted-foreground">({completedItems.length})</span>
                </div>
                <p className="mb-5 text-xs text-muted-foreground">{t(statusColumnConfig.completed.descKey)}</p>
                <div className="space-y-3">
                  {completedItems.map((item, i) => (
                    <RoadmapCard key={item.id} item={item} index={i} t={t} />
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-5xl">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filteredItems.map((item, i) => (
                <RoadmapCard key={item.id} item={item} index={i} t={t} />
              ))}
            </div>
            {filteredItems.length === 0 && (
              <p className="text-center text-sm text-muted-foreground py-12">{t("roadmap.noItems")}</p>
            )}
          </div>
        )}
      </SectionWrapper>

      {/* Voting Placeholder */}
      <SectionWrapper className="bg-muted/30">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-xl text-center"
        >
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-muted">
            <Lightbulb className="h-6 w-6 text-muted-foreground" />
          </div>
          <h2 className="mt-4 text-lg font-semibold">{t("roadmap.vote")}</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {t("roadmap.voteDesc")}
          </p>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
