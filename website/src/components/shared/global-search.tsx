"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { useAppNavigate } from "@/hooks/useAppNavigate"
import { motion, AnimatePresence } from "motion/react"
import {
  Search,
  Command,
  FileText,
  BookOpen,
  GraduationCap,
  HelpCircle,
  History,
  Compass,
  Download,
  Loader2,
  ChevronRight,
  LayoutDashboard,
  DollarSign,
  Headphones,
  Code,
  Building2,
  Route,
  Shirt,
  Clock,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useLocale } from "@/i18n/locale-context"
// TODO: Implement when backend endpoint is ready
// import { useGlobalSearch } from "@/services/queries"
import type { SearchResponse } from "@/api/endpoints"

type SearchResultItem = SearchResponse["results"][number]

// ─── Quick actions ────────────────────────────────────────────

interface QuickAction {
  id: string
  label: string
  href: string
  icon: React.ElementType
  category: "action"
}

// ─── Content type registry ────────────────────────────────────

const TYPE_ICONS: Record<string, React.ElementType> = {
  doc: BookOpen,
  blog: FileText,
  tutorial: GraduationCap,
  faq: HelpCircle,
  changelog: History,
  roadmap: Compass,
  download: Download,
  products: Building2,
  integrations: Code,
  industries: Shirt,
  pricing: DollarSign,
  support: Headphones,
  api: Code,
}

const TYPE_ORDER = [
  "doc",
  "blog",
  "tutorial",
  "products",
  "integrations",
  "industries",
  "pricing",
  "faq",
  "support",
  "api",
  "changelog",
  "roadmap",
  "download",
] as const

// ─── Search history in localStorage ──────────────────────────

const SEARCH_HISTORY_KEY = "operion-search-history"
const MAX_HISTORY = 5

function getSearchHistory(): string[] {
  try {
    const raw = localStorage.getItem(SEARCH_HISTORY_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function addToSearchHistory(query: string) {
  if (!query.trim()) return
  try {
    const history = getSearchHistory().filter((h) => h !== query)
    history.unshift(query)
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)))
  } catch {
    // localStorage may be unavailable
  }
}

// ─── Debounce hook ────────────────────────────────────────────

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debouncedValue
}

// ─── Component ────────────────────────────────────────────────

interface GlobalSearchProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

export function GlobalSearch({ open: controlledOpen, onOpenChange }: GlobalSearchProps) {
  const { t } = useLocale()

  const QUICK_ACTIONS: QuickAction[] = [
    { id: "qa-dashboard", label: t("search.quickActionDashboard"), href: "/dashboard", icon: LayoutDashboard, category: "action" },
    { id: "qa-download", label: t("search.quickActionDownload"), href: "/download", icon: Download, category: "action" },
    { id: "qa-pricing", label: t("search.quickActionPricing"), href: "/pricing", icon: DollarSign, category: "action" },
    { id: "qa-support", label: t("search.quickActionSupport"), href: "/support", icon: Headphones, category: "action" },
    { id: "qa-demo", label: t("search.quickActionDemo"), href: "/route-demo", icon: Route, category: "action" },
  ]

  const TYPE_LABELS: Record<string, string> = {
    doc: t("search.typeDocs"),
    blog: t("search.typeBlog"),
    tutorial: t("search.typeTutorials"),
    faq: t("search.typeFaq"),
    changelog: t("search.typeChangelog"),
    roadmap: t("search.typeRoadmap"),
    download: t("search.typeDownloads"),
    products: t("search.typeProducts"),
    integrations: t("search.typeIntegrations"),
    industries: t("search.typeIndustries"),
    pricing: t("search.typePricing"),
    support: t("search.typeSupport"),
    api: t("search.typeApi"),
  }

  const navigate = useAppNavigate()
  const [internalOpen, setInternalOpen] = useState(false)
  const open = controlledOpen ?? internalOpen
  const setOpen = (val: boolean | ((prev: boolean) => boolean)) => {
    const next = typeof val === "function" ? val(open) : val
    if (onOpenChange) onOpenChange(next)
    else setInternalOpen(next)
  }

  const [query, setQuery] = useState("")
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [searchHistory, setSearchHistory] = useState<string[]>(getSearchHistory)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const debouncedQuery = useDebouncedValue(query, 300)
  // TODO: Implement when backend endpoint is ready
  // const { data: searchData, isLoading } = useGlobalSearch(debouncedQuery)
  const searchData: SearchResponse | undefined = undefined as SearchResponse | undefined
  const isLoading = false

  const results: SearchResultItem[] = (searchData?.results ?? []) as SearchResultItem[]

  // Group API results by type
  const groupedResults = results.reduce<Record<string, SearchResultItem[]>>((acc: Record<string, SearchResultItem[]>, result: SearchResultItem) => {
    const group = result.type || "other"
    if (!acc[group]) acc[group] = []
    acc[group].push(result)
    return acc
  }, {})

  // Build flat list: quick actions (when query is empty) + grouped results
  const showQuickActions = !debouncedQuery
  const flatResults = showQuickActions
    ? QUICK_ACTIONS
    : TYPE_ORDER.flatMap((type) => groupedResults[type] || [])

  // Keyboard shortcut listener
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
      if (e.key === "Escape") {
        setOpen(false)
      }
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [])

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery("")
      setSelectedIndex(0)
      setSearchHistory(getSearchHistory())
      const timer = setTimeout(() => inputRef.current?.focus(), 50)
      return () => clearTimeout(timer)
    }
  }, [open])

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => {
      document.body.style.overflow = ""
    }
  }, [open])

  const navigateTo = useCallback(
    (url: string) => {
      setOpen(false)
      // Security: validate URL to prevent open redirect
      if (
        url.startsWith("http") &&
        !url.includes("operionerp.xyz") &&
        !url.startsWith("http://localhost")
      ) {
        return
      }
      navigate(url)
    },
    [navigate]
  )

  const handleSelect = useCallback(
    (item: { href?: string; url?: string }) => {
      const target = item.href || item.url
      if (!target) return
      if (query.trim()) addToSearchHistory(query.trim())
      navigateTo(target)
    },
    [query, navigateTo]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault()
        setSelectedIndex((prev) => (prev < flatResults.length - 1 ? prev + 1 : 0))
      } else if (e.key === "ArrowUp") {
        e.preventDefault()
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : flatResults.length - 1))
      } else if (e.key === "Enter" && flatResults[selectedIndex]) {
        e.preventDefault()
        handleSelect(flatResults[selectedIndex] as QuickAction & SearchResultItem)
      }
    },
    [flatResults, selectedIndex, handleSelect]
  )

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current || flatResults.length === 0) return
    const selected = listRef.current.querySelector(
      `[data-index="${selectedIndex}"]`
    ) as HTMLElement | null
    selected?.scrollIntoView({ block: "nearest" })
  }, [selectedIndex, flatResults.length])

  // Suggestions for no-results state
  const suggestions = [
    { label: "Getting started guide", href: "/docs/getting-started" },
    { label: "Pricing plans", href: "/pricing" },
    { label: "Route planning", href: "/docs/route-planning" },
    { label: "Download Operion", href: "/download" },
    { label: "Contact support", href: "/support" },
  ]

  // Compute visible group indices for ARIA
  let currentFlatIndex = 0

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop — smoother */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-md"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -16 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] sm:pt-[18vh]"
            role="dialog"
            aria-modal="true"
            aria-label={t("common.search")}
          >
            <div
              className="w-full max-w-xl rounded-xl border border-border/50 bg-background shadow-2xl shadow-black/20 dark:border-border/30 dark:bg-zinc-900/95 dark:backdrop-blur-2xl"
              onKeyDown={handleKeyDown}
            >
              {/* Search Input */}
              <div className="flex items-center gap-3 border-b border-border/50 px-4 dark:border-border/30">
                {isLoading && query.length >= 2 ? (
                  <Loader2 className="h-5 w-5 shrink-0 animate-spin text-muted-foreground" />
                ) : (
                  <Search className="h-5 w-5 shrink-0 text-muted-foreground" />
                )}
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value)
                    setSelectedIndex(0)
                  }}
                  placeholder={t("search.placeholder")}
                  className="flex h-14 w-full bg-transparent text-base outline-none placeholder:text-muted-foreground/60"
                  autoComplete="off"
                  spellCheck={false}
                />
                <kbd className="hidden shrink-0 items-center gap-1 rounded-md border border-border/50 bg-muted/50 px-1.5 py-0.5 text-[11px] text-muted-foreground sm:inline-flex">
                  <Command className="h-3 w-3" />
                  <span>K</span>
                </kbd>
              </div>

              {/* Results area */}
              <div className="max-h-[min(60vh,420px)] overflow-y-auto p-2" ref={listRef}>
                {/* Loading */}
                {isLoading && query.length >= 2 && (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                )}

                {/* No results — with suggestions */}
                {!isLoading && debouncedQuery && flatResults.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-10 text-center">
                    <Search className="mb-3 h-10 w-10 text-muted-foreground/40" />
                    <p className="text-sm font-medium">{t("common.noResults")}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {t("search.tryDifferent")}
                    </p>
                    <div className="mt-5 space-y-1.5">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
                        {t("search.tryThese")}
                      </p>
                      <div className="flex flex-wrap justify-center gap-2">
                        {suggestions.map((s) => (
                          <button
                            key={s.href}
                            onClick={() => handleSelect({ href: s.href })}
                            className="rounded-md border border-border/50 bg-muted/30 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                          >
                            {s.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Empty initial state */}
                {!isLoading && !debouncedQuery && flatResults.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-10 text-center">
                    <Search className="mb-3 h-10 w-10 text-muted-foreground/20" />
                    <p className="text-sm text-muted-foreground">
                      {t("search.typeToSearch")}
                    </p>
                  </div>
                )}

                {/* Search history */}
                {!isLoading && !debouncedQuery && searchHistory.length > 0 && (
                  <div className="mb-2">
                    <div className="flex items-center gap-2 px-3 py-2">
                      <Clock className="h-4 w-4 text-muted-foreground" />
                      <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        {t("search.recentSearches")}
                      </span>
                    </div>
                    {searchHistory.map((term, i) => {
                      const flatIdx = i
                      const isSelected = selectedIndex === flatIdx
                      return (
                        <button
                          key={term}
                          data-index={flatIdx}
                          onClick={() => {
                            setQuery(term)
                          }}
                          onMouseEnter={() => setSelectedIndex(flatIdx)}
                          className={cn(
                            "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors",
                            isSelected ? "bg-accent text-accent-foreground" : "hover:bg-muted/50"
                          )}
                        >
                          <Clock className="h-4 w-4 shrink-0 text-muted-foreground/50" />
                          <span className="text-sm">{term}</span>
                        </button>
                      )
                    })}
                  </div>
                )}

                {/* Quick actions — shown when no query */}
                {!isLoading && !debouncedQuery && QUICK_ACTIONS.length > 0 && (
                  <div className="mb-2">
                    <div className="flex items-center gap-2 px-3 py-2">
                      <Command className="h-4 w-4 text-muted-foreground" />
                      <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        {t("search.quickActions")}
                      </span>
                    </div>
                    {QUICK_ACTIONS.map((action, i) => {
                      const historyOffset = searchHistory.length
                      const flatIdx = historyOffset + i
                      const isSelected = selectedIndex === flatIdx
                      const Icon = action.icon
                      return (
                        <button
                          key={action.id}
                          data-index={flatIdx}
                          onClick={() => handleSelect(action)}
                          onMouseEnter={() => setSelectedIndex(flatIdx)}
                          className={cn(
                            "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors",
                            isSelected ? "bg-accent text-accent-foreground" : "hover:bg-muted/50"
                          )}
                        >
                          <Icon className="h-4 w-4 shrink-0 text-muted-foreground/50" />
                          <span className="text-sm font-medium">{action.label}</span>
                          <ChevronRight
                            className={cn(
                              "ml-auto h-4 w-4 shrink-0 text-muted-foreground/40 transition-opacity",
                              isSelected ? "opacity-100" : "opacity-0"
                            )}
                          />
                        </button>
                      )
                    })}
                  </div>
                )}

                {/* Search results grouped by type */}
                {!isLoading &&
                  debouncedQuery &&
                  TYPE_ORDER.map((type) => {
                    const group = groupedResults[type]
                    if (!group || group.length === 0) return null
                    const Icon = TYPE_ICONS[type] || FileText
                    const label = TYPE_LABELS[type] || type

                    const startIndex = currentFlatIndex
                    currentFlatIndex += group.length

                    return (
                      <div key={type} className="mb-2">
                        <div className="flex items-center gap-2 px-3 py-2">
                          <Icon className="h-4 w-4 text-muted-foreground" />
                          <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                            {label}
                          </span>
                          <span className="ml-auto text-xs text-muted-foreground/50">
                            {group.length}
                          </span>
                        </div>
                        {group.map((result: SearchResultItem, groupIndex: number) => {
                          const flatIdx = startIndex + groupIndex
                          const isSelected = selectedIndex === flatIdx
                          return (
                            <button
                              key={result.id}
                              data-index={flatIdx}
                              onClick={() => handleSelect(result)}
                              onMouseEnter={() => setSelectedIndex(flatIdx)}
                              className={cn(
                                "flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors",
                                isSelected
                                  ? "bg-accent text-accent-foreground"
                                  : "hover:bg-muted/50"
                              )}
                            >
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm font-medium truncate">
                                    {result.title}
                                  </span>
                                  <span
                                    className={cn(
                                      "inline-flex shrink-0 items-center rounded-md px-1.5 py-0.5 text-[10px] font-medium uppercase leading-none",
                                      "bg-muted text-muted-foreground"
                                    )}
                                  >
                                    {label}
                                  </span>
                                </div>
                                {result.description && (
                                  <p className="mt-0.5 text-xs text-muted-foreground/70 line-clamp-1">
                                    {result.description}
                                  </p>
                                )}
                              </div>
                              <ChevronRight
                                className={cn(
                                  "mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/40 transition-opacity",
                                  isSelected ? "opacity-100" : "opacity-0"
                                )}
                              />
                            </button>
                          )
                        })}
                      </div>
                    )
                  })}
              </div>

              {/* Footer hint — more prominent */}
              <div className="border-t border-border/50 px-4 py-2.5 dark:border-border/30">
                <div className="flex items-center justify-between gap-4 text-xs text-muted-foreground/60">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1">
                      <kbd className="rounded border border-border/50 bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium">↑</kbd>
                      <kbd className="rounded border border-border/50 bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium">↓</kbd>
                      <span className="hidden sm:inline">{t("search.navigate")}</span>
                    </span>
                    <span className="flex items-center gap-1">
                      <kbd className="rounded border border-border/50 bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium">↵</kbd>
                      <span className="hidden sm:inline">{t("search.select")}</span>
                    </span>
                    <span className="flex items-center gap-1">
                      <kbd className="rounded border border-border/50 bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium">esc</kbd>
                      <span className="hidden sm:inline">{t("search.close")}</span>
                    </span>
                  </div>
                  <span className="text-[10px] text-muted-foreground/40">
                    <kbd className="rounded border border-border/50 bg-muted/50 px-1 py-0.5 text-[10px] font-medium">⌘K</kbd>
                      <span className="ml-1 hidden sm:inline">{t("search.toggle")}</span>
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
