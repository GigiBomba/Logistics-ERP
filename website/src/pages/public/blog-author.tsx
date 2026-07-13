import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useParams, useSearchParams, Link } from "react-router"
import { ArrowLeft, FileText, User } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { BlogCard } from "@/components/shared/blog-card"
import { Pagination } from "@/components/ui/pagination"
import { Skeleton } from "@/components/ui/skeleton"
import { blogConfig } from "@/config/site"
import { useBlogPosts } from "@/services/queries"

const MOCK_AUTHORS: Record<
  string,
  {
    id: string
    name: string
    avatar: string
    role: string
    bio: string
  }
> = {
  "operion-team": {
    id: "operion-team",
    name: "Operion Team",
    avatar: "",
    role: "Transport & Logistics",
    bio: "The Operion Team writes about fleet management, transport operations, and logistics best practices. We are building a logistics ERP for transport professionals, based in Romania.",
  },
}

const MOCK_POSTS = [
  {
    title: "Preventive Maintenance Guide: Keep Your Fleet on the Road",
    slug: "preventive-maintenance-scheduling-small-mid-size-fleets",
    excerpt:
      "Build a preventive maintenance program that keeps your fleet on the road. Practical guide covering service intervals, cost savings, and scheduling for small to mid-size fleets.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["preventive-maintenance", "scheduling", "fleet-operations", "fleet-maintenance", "IRU"],
    featured_image: "",
    reading_time_minutes: 8,
    published_at: "2026-07-12T10:00:00Z",
  },
  {
    title: "Tire Management: Cut Fleet Operating Costs Through Better Tire Care",
    slug: "tire-management-overlooked-cost-center-fleet-operations",
    excerpt:
      "Tires are a major fleet operating expense. Learn how tire selection, pressure monitoring, and retreading strategies reduce costs and improve safety for transport companies.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["tire-management", "operating-costs", "fleet-maintenance", "safety", "retreading"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-07-10T10:00:00Z",
  },
  {
    title: "Total Cost of Ownership: Calculate Commercial Vehicle Costs",
    slug: "calculate-total-cost-ownership-commercial-vehicles",
    excerpt:
      "Learn how to calculate total cost of ownership for commercial vehicles. A framework for making informed fleet purchasing and replacement decisions that protect your bottom line.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["total-cost-of-ownership", "cost-analysis", "fleet-budgeting", "vehicle-costs", "fleet-planning"],
    featured_image: "",
    reading_time_minutes: 9,
    published_at: "2026-07-08T10:00:00Z",
  },
  {
    title: "Fleet Utilization: Maximize Vehicle Productivity Without Adding Trucks",
    slug: "fleet-utilization-getting-most-out-every-vehicle",
    excerpt:
      "Improve fleet utilization to increase profitability without adding vehicles. Learn how to measure idle time, optimize multi-shift operations, and boost fleet efficiency.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["fleet-utilization", "idle-time", "fleet-efficiency", "multi-shift", "capacity-planning"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-07-05T10:00:00Z",
  },
  {
    title: "Driver Performance Metrics: Safety, Fuel Economy & Fleet Analytics",
    slug: "driver-performance-metrics-that-actually-matter",
    excerpt:
      "Focus on driver performance metrics that directly impact safety, fuel consumption, and fleet efficiency. Learn which KPIs matter most for transport operations.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["driver-performance", "safety", "fuel-economy", "fleet-analytics", "telematics"],
    featured_image: "",
    reading_time_minutes: 7,
    published_at: "2026-07-01T10:00:00Z",
  },
  {
    title: "Vehicle Replacement: A Data-Driven Framework for Fleet Renewal",
    slug: "when-to-replace-vehicle-data-driven-approach",
    excerpt:
      "Replace vehicles at the right time with a data-driven approach. Learn how to balance depreciation costs against rising maintenance expenses for optimal fleet renewal.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["vehicle-replacement", "lifecycle-management", "depreciation", "fleet-planning", "total-cost-of-ownership"],
    featured_image: "",
    reading_time_minutes: 8,
    published_at: "2026-06-28T10:00:00Z",
  },
  {
    title: "Mixed Fleet Management: How to Run Vans, Trucks & Artics Together",
    slug: "managing-mixed-fleet-challenges-different-vehicle-types",
    excerpt:
      "Running vans, rigid trucks, and artics in one fleet presents unique challenges. Learn best practices for mixed fleet management in maintenance, routing, and driver assignment.",
    author_name: "Operion Team",
    author_avatar: "",
    category: "Fleet Management",
    tags: ["mixed-fleet", "vehicle-types", "fleet-management", "logistics", "fleet-optimization"],
    featured_image: "",
    reading_time_minutes: 6,
    published_at: "2026-06-25T10:00:00Z",
  },
]

export default function BlogAuthorPage() {
  const { authorId } = useParams<{ authorId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10))

  const { isLoading: postsLoading } = useBlogPosts({ page, author: authorId })

  const author = authorId ? MOCK_AUTHORS[authorId] : undefined

  const authorPosts = useMemo(() => {
    if (!author) return []
    return MOCK_POSTS.filter((p) => p.author_name === author.name)
  }, [author])

  const totalPages = Math.max(1, Math.ceil(authorPosts.length / blogConfig.postsPerPage))
  const safePage = Math.min(page, totalPages)
  const paginatedPosts = authorPosts.slice(
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

  if (!postsLoading && !author) {
    return (
      <>
        <Helmet>
          <title>Author Not Found — Operion</title>
        </Helmet>
        <PageHeader title="Author Not Found" />
        <SectionWrapper>
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <User className="mb-4 h-12 w-12 text-muted-foreground/50" />
            <h2 className="text-xl font-semibold">This author does not exist.</h2>
            <Link
              to="/blog"
              className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Blog
            </Link>
          </div>
        </SectionWrapper>
      </>
    )
  }

  return (
    <>
      <Helmet>
        <title>
          {author ? `${author.name} — Blog — Operion` : "Author — Operion"}
        </title>
        {author && (
          <meta name="description" content={`Articles by ${author.name}, ${author.role} at Operion.`} />
        )}
      </Helmet>

      <PageHeader
        title={author ? author.name : "Author"}
        description={author ? `${author.role} at Operion` : ""}
      />

      <SectionWrapper className="pt-0">
        <div className="container-wide">
          {/* Author Profile */}
          {author && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="mb-12 flex flex-col items-start gap-6 rounded-xl border bg-card p-6 sm:flex-row sm:items-center sm:p-8"
            >
              {author.avatar ? (
                <img
                  loading="lazy"
                  src={author.avatar}
                  alt={author.name}
                  className="h-20 w-20 rounded-full object-cover"
                />
              ) : (
                <div className="flex h-20 w-20 items-center justify-center rounded-full bg-accent">
                  <User className="h-10 w-10 text-muted-foreground" />
                </div>
              )}
              <div>
                <h2 className="text-xl font-semibold">{author.name}</h2>
                <p className="text-sm text-muted-foreground">{author.role}</p>
                <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                  {author.bio}
                </p>
              </div>
            </motion.div>
          )}

          <div className="mb-6 flex items-center justify-between">
            <h3 className="text-lg font-semibold">
              {authorPosts.length} article{authorPosts.length !== 1 ? "s" : ""}
            </h3>
            <Link
              to="/blog"
              className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              All articles
            </Link>
          </div>

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
              <h3 className="text-lg font-semibold">No articles yet</h3>
              <p className="mt-2 text-muted-foreground">
                This author has not published any articles.
              </p>
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
        </div>
      </SectionWrapper>
    </>
  )
}
