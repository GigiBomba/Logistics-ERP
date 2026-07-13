import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useParams, useSearchParams, Link } from "react-router"
import { ArrowLeft, FileText } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { BlogCard } from "@/components/shared/blog-card"
import { Pagination } from "@/components/ui/pagination"
import { SearchInput } from "@/components/shared/search-input"
import { Skeleton } from "@/components/ui/skeleton"
import { blogConfig } from "@/config/site"
import { useBlogPosts } from "@/services/queries"

const MOCK_POSTS = [
  {
    title: "Trip Profitability: How to Calculate Profit Per Transport Job",
    slug: "how-to-calculate-trip-profitability-road-transport",
    excerpt:
      "Learn how to calculate trip profitability in road transport. This practical guide covers cost components, revenue tracking, and margin analysis for freight operators.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Profitability & Transport Finance",
    tags: ["trip-profitability", "cost-calculation", "transport-finance", "margin-analysis", "efti", "graphhopper"],
    featured_image: "",
    reading_time_minutes: 8,
    published_at: "2026-07-12T10:00:00Z",
  },
  {
    title: "Cost Per Kilometer Guide: Fixed vs Variable Fleet Costs Explained",
    slug: "understanding-cost-per-kilometer-transport-manager-guide",
    excerpt:
      "Master cost per kilometer calculation for your transport fleet. Understand fixed vs variable fleet costs and how this CPK metric drives transport profitability.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Profitability & Transport Finance",
    tags: ["cost-per-kilometer", "fleet-costs", "fixed-costs", "variable-costs", "maintenance-costs"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-07-10T10:00:00Z",
  },
  {
    title: "Fuel Cost Management: Strategies for Small Transport Fleets",
    slug: "fuel-cost-management-strategies-small-fleets",
    excerpt:
      "Practical fuel cost management strategies for small transport fleets. Reduce fuel consumption and manage expenses without costly technology investments.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Profitability & Transport Finance",
    tags: ["fuel-costs", "fleet-efficiency", "cost-saving", "small-fleet", "driver-training", "route-optimization"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-07-08T10:00:00Z",
  },
  {
    title: "Exchange Rates in Logistics: Managing Currency Risk in International Freight",
    slug: "role-of-exchange-rates-international-logistics-profitability",
    excerpt:
      "Learn how exchange rates in logistics affect cross-border transport margins. Discover currency risk management strategies for international freight operations.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Profitability & Transport Finance",
    tags: ["exchange-rates", "international-logistics", "currency-risk", "cross-border", "forex-risk", "eu-mobility-package"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-07-05T10:00:00Z",
  },
  {
    title: "Profitable vs Unprofitable Routes: How to Evaluate Transport Jobs",
    slug: "what-makes-transport-route-profitable-vs-unprofitable",
    excerpt:
      "Learn to identify profitable vs unprofitable routes in road transport. Key factors include load balancing, backhaul planning, and empty mile reduction.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Profitability & Transport Finance",
    tags: ["route-profitability", "backhauls", "empty-miles", "load-balancing", "cmr", "toll-costs"],
    featured_image: "",
    reading_time_minutes: 8,
    published_at: "2026-07-01T10:00:00Z",
  },
  {
    title: "Logistics KPIs: Key Financial Metrics for Transport Companies",
    slug: "financial-kpis-every-logistics-business-should-track",
    excerpt:
      "Track the right logistics KPIs for your transport company. From operating ratio to profit per kilometer, master financial metrics that drive profitability.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Profitability & Transport Finance",
    tags: ["financial-kpis", "operating-ratio", "profit-per-km", "utilization-rate", "cash-flow", "benchmarking"],
    featured_image: "",
    reading_time_minutes: 9,
    published_at: "2026-06-28T10:00:00Z",
  },
  {
    title: "Hidden Transport Costs: Tolls, Waiting Time & Operational Expenses",
    slug: "hidden-costs-transport-operations-you-might-be-missing",
    excerpt:
      "Uncover hidden transport costs that erode your margins. From tolls and waiting time to detention charges and insurance gaps — identify every operational expense.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Profitability & Transport Finance",
    tags: ["hidden-costs", "tolls", "detention", "insurance", "operating-costs", "administration-fees", "waiting-time"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-06-25T10:00:00Z",
  },
  {
    title: "Transport Pricing Strategy: How to Set Competitive & Profitable Rates",
    slug: "how-to-price-transport-services-competitively-and-profitably",
    excerpt:
      "Master transport pricing strategy with our guide to setting competitive and profitable rates. Learn cost-plus pricing, market analysis, and margin optimization.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Profitability & Transport Finance",
    tags: ["pricing-strategy", "cost-plus-pricing", "market-rates", "transport-services", "rate-negotiation", "market-analysis"],
    featured_image: "",
    reading_time_minutes: 8,
    published_at: "2026-06-22T10:00:00Z",
  },
  {
    title: "Seasonal Demand in Logistics: Managing Transport Margins Year-Round",
    slug: "seasonal-demand-impact-transport-margins",
    excerpt:
      "Understand how seasonal demand in logistics affects freight rates and transport margins. Plan capacity for peak and off-peak seasons to protect profitability.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Profitability & Transport Finance",
    tags: ["seasonal-demand", "peak-season", "capacity-planning", "margin-management", "capacity-management", "freight-rates"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-06-19T10:00:00Z",
  },
  {
    title: "Transport Management Software: Digital Tools for Fleet Finances in 2026",
    slug: "digital-tools-transport-financial-management-2026",
    excerpt:
      "Compare transport management software for fleet finances in 2026. From spreadsheets to logistics ERP, find the right digital tools for your operation.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Profitability & Transport Finance",
    tags: ["digital-tools", "financial-management", "logistics-software", "erp", "erp-software", "digital-transformation"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-06-16T10:00:00Z",
  },
  {
    title: "Preventive Maintenance Scheduling for Small Truck Fleets",
    slug: "preventive-maintenance-scheduling-small-truck-fleets",
    excerpt:
      "How to build a maintenance schedule that minimizes downtime and reduces long-term repair costs for fleets with limited staff.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["preventive-maintenance", "fleet-maintenance", "downtime", "repair-costs"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-06-13T10:00:00Z",
  },
  {
    title: "Tire Management and Its Impact on Operating Costs",
    slug: "tire-management-impact-operating-costs",
    excerpt:
      "Why tire selection, pressure monitoring, and rotation schedules matter more than most fleet managers realize for the bottom line.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["tire-management", "operating-costs", "fleet-efficiency", "maintenance"],
    featured_image: "",
    reading_time_minutes: 5,
    published_at: "2026-06-10T10:00:00Z",
  },
  {
    title: "The Modern Transport Dispatcher's Workflow: A Day in the Life",
    slug: "modern-transport-dispatcher-workflow",
    excerpt:
      "From pre-trip planning to end-of-day reconciliation, follow a realistic dispatch operation from the dispatcher's seat—covering load assignments, route monitoring, issue resolution, and communication loops.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["dispatch", "workflow", "operations", "scheduling"],
    featured_image: "",
    reading_time_minutes: 8,
    published_at: "2026-07-11T10:00:00Z",
  },
  {
    title: "Load Planning Strategies for Maximum Vehicle Utilization",
    slug: "load-planning-strategies-vehicle-utilization",
    excerpt:
      "Every empty kilometre is lost revenue. Learn practical load consolidation, backhauling, and weight-volume balancing techniques that improve fleet profitability without adding trucks.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["load-planning", "vehicle-utilization", "dispatch", "freight"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-07-08T10:00:00Z",
  },
  {
    title: "Route Optimization Basics: More Than Just the Shortest Path",
    slug: "route-optimization-basics",
    excerpt:
      "Real-world route planning means balancing driver hours, toll costs, vehicle restrictions, loading dock availability, and customer time windows—the shortest line on a map is rarely the best route.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["route-optimization", "dispatch", "planning", "constraints"],
    featured_image: "",
    reading_time_minutes: 9,
    published_at: "2026-07-04T10:00:00Z",
  },
  {
    title: "Handling Last-Minute Changes: The Dispatcher's Survival Guide",
    slug: "handling-last-minute-changes-dispatcher-guide",
    excerpt:
      "Breakdowns, cancellations, delays, and border closures are inevitable. Build a structured response framework that turns chaos into controlled execution.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["dispatch", "crisis-management", "flexibility", "communication"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-06-30T10:00:00Z",
  },
  {
    title: "Communication Between Dispatchers and Drivers: Best Practices",
    slug: "dispatcher-driver-communication-best-practices",
    excerpt:
      "Miscommunication between the office and the cab is a top source of operational friction. Establish clear protocols, choose the right channels, and build a culture of feedback.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["communication", "dispatch", "drivers", "protocols"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-06-26T10:00:00Z",
  },
  {
    title: "Cross-Border Dispatching: Documentation and Compliance Checklist",
    slug: "cross-border-dispatching-documentation-compliance",
    excerpt:
      "International freight requires CMR waybills, customs declarations, transport permits, and TIR carnets. A practical checklist for dispatchers managing cross-border operations.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["cross-border", "dispatch", "compliance", "cmr", "customs"],
    featured_image: "",
    reading_time_minutes: 10,
    published_at: "2026-06-22T10:00:00Z",
  },
  {
    title: "Digital Tools That Help Small Dispatch Operations Scale",
    slug: "digital-tools-small-dispatch-scale",
    excerpt:
      "Spreadsheets work at five trucks but break at twenty. An honest look at how small fleets can use software—including Operion—to automate scheduling, tracking, and documentation.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["software", "dispatch", "scaling", "tools", "operion"],
    featured_image: "",
    reading_time_minutes: 8,
    published_at: "2026-06-18T10:00:00Z",
  },
  {
    title: "Key Performance Indicators for Dispatch Operations",
    slug: "dispatch-kpi-key-performance-indicators",
    excerpt:
      "Stop tracking everything and start tracking what matters: on-time delivery rate, empty miles ratio, load acceptance rate, and cost per dispatched mile.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["kpi", "dispatch", "analytics", "performance"],
    featured_image: "",
    reading_time_minutes: 5,
    published_at: "2026-06-14T10:00:00Z",
  },
]

const CATEGORY_NAMES: Record<string, string> = {
  "profitability-transport-finance": "Profitability & Transport Finance",
  "fleet-management": "Fleet Management",
  dispatching: "Dispatching",
}

export default function BlogCategoryPage() {
  const { category: categorySlug } = useParams<{ category: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10))
  const search = searchParams.get("search") || ""

  const { isLoading: postsLoading } = useBlogPosts({ page, category: categorySlug, search })

  const allPosts = MOCK_POSTS
  const categoryName = categorySlug ? CATEGORY_NAMES[categorySlug] || categorySlug : ""

  const filteredPosts = useMemo(() => {
    let result = allPosts.filter(
      (p) => p.category.toLowerCase().replace(/\s+/g, "-") === categorySlug
    )
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(
        (p) =>
          p.title.toLowerCase().includes(q) ||
          p.excerpt.toLowerCase().includes(q) ||
          p.tags.some((t) => t.toLowerCase().includes(q))
      )
    }
    return result
  }, [allPosts, categorySlug, search])

  const totalPages = Math.max(1, Math.ceil(filteredPosts.length / blogConfig.postsPerPage))
  const safePage = Math.min(page, totalPages)
  const paginatedPosts = filteredPosts.slice(
    (safePage - 1) * blogConfig.postsPerPage,
    safePage * blogConfig.postsPerPage
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
        <title>{categoryName} — Blog — Operion</title>
        <meta
          name="description"
          content={`Articles in the ${categoryName} category on the Operion blog.`}
        />
      </Helmet>

      <PageHeader
        title={categoryName || "Category"}
        description={`All articles in the ${categoryName || "selected"} category.`}
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
              placeholder="Search articles..."
              value={search}
              onChange={handleSearchChange}
              className="w-full sm:max-w-sm"
            />
            <div className="text-sm text-muted-foreground">
              {filteredPosts.length} article{filteredPosts.length !== 1 ? "s" : ""}
            </div>
          </div>

          <Link
            to="/blog"
            className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            All categories
          </Link>
        </motion.div>

        {postsLoading ? (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex flex-col gap-3">
                <Skeleton className="aspect-video w-full rounded-lg" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-5 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            ))}
          </div>
        ) : paginatedPosts.length > 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
          >
            {paginatedPosts.map((post, i) => (
              <motion.div
                key={post.slug}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
              >
                <BlogCard post={post} />
              </motion.div>
            ))}
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="flex flex-col items-center justify-center py-20 text-center"
          >
            <FileText className="mb-4 h-12 w-12 text-muted-foreground/50" />
            <h3 className="text-lg font-semibold">No articles found</h3>
            <p className="mt-2 text-muted-foreground">
              Try adjusting your search or browse a different category.
            </p>
            <Link
              to="/blog"
              className="mt-4 text-sm font-medium text-primary hover:underline"
            >
              Back to all articles
            </Link>
          </motion.div>
        )}

        {paginatedPosts.length > 0 && totalPages > 1 && (
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
