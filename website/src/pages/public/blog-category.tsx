import { SeoHead } from "@/components/seo/seo-head"
import { JsonLd, itemListSchema } from "@/components/seo/structured-data"
import { motion } from "motion/react"
import { useParams, useSearchParams, Link } from "react-router"

import { useLocale } from "@/i18n/locale-context"
import { ArrowLeft, FileText } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { BlogCard } from "@/components/shared/blog-card"
import { Pagination } from "@/components/ui/pagination"
import { SearchInput } from "@/components/shared/search-input"
import { Skeleton } from "@/components/ui/skeleton"
import { blogConfig } from "@/config/site"
import { useBlogPosts } from "@/services/queries"

const CATEGORY_NAMES: Record<string, string> = {
  "ai-automation": "AI & Automation",
  "profitability-transport-finance": "Profitability & Transport Finance",
  "fleet-management": "Fleet Management",
  dispatching: "Dispatching",
}

export default function BlogCategoryPage() {
  const { t } = useLocale()
  const { category: categorySlug } = useParams<{ category: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10))
  const search = searchParams.get("search") || ""

  const { data: postsData, isLoading: postsLoading } = useBlogPosts({ page, category: categorySlug, search })

  const posts = (postsData?.items ?? []) as any[]
  const totalCount = postsData?.total ?? posts.length
  const totalPages = Math.max(1, Math.ceil(totalCount / blogConfig.postsPerPage))
  const safePage = Math.min(page, totalPages)

  const categoryName = categorySlug ? CATEGORY_NAMES[categorySlug] || categorySlug : ""

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
      <SeoHead
        title={`${categoryName} — Blog — Operion`}
        description={`Articles in the ${categoryName} category on the Operion blog.`}
        canonical={`https://operionerp.xyz/blog/category/${categorySlug}`}
      />

      {/* Structured Data: ItemList */}
      {posts.length > 0 && (
        <JsonLd
          data={itemListSchema({
            items: posts.map((post: any) => ({
              title: post.title,
              url: `https://operionerp.xyz/blog/${post.slug}`,
            })),
          })}
        />
      )}

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
              placeholder={t("common.searchArticles")}
              value={search}
              onChange={handleSearchChange}
              className="w-full sm:max-w-sm"
            />
            <div className="text-sm text-muted-foreground">
              {totalCount} article{totalCount !== 1 ? "s" : ""}
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
        ) : posts.length > 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
          >
            {posts.map((post, i) => (
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
            <h3 className="text-lg font-semibold">{t("blog.noArticles")}</h3>
            <p className="mt-2 text-muted-foreground">
              {t("blog.noArticlesDesc")}
            </p>
            <Link
              to="/blog"
              className="mt-4 text-sm font-medium text-primary hover:underline"
            >
              {t("blog.backToArticles")}
            </Link>
          </motion.div>
        )}

        {posts.length > 0 && totalPages > 1 && (
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
