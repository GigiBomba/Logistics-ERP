import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { Link } from "react-router"
import { PenLine, Tag } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { BlogCard } from "@/components/shared/blog-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/contexts/auth-provider"

interface BlogPost {
  title: string
  slug: string
  excerpt: string
  seo_description?: string
  author_name: string
  author_avatar: string
  category: string
  tags: string[]
  featured_image: string
  reading_time_minutes: number
  published_at: string
}

const BLOG_POSTS: BlogPost[] = [
  {
    title: "Trip Profitability: How to Calculate Profit Per Transport Job",
    slug: "how-to-calculate-trip-profitability-road-transport",
    excerpt:
      "Learn how to calculate trip profitability in road transport. This practical guide covers cost components, revenue tracking, and margin analysis for freight operators.",
    seo_description:
      "Learn how to calculate trip profitability in road transport with our complete guide. Master cost tracking, revenue analysis, and margin calculation for freight operations.",
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
    seo_description:
      "Understand cost per kilometer in transport management. Our guide explains fixed vs variable fleet costs and how to calculate CPK for better fleet profitability.",
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
    seo_description:
      "Discover fuel cost management strategies for small transport fleets. Learn to reduce fuel consumption and manage expenses without costly technology investments.",
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
    seo_description:
      "Learn how exchange rates in logistics affect international freight margins. Discover currency risk management strategies for cross-border transport operations.",
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
    seo_description:
      "Learn how to evaluate profitable vs unprofitable routes in road transport. Discover key factors including load balancing, backhauls, and empty mile reduction strategies.",
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
    seo_description:
      "Discover the essential logistics KPIs every transport company should track. From operating ratio to profit per kilometer, master financial performance metrics.",
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
    seo_description:
      "Identify hidden transport costs eating into your margins. From tolls and waiting time to detention charges — uncover every operational expense in trucking.",
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
    seo_description:
      "Master transport pricing strategy to set competitive and profitable rates. Learn cost-plus pricing, market rate analysis, and margin optimization for your fleet.",
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
    seo_description:
      "Discover how seasonal demand in logistics impacts transport margins year-round. Learn capacity planning strategies for peak and off-peak freight seasons.",
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
    seo_description:
      "Compare transport management software options for fleet financial management in 2026. From spreadsheets to logistics ERP, find the right digital tools for your operation.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Profitability & Transport Finance",
    tags: ["digital-tools", "financial-management", "logistics-software", "erp", "erp-software", "digital-transformation"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-06-16T10:00:00Z",
  },
  {
    title: "Preventive Maintenance Schedule: Reduce Fleet Downtime & Repair Costs",
    slug: "preventive-maintenance-scheduling-small-truck-fleets",
    excerpt:
      "Build a preventive maintenance schedule to reduce fleet downtime, cut repair costs, and extend vehicle life. Practical service interval guide for small fleets.",
    seo_description:
      "Build a preventive maintenance schedule to reduce fleet downtime and cut repair costs for small to mid-size truck fleets. Practical service interval guide.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["preventive-maintenance", "fleet-maintenance", "downtime", "repair-costs", "vehicle-service", "IRU"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-06-13T10:00:00Z",
  },
  {
    title: "Tire Management Guide: Lower Fleet Operating Costs Through Better Tire Care",
    slug: "tire-management-impact-operating-costs",
    excerpt:
      "Discover how tire selection, pressure monitoring, and rotation schedules lower fleet operating costs and improve safety. Practical tire management guide for transport operators.",
    seo_description:
      "Discover how tire selection, pressure monitoring, and rotation schedules lower fleet operating costs. A practical tire management guide for transport companies.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["tire-management", "operating-costs", "fleet-efficiency", "maintenance", "retreading", "safety-compliance"],
    featured_image: "",
    reading_time_minutes: 5,
    published_at: "2026-06-10T10:00:00Z",
  },
  {
    title: "Driver Retention Strategies: How Transport Companies Keep Good Drivers",
    slug: "driver-retention-strategies-transport-companies",
    excerpt:
      "Proven driver retention strategies: competitive pay, quality of life improvements, recognition programs, and fair dispatch practices that reduce costly driver turnover.",
    seo_description:
      "Proven driver retention strategies for transport companies: competitive pay, quality of life improvements, and fair dispatch practices that reduce costly driver turnover.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["driver-retention", "turnover", "human-resources", "driver-satisfaction", "dispatch", "IRU"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-06-07T10:00:00Z",
  },
  {
    title: "Telematics for Small Fleets: GPS Tracking & Vehicle Data Basics",
    slug: "telematics-basics-small-fleets-need-to-know",
    excerpt:
      "Learn how telematics and GPS tracking help small fleets reduce operating costs and improve efficiency. Practical guide to vehicle data, provider selection, and implementation.",
    seo_description:
      "Learn how telematics and GPS tracking help small fleets reduce costs and improve efficiency. Guide to vehicle data, provider selection, and implementation tips.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["telematics", "gps-tracking", "small-fleet", "fleet-data", "fleet-technology", "compliance"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-06-04T10:00:00Z",
  },
  {
    title: "Fleet Right-Sizing: Match Vehicle Capacity to Transport Demand",
    slug: "fleet-right-sizing-matching-capacity-to-demand",
    excerpt:
      "Match fleet capacity to transport demand using utilization analysis, seasonal planning, and leasing strategies. A practical fleet right-sizing guide for managers.",
    seo_description:
      "Learn to match fleet capacity to transport demand using utilization analysis, seasonal planning, and leasing strategies. A practical fleet right-sizing guide.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["fleet-sizing", "capacity-planning", "fleet-optimization", "asset-management", "utilization", "TIMOCOM"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-06-01T10:00:00Z",
  },
  {
    title: "EU Road Transport Compliance: Regulations Every Fleet Manager Must Know",
    slug: "compliance-regulatory-considerations-eu-road-transport",
    excerpt:
      "Essential EU road transport compliance guide: driving hours, cabotage rules, tachograph requirements, and Mobility Package regulations every fleet manager must know.",
    seo_description:
      "Essential EU road transport compliance guide: driving hours, cabotage rules, tachographs, and Mobility Package regulations every fleet manager must know.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["compliance", "eu-regulations", "driving-hours", "cabotage", "transport-law", "EU-Mobility-Package", "ADR"],
    featured_image: "",
    reading_time_minutes: 8,
    published_at: "2026-05-29T10:00:00Z",
  },
  {
    title: "Vehicle Lifecycle Management: When to Repair vs Replace Fleet Assets",
    slug: "vehicle-lifecycle-management-repair-vs-replace",
    excerpt:
      "Learn when to repair vs replace fleet assets with a data-driven vehicle lifecycle management framework. Optimize total cost of ownership for your truck fleet.",
    seo_description:
      "Data-driven vehicle lifecycle management: learn when to repair vs replace fleet assets to optimize total cost of ownership and maximize fleet ROI.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["vehicle-lifecycle", "repair-vs-replace", "fleet-renewal", "total-cost-of-ownership", "fleet-planning", "IRU"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-05-26T10:00:00Z",
  },
  {
    title: "Dispatcher Communication: Best Practices for Driver Coordination",
    slug: "effective-communication-dispatchers-and-drivers",
    excerpt:
      "Master dispatcher communication best practices to improve driver coordination, reduce errors, and boost on-time performance. Essential reading for freight dispatch teams looking to strengthen operations.",
    seo_description:
      "Master dispatcher communication best practices for better driver coordination. Reduce errors, improve on-time performance, and strengthen freight dispatch operations with proven communication strategies.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["dispatcher-communication", "driver-communication", "dispatch-best-practices", "cmr", "ecmr"],
    featured_image: "",
    reading_time_minutes: 5,
    published_at: "2026-05-23T10:00:00Z",
  },
  {
    title: "Load Planning Guide: How New Dispatchers Build Efficient Routes",
    slug: "load-planning-fundamentals-new-dispatchers",
    excerpt:
      "A complete load planning guide for new dispatchers covering route optimization, capacity matching, backhaul strategies, and weight distribution to maximize freight efficiency and fleet profitability.",
    seo_description:
      "New to dispatch? This load planning guide covers route optimization, vehicle capacity matching, backhaul strategies, and weight distribution for efficient freight operations and higher profitability.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["load-planning", "dispatch-training", "weight-distribution", "delivery-sequence", "graphhopper", "route-optimization"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-05-20T10:00:00Z",
  },
  {
    title: "Detention Time Management: Reduce Waiting Costs in Freight Transport",
    slug: "managing-detention-time-and-waiting-charges",
    excerpt:
      "Reduce detention time costs with proven strategies for tracking waiting charges, documenting delays, and negotiating fair terms with shippers and receivers in freight transport operations.",
    seo_description:
      "Learn how to reduce freight detention time costs with proven waiting charge management strategies. Track delays, document waiting time, and negotiate fair terms with shippers and receivers.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["detention-time", "waiting-charges", "loading-dock", "dispatch-operations", "ecmr", "efti"],
    featured_image: "",
    reading_time_minutes: 5,
    published_at: "2026-05-17T10:00:00Z",
  },
  {
    title: "Dispatcher Profitability: How Dispatch Decisions Impact Transport Margins",
    slug: "role-of-the-dispatcher-in-trip-profitability",
    excerpt:
      "Discover how dispatch decisions directly impact transport margins. From load selection and empty mile reduction to fuel-efficient routing, dispatchers drive fleet profitability every day.",
    seo_description:
      "Understand how dispatcher decisions impact transport margins. Learn load selection, empty mile reduction, and fuel-efficient routing strategies that boost fleet financial performance.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["dispatcher-impact", "trip-profitability", "load-selection", "dispatch-efficiency", "graphhopper"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-05-14T10:00:00Z",
  },
  {
    title: "Carrier Relationships: Building Strong Freight Partnerships That Last",
    slug: "building-strong-carrier-relationships-freight-dispatching",
    excerpt:
      "Build and maintain strong carrier relationships in freight dispatching that lead to better rates, reliable service, and long-term partnerships. Essential strategies for dispatchers and brokers.",
    seo_description:
      "Learn how to build strong carrier relationships in freight dispatching for better rates and reliable service. Partnership strategies that create long-term value for dispatchers and brokers.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["carrier-relationships", "freight-dispatching", "partnerships", "broker-dispatcher", "timocom", "trans-eu"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-05-11T10:00:00Z",
  },
  {
    title: "Dispatch Software Features: What to Look For in Transport Management Tools",
    slug: "dispatch-software-evaluation-features-that-matter",
    excerpt:
      "Compare essential dispatch software features for transport management. Learn which TMS tools improve route planning, fleet tracking, documentation, and daily dispatch operations.",
    seo_description:
      "Compare essential dispatch software features for transport management. Learn how TMS tools improve route planning, fleet tracking, documentation, and daily dispatch operations efficiently.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["dispatch-software", "software-evaluation", "dispatch-tools", "logistics-tech", "graphhopper", "timocom", "efti"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-05-08T10:00:00Z",
  },
  {
    title: "Disruption Management: A Dispatcher's Contingency Planning Guide",
    slug: "handling-disruptions-dispatcher-guide-contingency-planning",
    excerpt:
      "Master freight disruption management with proven contingency planning strategies. Learn how dispatchers handle breakdowns, weather events, cancellations, and border delays effectively.",
    seo_description:
      "Learn freight disruption management and contingency planning for dispatchers. Practical guide to handling breakdowns, weather delays, cancellations, and border issues in transport operations.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["contingency-planning", "disruption-management", "dispatch", "emergency-response", "adr", "eu-mobility-package"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-05-05T10:00:00Z",
  },
  {
    title: "Document Management for Dispatch: CMR, Invoices & Transport Paperwork",
    slug: "document-management-dispatch-operations",
    excerpt:
      "Streamline document management in dispatch operations with best practices for CMR waybills, invoices, delivery receipts, and digital record-keeping that boost efficiency and accuracy.",
    seo_description:
      "Optimize document management for dispatch operations covering CMR waybills, eCMR, invoices, and delivery receipts. Best practices for organized transport paperwork and digital record keeping.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Dispatching",
    tags: ["document-management", "cmr", "invoices", "dispatch-operations", "paperwork", "ecmr", "efti"],
    featured_image: "",
    reading_time_minutes: 5,
    published_at: "2026-05-02T10:00:00Z",
  },
]

const BLOG_CATEGORIES = [
  {
    id: "1",
    name: "Profitability & Transport Finance",
    slug: "profitability-transport-finance",
    post_count: 10,
  },
  {
    id: "2",
    name: "Fleet Management",
    slug: "fleet-management",
    post_count: 7,
  },
  {
    id: "3",
    name: "Dispatching",
    slug: "dispatching",
    post_count: 8,
  },
]

export default function BlogListPage() {
  const { isAdmin } = useAuth()
  const [activeCategory, setActiveCategory] = useState<string | null>(null)

  const filteredPosts = useMemo(() => {
    if (!activeCategory) return BLOG_POSTS
    return BLOG_POSTS.filter((post) => post.category === activeCategory)
  }, [activeCategory])

  return (
    <>
      <Helmet>
        <title>Blog — Operion</title>
        <meta
          name="description"
          content="Practical insights on transport profitability, fleet management, dispatching, and logistics operations. Educational content for transport professionals."
        />
        <link rel="canonical" href="https://operion.com/blog" />
      </Helmet>

      <PageHeader
        title="Blog"
        description="Insights, updates, and practical tips on logistics management, fleet optimization, and transport operations."
      />

      {isAdmin && (
        <div className="border-y bg-accent/50">
          <div className="container-wide flex items-center justify-between py-3">
            <div className="flex items-center gap-3">
              <Badge variant="secondary">Admin mode</Badge>
              <span className="text-sm text-muted-foreground">
                You have admin access to manage blog content
              </span>
            </div>
            <Button asChild size="sm">
              <Link to="/admin/blog/editor">
                <PenLine className="h-4 w-4" />
                New Article
              </Link>
            </Button>
          </div>
        </div>
      )}

      <SectionWrapper>
        {/* Categories */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mb-10"
        >
          <div className="flex flex-wrap items-center gap-3">
            <span className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Tag className="h-4 w-4" />
              Categories:
            </span>
            <button
              onClick={() => setActiveCategory(null)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                activeCategory === null
                  ? "bg-primary text-primary-foreground"
                  : "bg-accent text-muted-foreground hover:bg-accent/80"
              }`}
            >
              All ({BLOG_POSTS.length})
            </button>
            {BLOG_CATEGORIES.map((cat) => (
              <button
                key={cat.slug}
                onClick={() => setActiveCategory(cat.name)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                  activeCategory === cat.name
                    ? "bg-primary text-primary-foreground"
                    : "bg-accent text-muted-foreground hover:bg-accent/80"
                }`}
              >
                {cat.name} ({cat.post_count})
              </button>
            ))}
          </div>
        </motion.div>

        {/* Blog Posts Grid */}
        {filteredPosts.length > 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
          >
            {filteredPosts.map((post, i) => (
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
            <h2 className="text-2xl font-bold tracking-tight">No articles found</h2>
            <p className="mt-4 text-muted-foreground">
              No articles available in this category yet. Check back soon.
            </p>
          </motion.div>
        )}
      </SectionWrapper>
    </>
  )
}
