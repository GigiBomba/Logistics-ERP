import { useMemo, useState } from "react"
import { SeoHead } from "@/components/seo/seo-head"
import { JsonLd, itemListSchema } from "@/components/seo/structured-data"
import { motion } from "motion/react"
import { Link } from "react-router"
import { PenLine, Tag, Newspaper, AlertCircle } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { BlogCard } from "@/components/shared/blog-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/shared/empty-state"
import { useAuth } from "@/contexts/auth-provider"
import { useBlogPosts, useBlogCategories } from "@/services/queries"
import { useLocale } from "@/i18n/locale-context"

export default function BlogListPage() {
  const { isAdmin } = useAuth()
  const { t } = useLocale()
  const [activeCategory, setActiveCategory] = useState<string | null>(null)

  const { data: postsData, isLoading, isError, refetch } = useBlogPosts()
  const { data: categoriesData } = useBlogCategories()

  const posts = postsData?.items ?? []

  // Derive category filters from the posts we actually have, falling back to
  // the categories endpoint when it provides ones we haven't fetched yet.
  const categories = useMemo(() => {
    const names = new Set<string>()
    for (const post of posts) {
      if (post.category) names.add(post.category)
    }
    for (const cat of categoriesData ?? []) {
      if (cat.name) names.add(cat.name)
    }
    return Array.from(names).map((name) => ({
      name,
      count: posts.filter((post: any) => post.category === name).length,
    }))
  }, [posts, categoriesData])

  const filteredPosts = useMemo(() => {
    if (!activeCategory) return posts
    return posts.filter((post: any) => post.category === activeCategory)
  }, [activeCategory, posts])

  return (
    <>
      <SeoHead
        title="Blog — Operion"
        description="Practical insights on transport profitability, fleet management, dispatching, and logistics operations. Educational content for transport professionals."
        canonical="https://operionerp.xyz/blog"
      />

      {/* Structured Data: ItemList */}
      <JsonLd
        data={itemListSchema({
          items: filteredPosts.map((post: any) => ({
            title: post.title,
            url: `https://operionerp.xyz/blog/${post.slug}`,
          })),
        })}
      />

      <PageHeader
        title={t("blog.title")}
        description={t("blog.pageDesc")}
      />

      {isAdmin && (
        <div className="border-y bg-accent/50">
          <div className="container-wide flex items-center justify-between py-3">
            <div className="flex items-center gap-3">
              <Badge variant="secondary">{t("blog.adminMode")}</Badge>
              <span className="text-sm text-muted-foreground">
                {t("blog.adminDesc")}
              </span>
            </div>
            <Button asChild size="sm">
              <Link to="/admin/blog/editor">
                <PenLine className="h-4 w-4" />
                {t("blog.newArticle")}
              </Link>
            </Button>
          </div>
        </div>
      )}

      <SectionWrapper>
        {/* Categories */}
        {!isLoading && posts.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-10"
          >
            <div className="flex flex-wrap items-center gap-3">
              <span className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <Tag className="h-4 w-4" />
                {t("blog.categories")}
              </span>
              <button
                onClick={() => setActiveCategory(null)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                  activeCategory === null
                    ? "bg-primary text-primary-foreground"
                    : "bg-accent text-muted-foreground hover:bg-accent/80"
                }`}
              >
                {t("blog.all").replace("{count}", String(posts.length))}
              </button>
              {categories.map((cat) => (
                <button
                  key={cat.name}
                  onClick={() => setActiveCategory(cat.name)}
                  className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                    activeCategory === cat.name
                      ? "bg-primary text-primary-foreground"
                      : "bg-accent text-muted-foreground hover:bg-accent/80"
                  }`}
                >
                  {cat.name} ({cat.count})
                </button>
              ))}
            </div>
          </motion.div>
        )}

        {/* Loading skeletons */}
        {isLoading ? (
          <div aria-label={t("blog.loadingArticles")} className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex flex-col gap-3">
                <Skeleton className="h-5 w-24 rounded-full" />
                <Skeleton className="h-6 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-2/3" />
                <div className="mt-auto flex items-center justify-between pt-4">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
            ))}
          </div>
        ) : isError ? (
          <EmptyState
            icon={<AlertCircle className="h-12 w-12 text-destructive/70" />}
            title="Failed to load articles"
            description="We couldn't fetch the latest articles right now. Please try again."
            action={
              <Button variant="outline" onClick={() => refetch()}>
                Try again
              </Button>
            }
          />
        ) : filteredPosts.length > 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
          >
            {filteredPosts.map((post: any, i: number) => (
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
          <EmptyState
            icon={<Newspaper className="h-12 w-12 text-muted-foreground/50" />}
            title="No articles published yet"
            description="We're still writing our first articles. Check back soon for practical transport and logistics guides."
          />
        )}
      </SectionWrapper>
    </>
  )
}
