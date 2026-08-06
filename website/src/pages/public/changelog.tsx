import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useChangelog } from "@/services/queries"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { formatDate } from "@/lib/utils"
import { cn } from "@/lib/utils"
import { AlertCircle, GitCommit } from "lucide-react"
import { useReducedMotion } from "@/services/accessibility"
import type { ChangelogEntry, ChangelogSection } from "@/types"

const sectionBadgeColors: Record<ChangelogSection["type"], string> = {
  added: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  changed: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  fixed: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
  removed: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  deprecated: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
}

function TimelineEntry({ entry, index }: { entry: ChangelogEntry; index: number }) {
  const prefersReducedMotion = useReducedMotion()
  return (
    <motion.div
      initial={prefersReducedMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: prefersReducedMotion ? 0 : Math.min(index * 0.05, 0.3) }}
      className="relative flex gap-6 pb-12 last:pb-0"
    >
      {/* Timeline dot */}
      <div className="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border bg-background">
        <span className="text-[10px] font-bold leading-none text-muted-foreground">
          {index === 0 ? "NOW" : ""}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 space-y-4 pt-0.5">
        <div>
          <h3 className="text-lg font-semibold">v{entry.version}</h3>
          <p className="text-sm text-muted-foreground">
            {formatDate(entry.release_date)}
          </p>
        </div>

        {entry.sections.map((section) => (
          <div key={section.type}>
            <span
              className={cn(
                "inline-block rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                sectionBadgeColors[section.type]
              )}
            >
              {section.type}
            </span>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {section.items.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        ))}

        {entry.known_issues && entry.known_issues.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/30">
            <p className="text-xs font-semibold text-amber-800 dark:text-amber-300">
              Known Issues
            </p>
            <ul className="mt-1 list-disc pl-4 text-xs text-amber-700 dark:text-amber-400">
              {entry.known_issues.map((issue, i) => (
                <li key={i}>{issue}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </motion.div>
  )
}

export default function ChangelogPage() {
  const { data: entries, isLoading, error } = useChangelog()

  return (
    <>
      <SeoHead
        title="Changelog — Operion"
        description="Track every update to the Operion platform."
        canonical="https://operionerp.xyz/changelog"
      />

      <PageHeader
        title="Changelog"
        description="Track every update to the Operion platform."
      />

      <SectionWrapper>
        {isLoading ? (
          <div className="flex justify-center py-20">
            <LoadingSpinner size="lg" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <AlertCircle className="mb-4 h-12 w-12 text-destructive/50" />
            <h2 className="text-xl font-semibold">Failed to load changelog</h2>
            <p className="mt-2 text-muted-foreground">
              Something went wrong while loading the changelog. Please try again later.
            </p>
          </div>
        ) : !entries || entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <GitCommit className="mb-4 h-12 w-12 text-muted-foreground/50" />
            <h2 className="text-xl font-semibold">No releases yet</h2>
            <p className="mt-2 text-muted-foreground">
              Release notes will appear here once the first public version ships.
            </p>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl">
            <div className="relative">
              {/* Vertical timeline line */}
              <div
                className="absolute left-[19px] top-0 h-full w-px bg-border"
                aria-hidden="true"
              />
              {entries.map((entry, index) => (
                <TimelineEntry key={entry.version} entry={entry} index={index} />
              ))}
            </div>
          </div>
        )}
      </SectionWrapper>
    </>
  )
}
