import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useSearchParams, Link } from "react-router"
import { BookOpen, Clock, BarChart3, Signal } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Pagination } from "@/components/ui/pagination"
import { SearchInput } from "@/components/shared/search-input"
import { EmptyState } from "@/components/shared/empty-state"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tag } from "@/components/ui/tag"
import { Skeleton } from "@/components/ui/skeleton"
import { useTutorials } from "@/services/queries"
import { formatDate } from "@/lib/utils"
import { cn } from "@/lib/utils"

const TUTORIALS_PER_PAGE = 9

const FILTER_TABS = [
  "All",
  "Beginner",
  "Intermediate",
  "Advanced",
  "Administrator",
  "Dispatcher",
  "Fleet Manager",
  "Driver",
  "Installation",
  "AI Assistant",
  "OCR",
  "Analytics",
] as const

type FilterTab = (typeof FILTER_TABS)[number]

interface MockTutorial {
  title: string
  slug: string
  excerpt: string
  category: FilterTab
  difficulty: "Beginner" | "Intermediate" | "Advanced"
  reading_time_minutes: number
  published_at: string
}

const MOCK_TUTORIALS: MockTutorial[] = [
  {
    title: "Installing Operion ERP on Windows Server",
    slug: "installing-operion-windows-server",
    excerpt:
      "A complete walkthrough of installing Operion ERP on Windows Server 2019 or later, including database setup, IIS configuration, and firewall rules.",
    category: "Installation",
    difficulty: "Beginner",
    reading_time_minutes: 12,
    published_at: "2026-07-08T10:00:00Z",
  },
  {
    title: "Your First Route Plan: A Beginner's Guide",
    slug: "your-first-route-plan",
    excerpt:
      "Learn how to create your first optimized route in Operion. Import stops, set constraints, and dispatch to a driver in under 10 minutes.",
    category: "Beginner",
    difficulty: "Beginner",
    reading_time_minutes: 8,
    published_at: "2026-07-05T09:00:00Z",
  },
  {
    title: "Setting Up Your Fleet in 15 Minutes",
    slug: "setting-up-your-fleet",
    excerpt:
      "Add vehicles, define capacity profiles, upload inspection documents, and invite drivers. Everything you need to get your fleet operational fast.",
    category: "Fleet Manager",
    difficulty: "Beginner",
    reading_time_minutes: 15,
    published_at: "2026-07-02T08:00:00Z",
  },
  {
    title: "Dispatching Jobs to Drivers",
    slug: "dispatching-jobs-to-drivers",
    excerpt:
      "Master the dispatch workflow: create jobs, assign drivers, set priorities, and track real-time status from the central dashboard.",
    category: "Dispatcher",
    difficulty: "Beginner",
    reading_time_minutes: 10,
    published_at: "2026-06-28T11:00:00Z",
  },
  {
    title: "Understanding the Driver Mobile App",
    slug: "understanding-driver-mobile-app",
    excerpt:
      "A tour of the driver mobile app: navigation, proof of delivery, break logging, and two-way communication with dispatch.",
    category: "Driver",
    difficulty: "Beginner",
    reading_time_minutes: 6,
    published_at: "2026-06-25T10:00:00Z",
  },
  {
    title: "OCR Document Scanning for Invoices",
    slug: "ocr-document-scanning-invoices",
    excerpt:
      "Configure Operion's OCR engine to scan invoices, CMRs, and delivery receipts. Validate extracted data and sync with your billing system.",
    category: "OCR",
    difficulty: "Intermediate",
    reading_time_minutes: 14,
    published_at: "2026-06-20T09:00:00Z",
  },
  {
    title: "AI Route Optimization Deep Dive",
    slug: "ai-route-optimization-deep-dive",
    excerpt:
      "Learn how Operion's AI engine balances fuel cost, delivery windows, driver hours, and traffic to generate near-optimal routes.",
    category: "AI Assistant",
    difficulty: "Intermediate",
    reading_time_minutes: 18,
    published_at: "2026-06-18T08:00:00Z",
  },
  {
    title: "Building Custom Analytics Dashboards",
    slug: "building-custom-analytics-dashboards",
    excerpt:
      "Use the analytics builder to create personalized dashboards. Drag metrics, apply filters, and schedule automated report delivery.",
    category: "Analytics",
    difficulty: "Intermediate",
    reading_time_minutes: 11,
    published_at: "2026-06-15T10:00:00Z",
  },
  {
    title: "Geofencing and Alert Configuration",
    slug: "geofencing-alert-configuration",
    excerpt:
      "Create polygon geofences, set dwell thresholds, and configure alert routing rules so the right person gets notified at the right time.",
    category: "Administrator",
    difficulty: "Intermediate",
    reading_time_minutes: 13,
    published_at: "2026-06-12T09:00:00Z",
  },
  {
    title: "Advanced Multi-Stop Route Planning",
    slug: "advanced-multi-stop-route-planning",
    excerpt:
      "Handle complex routing scenarios: time windows, vehicle compartments, driver breaks, and real-time re-optimization mid-route.",
    category: "Dispatcher",
    difficulty: "Advanced",
    reading_time_minutes: 16,
    published_at: "2026-06-10T11:00:00Z",
  },
  {
    title: "Fleet Maintenance Scheduling",
    slug: "fleet-maintenance-scheduling",
    excerpt:
      "Set up predictive maintenance alerts, schedule vendor appointments, and block maintenance slots in your dispatch calendar.",
    category: "Fleet Manager",
    difficulty: "Intermediate",
    reading_time_minutes: 9,
    published_at: "2026-06-08T08:00:00Z",
  },
  {
    title: "Integrating with Third-Party ERPs",
    slug: "integrating-third-party-erps",
    excerpt:
      "Connect Operion to SAP, Oracle, Microsoft Dynamics, and custom systems using REST API, webhooks, and batch synchronization.",
    category: "Administrator",
    difficulty: "Advanced",
    reading_time_minutes: 20,
    published_at: "2026-06-05T10:00:00Z",
  },
  {
    title: "Driver Performance Reports",
    slug: "driver-performance-reports",
    excerpt:
      "Generate and interpret driver scorecards. Track on-time delivery, safety scores, fuel efficiency, and customer feedback.",
    category: "Analytics",
    difficulty: "Intermediate",
    reading_time_minutes: 10,
    published_at: "2026-06-02T09:00:00Z",
  },
  {
    title: "Automated Proof of Delivery Workflows",
    slug: "automated-proof-of-delivery",
    excerpt:
      "Configure digital POD capture: signatures, photos, barcodes, and timestamps. Automate downstream invoicing and customer notifications.",
    category: "Dispatcher",
    difficulty: "Intermediate",
    reading_time_minutes: 12,
    published_at: "2026-05-28T11:00:00Z",
  },
  {
    title: "System Administration and User Roles",
    slug: "system-administration-user-roles",
    excerpt:
      "Design a secure permission model. Create custom roles, manage SSO integration, audit user activity, and enforce MFA policies.",
    category: "Administrator",
    difficulty: "Advanced",
    reading_time_minutes: 15,
    published_at: "2026-05-25T10:00:00Z",
  },
]

function getCategoryColor(category: FilterTab): string {
  switch (category) {
    case "Beginner":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100"
    case "Intermediate":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100"
    case "Advanced":
      return "bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-100"
    case "Administrator":
      return "bg-violet-100 text-violet-800 dark:bg-violet-900 dark:text-violet-100"
    case "Dispatcher":
      return "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-100"
    case "Fleet Manager":
      return "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-100"
    case "Driver":
      return "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-100"
    case "Installation":
      return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100"
    case "AI Assistant":
      return "bg-fuchsia-100 text-fuchsia-800 dark:bg-fuchsia-900 dark:text-fuchsia-100"
    case "OCR":
      return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100"
    case "Analytics":
      return "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-100"
    default:
      return "bg-secondary text-secondary-foreground"
  }
}

function getDifficultyVariant(difficulty: string) {
  switch (difficulty) {
    case "Beginner":
      return "success"
    case "Intermediate":
      return "secondary"
    case "Advanced":
      return "destructive"
    default:
      return "outline"
  }
}

function getDifficultyIcon(difficulty: string) {
  switch (difficulty) {
    case "Beginner":
      return <Signal className="h-3 w-3" />
    case "Intermediate":
      return <BarChart3 className="h-3 w-3" />
    case "Advanced":
      return <BarChart3 className="h-3 w-3" />
    default:
      return null
  }
}

function TutorialCard({ tutorial, index }: { tutorial: MockTutorial; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.05 }}
    >
      <Card className="group flex h-full flex-col transition-shadow hover:shadow-md">
        <CardHeader className="pb-3">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center rounded-md border border-transparent px-2.5 py-0.5 text-xs font-semibold shadow",
                getCategoryColor(tutorial.category)
              )}
            >
              {tutorial.category}
            </span>
            <Badge variant={getDifficultyVariant(tutorial.difficulty) as never} className="gap-1 text-xs">
              {getDifficultyIcon(tutorial.difficulty)}
              {tutorial.difficulty}
            </Badge>
          </div>
          <Link
            to={`/tutorials/${tutorial.slug}`}
            className="block transition-colors group-hover:text-primary"
          >
            <CardTitle className="text-lg leading-snug">{tutorial.title}</CardTitle>
          </Link>
          <CardDescription className="mt-2 line-clamp-3">{tutorial.excerpt}</CardDescription>
        </CardHeader>
        <CardContent className="flex-1" />
        <CardFooter className="flex items-center justify-between border-t pt-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" />
            {tutorial.reading_time_minutes} min read
          </span>
          <span>{formatDate(tutorial.published_at)}</span>
        </CardFooter>
      </Card>
    </motion.div>
  )
}

function TutorialsSkeleton() {
  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex flex-col gap-3">
          <Skeleton className="h-5 w-24 rounded-full" />
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
          <div className="mt-auto flex items-center justify-between pt-4">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-24" />
          </div>
        </div>
      ))}
    </div>
  )
}

export default function TutorialsListPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10))
  const activeTab = (searchParams.get("category") as FilterTab) || "All"
  const search = searchParams.get("search") || ""

  const { isLoading } = useTutorials()

  const allTutorials = MOCK_TUTORIALS

  const filteredTutorials = useMemo(() => {
    let result = [...allTutorials]
    if (activeTab !== "All") {
      result = result.filter(
        (t) =>
          t.category === activeTab ||
          t.difficulty === activeTab
      )
    }
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(
        (t) =>
          t.title.toLowerCase().includes(q) ||
          t.excerpt.toLowerCase().includes(q) ||
          t.category.toLowerCase().includes(q) ||
          t.difficulty.toLowerCase().includes(q)
      )
    }
    return result
  }, [allTutorials, activeTab, search])

  const totalPages = Math.max(1, Math.ceil(filteredTutorials.length / TUTORIALS_PER_PAGE))
  const safePage = Math.min(page, totalPages)
  const paginatedTutorials = filteredTutorials.slice(
    (safePage - 1) * TUTORIALS_PER_PAGE,
    safePage * TUTORIALS_PER_PAGE
  )

  const handlePageChange = (newPage: number) => {
    const params = new URLSearchParams(searchParams)
    if (newPage === 1) {
      params.delete("page")
    } else {
      params.set("page", String(newPage))
    }
    setSearchParams(params, { replace: true })
  }

  const handleTabChange = (tab: FilterTab) => {
    const params = new URLSearchParams(searchParams)
    params.delete("page")
    if (tab === "All") {
      params.delete("category")
    } else {
      params.set("category", tab)
    }
    setSearchParams(params, { replace: true })
  }

  const handleSearchChange = (value: string) => {
    const params = new URLSearchParams(searchParams)
    params.delete("page")
    if (value) {
      params.set("search", value)
    } else {
      params.delete("search")
    }
    setSearchParams(params, { replace: true })
  }

  return (
    <>
      <Helmet>
        <title>Tutorials — Operion</title>
        <meta
          name="description"
          content="Step-by-step tutorials for Operion ERP. Learn route planning, fleet management, dispatch, OCR, AI optimization, and more."
        />
      </Helmet>

      <PageHeader
        title="Tutorials"
        description="Step-by-step guides to help you get the most out of Operion ERP. From your first route plan to advanced system administration."
      />

      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mb-10 space-y-6"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <SearchInput
              placeholder="Search tutorials..."
              value={search}
              onChange={handleSearchChange}
              className="w-full sm:max-w-sm"
            />
            <div className="text-sm text-muted-foreground">
              {filteredTutorials.length} tutorial{filteredTutorials.length !== 1 ? "s" : ""}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {FILTER_TABS.map((tab) => (
              <Tag
                key={tab}
                variant={activeTab === tab ? "default" : "outline"}
                onClick={() => handleTabChange(tab)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    handleTabChange(tab)
                  }
                }}
                className={cn(
                  "cursor-pointer",
                  activeTab === tab && "bg-primary text-primary-foreground hover:bg-primary/90"
                )}
              >
                {tab}
              </Tag>
            ))}
          </div>
        </motion.div>

        {isLoading ? (
          <TutorialsSkeleton />
        ) : paginatedTutorials.length > 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
          >
            {paginatedTutorials.map((tutorial, i) => (
              <TutorialCard key={tutorial.slug} tutorial={tutorial} index={i} />
            ))}
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
          >
            <EmptyState
              icon={<BookOpen className="h-12 w-12 text-muted-foreground/50" />}
              title="No tutorials found"
              description="Try adjusting your search or category filter to find what you're looking for."
              action={
                <button
                  onClick={() =>
                    setSearchParams(new URLSearchParams(), { replace: true })
                  }
                  className="text-sm font-medium text-primary hover:underline"
                >
                  Clear all filters
                </button>
              }
            />
          </motion.div>
        )}

        {paginatedTutorials.length > 0 && totalPages > 1 && (
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="mt-12 flex justify-center"
          >
            <Pagination
              currentPage={safePage}
              totalPages={totalPages}
              onPageChange={handlePageChange}
            />
          </motion.div>
        )}
      </SectionWrapper>
    </>
  )
}
