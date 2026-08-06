import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useParams } from "react-router"
import { useLocale } from "@/i18n/locale-context"
import { motion } from "motion/react"
import { ChevronRight, BookOpen, Clock } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { SearchInput } from "@/components/shared/search-input"
import { docsConfig } from "@/config/site"

// ─── Data ───────────────────────────────────────────────────────────

interface ArticleEntry {
  title: string
  slug: string
  excerpt: string
  wordCount?: number
}

interface CategoryData {
  title: string
  description: string
  articles: ArticleEntry[]
}

const categoriesData: Record<string, CategoryData> = {
  "getting-started": {
    title: "Getting Started",
    description: "Installation, setup, and your first steps with Operion ERP.",
    articles: [
      { title: "Installing Operion ERP", slug: "installation", excerpt: "Download and install the Operion desktop application on Windows.", wordCount: 210 },
      { title: "Creating Your Account", slug: "creating-account", excerpt: "Set up your Operion account and configure your company profile.", wordCount: 95 },
      { title: "System Requirements", slug: "system-requirements", excerpt: "Hardware and software requirements for running Operion.", wordCount: 60 },
      { title: "Quick Start Guide", slug: "quick-start", excerpt: "A step-by-step guide to getting started with Operion in under 10 minutes.", wordCount: 150 },
      { title: "Navigating the Interface", slug: "interface-overview", excerpt: "Tour of the main dashboard, menus, and key screens.", wordCount: 120 },
    ],
  },
  "route-planning": {
    title: "Route Planning",
    description: "Learn how to create and optimize routes with Operion.",
    articles: [
      { title: "Creating Your First Route", slug: "first-route", excerpt: "Build a route from scratch using the route planner.", wordCount: 230 },
      { title: "Multi-Stop Optimization", slug: "multi-stop", excerpt: "Optimize routes with multiple stops for maximum efficiency.", wordCount: 180 },
      { title: "Importing Route Data", slug: "import-routes", excerpt: "Import routes from spreadsheets and external systems.", wordCount: 140 },
      { title: "Route Templates", slug: "route-templates", excerpt: "Save and reuse common route configurations.", wordCount: 110 },
    ],
  },
}

const defaultCategory: Record<string, CategoryData> = {
  "fleet-tracking": { title: "Fleet Tracking", description: "Real-time GPS tracking and fleet monitoring.", articles: [{ title: "Setting Up GPS Tracking", slug: "gps-setup", excerpt: "Configure GPS tracking for your fleet vehicles.", wordCount: 160 }] },
  "dispatch": { title: "Dispatch", description: "Job assignment and dispatch workflows.", articles: [{ title: "Creating Dispatch Jobs", slug: "creating-jobs", excerpt: "Create and assign dispatch jobs to drivers.", wordCount: 130 }] },
  "ocr": { title: "OCR & Documents", description: "Document scanning, OCR, and digital archiving.", articles: [{ title: "Scanning Documents", slug: "scanning", excerpt: "Use OCR to digitize invoices and CMR documents.", wordCount: 145 }] },
  "analytics": { title: "Analytics", description: "Reports, dashboards, and KPI tracking.", articles: [{ title: "Understanding Dashboards", slug: "dashboards", excerpt: "Navigate and customize your analytics dashboards.", wordCount: 175 }] },
  "administration": { title: "Administration", description: "User management, permissions, and settings.", articles: [{ title: "Managing Users", slug: "users", excerpt: "Add, remove, and manage user accounts.", wordCount: 120 }] },
  "api": { title: "API Reference", description: "Integrate Operion with your existing systems.", articles: [{ title: "Authentication", slug: "auth", excerpt: "Authenticate with the Operion API.", wordCount: 90 }] },
}

const allCategories: Record<string, CategoryData> = { ...categoriesData, ...defaultCategory }

// ─── Helpers ────────────────────────────────────────────────────────

function totalReadingTime(articles: ArticleEntry[]): number {
  const wpm = docsConfig.readingSpeedWPM
  const totalWords = articles.reduce((sum, a) => sum + (a.wordCount ?? 100), 0)
  return Math.ceil(totalWords / wpm)
}

// ─── Component ──────────────────────────────────────────────────────

export default function DocsCategoryPage() {
  const { t } = useLocale()
  const { category } = useParams<{ category?: string }>()
  const [searchQuery, setSearchQuery] = useState("")

  // Filter categories based on search
  const filteredCategories = useMemo(() => {
    if (!category && searchQuery) {
      const q = searchQuery.toLowerCase()
      return Object.fromEntries(
        Object.entries(allCategories).filter(([, cat]) => {
          const matchesCategory = cat.title.toLowerCase().includes(q) || cat.description.toLowerCase().includes(q)
          const matchesArticle = cat.articles.some((a) => a.title.toLowerCase().includes(q) || a.excerpt.toLowerCase().includes(q))
          return matchesCategory || matchesArticle
        })
      )
    }
    return allCategories
  }, [category, searchQuery])

  // Filter articles within a category
  const filteredArticles = useMemo(() => {
    if (category && searchQuery) {
      const q = searchQuery.toLowerCase()
      const cat = allCategories[category]
      if (!cat) return []
      return cat.articles.filter(
        (a) => a.title.toLowerCase().includes(q) || a.excerpt.toLowerCase().includes(q)
      )
    }
    return null // null means show all
  }, [category, searchQuery])

  // ── Docs Home (no category) ──

  if (!category) {
    return (
      <>
        <Helmet><title>{t("docs.pageTitle")}</title></Helmet>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl font-bold tracking-tight">{t("docs.title")}</h1>
          <p className="mt-2 text-muted-foreground">{t("docs.categoryDesc")}</p>

          {/* Search */}
          <div className="mt-6 max-w-md">
            <SearchInput
              placeholder={t("common.searchCategories")}
              value={searchQuery}
              onChange={setSearchQuery}
              onClear={() => setSearchQuery("")}
            />
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mt-8 grid gap-4 sm:grid-cols-2"
        >
          {Object.entries(filteredCategories).length > 0 ? (
            Object.entries(filteredCategories).map(([key, cat]) => (
              <Link key={key} to={`/docs/${key}`}>
                <Card className="h-full transition-all hover:shadow-md hover:border-primary/20">
                  <CardContent className="p-5">
                    <h3 className="font-semibold">{cat.title}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{cat.description}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Badge variant="secondary" className="text-xs">{t("docs.articleCount").replace("{count}", String(cat.articles.length))}</Badge>
                      <span className="flex items-center gap-1 text-xs text-foreground/80">
                        <Clock className="h-3 w-3" />
                        {t("docs.minTotal").replace("{minutes}", String(totalReadingTime(cat.articles)))}
                      </span>
                      <ChevronRight className="h-4 w-4 text-muted-foreground ml-auto" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))
          ) : (
            <div className="col-span-full text-center py-12">
              <BookOpen className="mx-auto h-10 w-10 text-muted-foreground/30" />
              <p className="mt-3 text-sm text-muted-foreground">{t("docs.noCategoriesMatch")}</p>
            </div>
          )}
        </motion.div>
      </>
    )
  }

  // ── Single Category View ──

  const cat = allCategories[category]
  const displayArticles = filteredArticles ?? cat?.articles ?? []

  if (!cat) {
    return (
      <>
        <Helmet><title>{t("docs.notFoundPageTitle")}</title></Helmet>
        <div className="text-center py-16">
          <BookOpen className="mx-auto h-12 w-12 text-muted-foreground/40" />
          <h1 className="mt-4 text-2xl font-bold">{t("docs.categoryNotFound")}</h1>
          <p className="mt-2 text-muted-foreground">{t("docs.categoryNotFoundDesc")}</p>
          <Link to="/docs" className="mt-4 inline-block text-sm text-primary hover:underline">{t("docs.browseAll")}</Link>
        </div>
      </>
    )
  }

  return (
    <>
      <Helmet><title>{`${cat.title} — Documentation — Operion ERP`}</title></Helmet>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <Link to="/docs" className="text-sm text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1 transition-colors">
          {t("docs.backToDocumentation")}
        </Link>
        <h1 className="text-3xl font-bold tracking-tight">{cat.title}</h1>
        <p className="mt-2 text-muted-foreground">{cat.description}</p>

        {/* Category meta */}
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <Badge variant="secondary" className="text-xs">{t("docs.articleCount").replace("{count}", String(cat.articles.length))}</Badge>
          <span className="flex items-center gap-1 text-xs text-foreground/80">
            <Clock className="h-3 w-3" />
            {t("docs.minTotal").replace("{minutes}", String(totalReadingTime(cat.articles)))}
          </span>
        </div>

        {/* Search within category */}
        <div className="mt-6 max-w-md">
          <SearchInput
            placeholder={t("docs.searchIn").replace("{title}", cat.title)}
            value={searchQuery}
            onChange={setSearchQuery}
            onClear={() => setSearchQuery("")}
          />
        </div>
      </motion.div>

      <div className="mt-6 space-y-3">
        {displayArticles.length > 0 ? (
          displayArticles.map((article, i) => (
            <motion.div key={article.slug} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Link to={`/docs/${category}/${article.slug}`}>
                <Card className="transition-all hover:shadow-md hover:border-primary/20">
                  <CardContent className="flex items-start justify-between p-5 gap-4">
                    <div className="min-w-0">
                      <h3 className="font-medium">{article.title}</h3>
                      <p className="mt-1 text-sm text-muted-foreground">{article.excerpt}</p>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 mt-1" />
                  </CardContent>
                </Card>
              </Link>
            </motion.div>
          ))
        ) : (
          <div className="text-center py-12">
            <BookOpen className="mx-auto h-10 w-10 text-muted-foreground/30" />
            <p className="mt-3 text-sm text-muted-foreground">{t("docs.noArticlesMatch")}</p>
          </div>
        )}
      </div>
    </>
  )
}
