import { SeoHead } from "@/components/seo/seo-head"
import { JsonLd, itemListSchema } from "@/components/seo/structured-data"
import { motion } from "motion/react"
import { useParams, useSearchParams, Link } from "react-router"
import { ArrowLeft, FileText, User } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { BlogCard } from "@/components/shared/blog-card"
import { Pagination } from "@/components/ui/pagination"
import { Skeleton } from "@/components/ui/skeleton"
import { blogConfig } from "@/config/site"
import { useBlogPosts, useBlogAuthor } from "@/services/queries"
import { useLocale } from "@/i18n/locale-context"

export default function BlogAuthorPage() {
  const { t } = useLocale()
  const { authorId } = useParams<{ authorId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10))

  const { data: postsData, isLoading: postsLoading } = useBlogPosts({ page, author: authorId })
  const { data: author, isLoading: authorLoading } = useBlogAuthor(authorId)

  const posts = (postsData?.items ?? []) as any[]
  const totalPages = postsData ? Math.max(1, Math.ceil(postsData.total / blogConfig.postsPerPage)) : 1
  const safePage = Math.min(page, totalPages)

  const handlePageChange = (newPage: number) => {
    const params = new URLSearchParams(searchParams)
    if (newPage === 1) {
      params.delete("page")
    } else {
      params.set("page", String(newPage))
    }
    setSearchParams(params, { replace: true })
  }

  const isLoading = postsLoading || authorLoading

  if (!isLoading && authorId && !author) {
    return (
      <>
        <SeoHead
          title={t("blog.authorNotFoundTitle")}
          description={t("blog.authorNotFoundDesc")}
        />
        <PageHeader title={t("blog.authorNotFound")} />
        <SectionWrapper>
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <User className="mb-4 h-12 w-12 text-muted-foreground/50" />
            <h2 className="text-xl font-semibold">{t("blog.authorDoesNotExist")}</h2>
            <Link
              to="/blog"
              className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              <ArrowLeft className="h-4 w-4" />
              {t("blog.backToBlog")}
            </Link>
          </div>
        </SectionWrapper>
      </>
    )
  }

  return (
    <>
      <SeoHead
        title={author ? `${author.name} — Blog — Operion` : "Author — Operion"}
        description={author ? `Articles by ${author.name}${author.role ? `, ${author.role}` : ""} at Operion.` : "Operion blog author page."}
        canonical={authorId ? `https://operionerp.xyz/blog/author/${authorId}` : undefined}
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
        title={author ? author.name : "Author"}
        description={author ? (author.role ? `${author.role} at Operion` : "") : ""}
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
              {author.avatar_url ? (
                <img
                  loading="lazy"
                  src={author.avatar_url}
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
                {author.role && (
                  <p className="text-sm text-muted-foreground">{author.role}</p>
                )}
                {author.bio && (
                  <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                    {author.bio}
                  </p>
                )}
              </div>
            </motion.div>
          )}

          <div className="mb-6 flex items-center justify-between">
            <h3 className="text-lg font-semibold">
              {posts.length} article{posts.length !== 1 ? "s" : ""}
            </h3>
            <Link
              to="/blog"
              className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              All articles
            </Link>
          </div>

          {isLoading ? (
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
              <h3 className="text-lg font-semibold">{t("blog.noArticlesYet")}</h3>
              <p className="mt-2 text-muted-foreground">
                {t("blog.noArticlesYetDesc")}
              </p>
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
        </div>
      </SectionWrapper>
    </>
  )
}
