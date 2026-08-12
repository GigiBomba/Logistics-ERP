import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import {
  CheckCircle2,
  Circle,
  ArrowRight,
  Sparkles,
  LifeBuoy,
  FileText,
  BookOpen,
  AlertTriangle,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Callout } from "@/components/ui/callout"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import {
  useOnboardingChecklist,
  useCompleteOnboardingStep,
  useTutorials,
  useChangelog,
} from "@/services/queries"
import { formatDate } from "@/lib/utils"
import { trackEvent } from "@/services/analytics"
import { useLocale } from "@/i18n/locale-context"
import type { OnboardingStep } from "@/types"

function CircularProgress({ value, total }: { value: number; total: number }) {
  const percentage = Math.round((value / total) * 100)
  const radius = 36
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  return (
    <div className="flex items-center gap-4">
      <div className="relative flex h-24 w-24 shrink-0 items-center justify-center">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="8"
            className="text-muted/30"
          />
          <motion.circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="8"
            strokeLinecap="round"
            className="text-primary"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-bold">{percentage}%</span>
        </div>
      </div>
      <div>
        <p className="text-sm font-medium">
          {value} of {total} steps completed
        </p>
        <p className="text-xs text-muted-foreground">
          Finish the required steps to get the most out of Operion.
        </p>
      </div>
    </div>
  )
}

/* ─── Loading skeleton for checklist ─── */
function ChecklistSkeleton() {
  return (
    <div className="mt-10 space-y-4">
      <Skeleton className="h-7 w-56" />
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardContent className="flex items-start gap-4 p-5">
            <Skeleton className="mt-0.5 h-6 w-6 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-72" />
            </div>
            <Skeleton className="h-8 w-20 shrink-0 rounded-md" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

/* ─── Loading skeleton for tutorials grid ─── */
function TutorialsSkeleton() {
  return (
    <div className="mt-12">
      <Skeleton className="mb-4 h-7 w-56" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardContent className="flex flex-col gap-4 p-5">
              <Skeleton className="h-10 w-10 rounded-lg" />
              <div className="space-y-2">
                <Skeleton className="h-4 w-36" />
                <Skeleton className="h-3 w-48" />
              </div>
              <div className="flex gap-2">
                <Skeleton className="h-5 w-16 rounded-full" />
                <Skeleton className="h-5 w-12" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

/* ─── Loading skeleton for releases ─── */
function ReleasesSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardContent className="p-5">
            <div className="flex items-start gap-3">
              <Skeleton className="h-8 w-8 shrink-0 rounded-lg" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-44" />
                <Skeleton className="h-3 w-64" />
                <Skeleton className="h-3 w-24" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

/** Derive a human-readable "title" for a changelog entry */
function changelogTitle(entry: { version: string; sections: { type: string; items: string[] }[] }): string {
  const added = entry.sections.find((s) => s.type === "added")
  if (added && added.items.length > 0) return added.items[0]
  for (const s of entry.sections) {
    if (s.items.length > 0) return s.items[0]
  }
  return `Version ${entry.version}`
}

/** Build a short description from changelog sections */
function changelogDescription(entry: { sections: { type: string; items: string[] }[] }): string {
  const allItems = entry.sections.flatMap((s) => s.items)
  return allItems.slice(0, 3).join(" · ") + (allItems.length > 3 ? " …" : "")
}

export default function OnboardingPage() {
  const { t } = useLocale()
  const {
    data: checklist,
    isLoading: checklistLoading,
    isError: checklistError,
  } = useOnboardingChecklist()
  const completeStep = useCompleteOnboardingStep()
  const {
    data: tutorialsData,
    isLoading: tutorialsLoading,
    isError: tutorialsError,
  } = useTutorials()
  const {
    data: changelogData,
    isLoading: changelogLoading,
    isError: changelogError,
  } = useChangelog()

  const steps: OnboardingStep[] = checklist?.steps ?? []
  const completedCount = steps.filter((s) => s.completed).length
  const totalCount = steps.length
  const requiredSteps = steps.filter((s) => s.required)
  const requiredCompleted = requiredSteps.filter((s) => s.completed).length
  const latestReleases = Array.isArray(changelogData)
    ? changelogData.slice(0, 3)
    : []

  return (
    <>
      <Helmet>
        <title>{t("onboarding.pageTitle")}</title>
      </Helmet>

      <SectionWrapper>
        {/* Page Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h1 className="text-3xl font-bold tracking-tight">{t("onboarding.heading")}</h1>
          <p className="mt-2 text-muted-foreground">
            {t("onboarding.description")}
          </p>
        </motion.div>

        {/* Overall Progress */}
        {!checklistLoading && !checklistError && steps.length > 0 && (
          <motion.div
            className="mt-8"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <Card>
              <CardContent className="flex flex-col gap-6 p-6 sm:flex-row sm:items-center">
                <CircularProgress value={completedCount} total={totalCount} />
                <div className="flex-1 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t("onboarding.requiredSteps")}</span>
                    <span className="font-medium">
                      {t("onboarding.completed").replace("{completed}", String(requiredCompleted)).replace("{total}", String(requiredSteps.length))}
                    </span>
                  </div>
                  <Progress
                    value={
                      requiredSteps.length > 0
                        ? (requiredCompleted / requiredSteps.length) * 100
                        : 0
                    }
                    variant="success"
                  />
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t("onboarding.allSteps")}</span>
                    <span className="font-medium">
                      {t("onboarding.completed").replace("{completed}", String(completedCount)).replace("{total}", String(totalCount))}
                    </span>
                  </div>
                  <Progress
                    value={totalCount > 0 ? (completedCount / totalCount) * 100 : 0}
                  />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Checklist */}
        {checklistLoading && <ChecklistSkeleton />}
        {checklistError && (
          <div className="mt-10">
            <Card>
              <CardContent className="flex items-center gap-4 p-6 text-red-600">
                <AlertTriangle className="h-5 w-5 shrink-0" />
                <p className="text-sm font-medium">
                  {t("onboarding.checklistError")}
                </p>
              </CardContent>
            </Card>
          </div>
        )}
        {!checklistLoading && !checklistError && (
          <div className="mt-10 space-y-4">
            <h2 className="text-xl font-bold tracking-tight">{t("onboarding.checklist")}</h2>
            {steps.length === 0 ? (
              <EmptyState
                title={t("onboarding.checklistComplete")}
                description={t("onboarding.checklistCompleteDesc")}
              />
            ) : (
              steps.map((step, index) => (
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.05 * index, ease: [0.22, 1, 0.36, 1] }}
                >
                  <Card
                    className={`transition-colors ${step.completed ? "border-green-200/50 bg-green-50/30 dark:border-green-900/30 dark:bg-green-950/20" : ""}`}
                  >
                    <CardContent className="flex items-start gap-4 p-5">
                      <div className="mt-0.5 shrink-0">
                        {step.completed ? (
                          <CheckCircle2 className="h-6 w-6 text-green-600" />
                        ) : (
                          <Circle className="h-6 w-6 text-muted-foreground/40" />
                        )}
                      </div>
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-muted-foreground">
                            {t("onboarding.step").replace("{number}", String(index + 1))}
                          </span>
                          {step.required && (
                            <Badge variant="destructive" className="text-[10px]">
                              {t("onboarding.required")}
                            </Badge>
                          )}
                        </div>
                        <h3
                          className={`text-sm font-semibold ${step.completed ? "line-through opacity-60" : ""}`}
                        >
                          {step.title}
                        </h3>
                        <p className="text-sm text-muted-foreground">{step.description}</p>
                      </div>
                      <div className="shrink-0">
                        {step.completed ? (
                          <Badge variant="success">{t("onboarding.done")}</Badge>
                        ) : (
                          <Button
                            size="sm"
                            onClick={() =>
                              completeStep.mutate(step.id, {
                                onSuccess: () =>
                                  trackEvent("onboarding_step_completed", "onboarding", step.id),
                              })
                            }
                            disabled={completeStep.isPending}
                          >
                            {completeStep.isPending ? (
                              <span className="flex items-center gap-1">
                                <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                                {t("onboarding.saving")}
                              </span>
                            ) : (
                              <>
                                {t("onboarding.complete")} <ArrowRight className="ml-1 h-3 w-3" />
                              </>
                            )}
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))
            )}
          </div>
        )}

        {/* Recommended Tutorials */}
        {tutorialsLoading && <TutorialsSkeleton />}
        {tutorialsError && (
          <motion.div
            className="mt-12"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <Card>
              <CardContent className="flex items-center gap-4 p-6 text-red-600">
                <AlertTriangle className="h-5 w-5 shrink-0" />
                <p className="text-sm font-medium">
                  {t("onboarding.tutorialsError")}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        )}
        {!tutorialsLoading && !tutorialsError && (
          <motion.div
            className="mt-12"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <h2 className="text-xl font-bold tracking-tight mb-4">{t("onboarding.recommendedTutorials")}</h2>
            {!tutorialsData || (Array.isArray(tutorialsData) && tutorialsData.length === 0) ? (
              <EmptyState
                title={t("onboarding.noTutorials")}
                description={t("onboarding.noTutorialsDesc")}
              />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {(Array.isArray(tutorialsData) ? tutorialsData : []).map(
                  (tutorial: any, index: number) => (
                    <motion.div
                      key={tutorial.id ?? tutorial.title}
                      initial={{ opacity: 0, y: 20 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: 0.05 * index }}
                    >
                      <Card className="h-full transition-shadow hover:shadow-md">
                        <CardContent className="flex flex-col gap-4 p-5">
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                            <FileText className="h-5 w-5 text-primary" />
                          </div>
                          <div className="flex-1">
                            <h3 className="text-sm font-semibold">{tutorial.title}</h3>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {tutorial.excerpt ?? tutorial.description}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="secondary" className="text-[10px]">
                              {tutorial.category
                                ? tutorial.category.charAt(0).toUpperCase() +
                                  tutorial.category.slice(1)
                                : t("onboarding.general")}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {tutorial.reading_time_minutes
                                ? `${tutorial.reading_time_minutes} min`
                                : ""}
                            </span>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ),
                )}
              </div>
            )}
          </motion.div>
        )}

        {/* Release Highlights + Best Practices placeholder */}
        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <h2 className="text-xl font-bold tracking-tight mb-4">{t("onboarding.releaseHighlights")}</h2>
            {changelogLoading && <ReleasesSkeleton />}
            {changelogError && (
              <Card>
                <CardContent className="flex items-center gap-4 p-6 text-red-600">
                  <AlertTriangle className="h-5 w-5 shrink-0" />
                  <p className="text-sm font-medium">
                    {t("onboarding.releasesError")}
                  </p>
                </CardContent>
              </Card>
            )}
            {!changelogLoading && !changelogError && (
              <>
                {latestReleases.length === 0 ? (
                  <EmptyState
                    title={t("onboarding.noReleases")}
                    description={t("onboarding.noReleasesDesc")}
                  />
                ) : (
                  <div className="space-y-4">
                    {latestReleases.map((release, index) => (
                      <motion.div
                        key={release.version}
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.05 * index }}
                      >
                        <Card>
                          <CardContent className="p-5">
                            <div className="flex items-start gap-3">
                              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent">
                                <Sparkles className="h-4 w-4 text-primary" />
                              </div>
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <h3 className="text-sm font-semibold">
                                    {changelogTitle(release)}
                                  </h3>
                                  <Badge variant="outline" className="text-[10px]">
                                    v{release.version}
                                  </Badge>
                                </div>
                                <p className="mt-1 text-xs text-muted-foreground">
                                  {changelogDescription(release)}
                                </p>
                                <p className="mt-2 text-xs text-muted-foreground/60">
                                  {release.release_date
                                    ? formatDate(release.release_date)
                                    : ""}
                                </p>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    ))}
                  </div>
                )}
              </>
            )}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 }}
          >
            <h2 className="text-xl font-bold tracking-tight mb-4">{t("onboarding.bestPractices")}</h2>
            <Card>
              <CardContent className="p-6">
                <EmptyState
                  icon={<BookOpen className="h-12 w-12" />}
                  title={t("onboarding.bestPracticesSoon")}
                  description={t("onboarding.bestPracticesSoonDesc")}
                />
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* CTA */}
        <motion.div
          className="mt-12"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
        >
          <Callout variant="info" icon={<LifeBuoy className="h-5 w-5 shrink-0 mt-0.5" />}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-semibold">{t("onboarding.needHelp")}</p>
                <p className="text-sm">
                  {t("onboarding.needHelpDesc")}
                </p>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link to="/dashboard/support">{t("onboarding.contactSupport")}</Link>
              </Button>
            </div>
          </Callout>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
