import { useMemo } from "react"
import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import { useSearchParams, Link } from "react-router"
import { BookOpen, Clock } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Pagination } from "@/components/ui/pagination"
import { SearchInput } from "@/components/shared/search-input"
import { EmptyState } from "@/components/shared/empty-state"
import { useLocale } from "@/i18n/locale-context"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"

import { Tag } from "@/components/ui/tag"
import { Skeleton } from "@/components/ui/skeleton"
import { useTutorials } from "@/services/queries"
import { formatDate } from "@/lib/utils"
import { cn } from "@/lib/utils"
import { useReducedMotion } from "@/services/accessibility"
import type { Tutorial } from "@/types"

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

function getCategoryColor(category: string): string {
  const map: Record<string, string> = {
    beginner: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100",
    intermediate: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100",
    advanced: "bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-100",
    administrator: "bg-violet-100 text-violet-800 dark:bg-violet-900 dark:text-violet-100",
    dispatcher: "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-100",
    "fleet manager": "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-100",
    driver: "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-100",
    installation: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100",
    ai: "bg-fuchsia-100 text-fuchsia-800 dark:bg-fuchsia-900 dark:text-fuchsia-100",
    "ai assistant": "bg-fuchsia-100 text-fuchsia-800 dark:bg-fuchsia-900 dark:text-fuchsia-100",
    ocr: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100",
    analytics: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-100",
  }
  return map[category.toLowerCase()] ?? "bg-secondary text-secondary-foreground"
}

function TutorialCard({ tutorial, index }: { tutorial: Tutorial; index: number }) {
  const prefersReducedMotion = useReducedMotion()
  return (
    <motion.div
      initial={prefersReducedMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: prefersReducedMotion ? 0 : Math.min(index * 0.05, 0.3) }}
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
  const { t } = useLocale()
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10))
  const activeTab = (searchParams.get("category") as FilterTab) || "All"
  const search = searchParams.get("search") || ""

  const { data: tutorials = [], isLoading } = useTutorials()

  const filteredTutorials = useMemo(() => {
    let result = [...tutorials]
    if (activeTab !== "All") {
      const tabLower = activeTab.toLowerCase()
      result = result.filter((t) => t.category.toLowerCase() === tabLower)
    }
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(
        (t) =>
          t.title.toLowerCase().includes(q) ||
          t.excerpt.toLowerCase().includes(q) ||
          t.category.toLowerCase().includes(q)
      )
    }
    return result
  }, [tutorials, activeTab, search])

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
      <SeoHead
        title="Tutorials — Operion"
        description="Step-by-step tutorials for Operion ERP. Learn route planning, fleet management, dispatch, OCR, AI optimization, and more."
        canonical="https://operionerp.xyz/tutorials"
      />

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
              placeholder={t("common.searchTutorials")}
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
