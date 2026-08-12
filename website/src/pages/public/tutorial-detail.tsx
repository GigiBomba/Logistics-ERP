import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import { useParams, Link } from "react-router"
import { ArrowLeft, Calendar, Clock, BookOpen } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { TableOfContents } from "@/components/shared/table-of-contents"
import { SocialShare } from "@/components/shared/social-share"
import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
import { useTutorial } from "@/services/queries"
import { formatDate, cn } from "@/lib/utils"
import { useLocale } from "@/i18n/locale-context"

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

const proseClasses =
  "[&_h2]:mt-10 [&_h2]:mb-4 [&_h2]:text-2xl [&_h2]:font-bold [&_h2]:tracking-tight [&_p]:mb-4 [&_p]:leading-7 [&_p]:text-muted-foreground [&_ul]:my-6 [&_ul]:ml-6 [&_ul]:list-disc [&_li]:mb-2 [&_li]:text-muted-foreground [&_strong]:font-semibold [&_strong]:text-foreground [&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-muted [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-sm [&_code]:font-mono"

function ArticleSkeleton() {
  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <Skeleton className="h-10 w-3/4" />
        <div className="flex items-center gap-4">
          <Skeleton className="h-6 w-20 rounded-full" />
          <Skeleton className="h-6 w-20 rounded-full" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>
      <div className="space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
      </div>
    </div>
  )
}

export default function TutorialDetailPage() {
  const { t } = useLocale()
  const { slug } = useParams<{ slug: string }>()
  const { data: tutorial, isLoading } = useTutorial(slug || "")

  const shareUrl =
    typeof window !== "undefined"
      ? window.location.href
      : `https://operionerp.xyz/tutorials/${slug}`

  if (!isLoading && !tutorial) {
    return (
      <>
        <SeoHead
          title={t("tutorials.notFoundTitle")}
          description={t("tutorials.notFoundDesc")}
        />
        <PageHeader title={t("tutorials.notFoundHeading")} />
        <SectionWrapper>
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <BookOpen className="mb-4 h-12 w-12 text-muted-foreground/50" />
            <h2 className="text-xl font-semibold">{t("tutorials.doesNotExist")}</h2>
            <p className="mt-2 text-muted-foreground">
              {t("tutorials.doesNotExistDesc")}
            </p>
            <Link
              to="/tutorials"
              className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              <ArrowLeft className="h-4 w-4" />
              {t("tutorials.backToTutorials")}
            </Link>
          </div>
        </SectionWrapper>
      </>
    )
  }

  return (
    <>
      <SeoHead
        title={tutorial ? `${tutorial.title} — Operion` : "Loading... — Operion"}
        description={tutorial ? tutorial.excerpt : "Loading tutorial..."}
        canonical={tutorial ? `https://operionerp.xyz/tutorials/${tutorial.slug}` : undefined}
      />

      <div className="py-8">
        <div className="container-wide">
          <Link
            to="/tutorials"
            className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("tutorials.backToTutorials")}
          </Link>
        </div>
      </div>

      {isLoading || !tutorial ? (
        <SectionWrapper className="pt-0">
          <div className="container-wide">
            <div className="mx-auto max-w-3xl">
              <ArticleSkeleton />
            </div>
          </div>
        </SectionWrapper>
      ) : (
        <>
          {/* Header */}
          <section className="pb-8">
            <div className="container-wide">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="mx-auto max-w-3xl"
              >
                <div className="mb-6 flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-md border border-transparent px-2.5 py-0.5 text-xs font-semibold shadow",
                      getCategoryColor(tutorial.category)
                    )}
                  >
                    {tutorial.category}
                  </span>
                </div>
                <h1 className="text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
                  {tutorial.title}
                </h1>
                <p className="mt-4 text-lg text-muted-foreground">{tutorial.excerpt}</p>

                <div className="mt-6 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-4 w-4" />
                    {formatDate(tutorial.published_at)}
                  </span>
                  <span className="hidden text-border sm:inline">|</span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {tutorial.reading_time_minutes} min read
                  </span>
                  <span className="hidden text-border sm:inline">|</span>
                  <span className="text-xs text-muted-foreground">
                    Updated {formatDate(tutorial.updated_at)}
                  </span>
                </div>
              </motion.div>
            </div>
          </section>

          {/* Content */}
          <SectionWrapper className="pt-0">
            <div className="container-wide">
              <div className="grid gap-8 lg:grid-cols-[1fr_280px]">
                <div className="mx-auto w-full max-w-3xl">
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.1 }}
                  >
                    <article
                      className={proseClasses}
                      dangerouslySetInnerHTML={{ __html: tutorial.content }}
                    />
                  </motion.div>

                  {/* Tags */}
                  <div className="mt-10 flex flex-wrap gap-2">
                    <Tag variant="outline">{tutorial.category}</Tag>
                  </div>

                  {/* Social Share */}
                  <div className="mt-10 flex items-center justify-between border-t pt-6">
                    <span className="text-sm font-medium text-muted-foreground">
                      Share this tutorial
                    </span>
                    <SocialShare url={shareUrl} title={tutorial.title} />
                  </div>
                </div>

                {/* TOC Sidebar */}
                <aside className="hidden lg:block">
                  <TableOfContents />
                </aside>
              </div>
            </div>
          </SectionWrapper>

          {/* Next Steps / Related */}
          <SectionWrapper className="bg-muted/30">
            <div className="container-wide">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
              >
                <h2 className="mb-2 text-2xl font-bold tracking-tight">{t("tutorials.nextSteps")}</h2>
                <p className="mb-8 text-muted-foreground">
                  {t("tutorials.nextStepsDesc")}
                </p>
                <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  <p className="col-span-full text-muted-foreground">
                    {t("tutorials.relatedComingSoon")}
                  </p>
                </div>
              </motion.div>
            </div>
          </SectionWrapper>
        </>
      )}
    </>
  )
}
