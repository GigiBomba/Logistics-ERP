import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion, AnimatePresence } from "motion/react"
import {
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { useOpsGuardrails, useOpsResolveGuardrail } from "@/services/queries"

export default function OpsGuardrailsPage() {
  const { t } = useLocale()
  const { data: violations, isLoading, isError } = useOpsGuardrails()
  const resolveGuardrail = useOpsResolveGuardrail()
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  const items = violations ?? []

  const toggleExpand = (id: number) => {
    const next = new Set(expandedIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setExpandedIds(next)
  }

  const severityBadge = (severity: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline" | "success"> = {
      hard_block: "destructive",
      review_required: "default",
    }
    const labels: Record<string, string> = {
      hard_block: t("ops.guardrails.hardBlock") || "Hard block",
      review_required: t("ops.guardrails.reviewRequired") || "Review required",
    }
    return <Badge variant={variants[severity] || "default"}>{labels[severity] || severity}</Badge>
  }

  if (isLoading) {
    return (
      <>
        <Helmet>
          <title>{t("ops.guardrails.pageTitle") || "Guardrails — Operion Ops"}</title>
        </Helmet>
        <SectionWrapper className="pt-0">
          <div className="flex justify-center py-12">
            <LoadingSpinner size="lg" />
          </div>
        </SectionWrapper>
      </>
    )
  }

  if (isError) {
    return (
      <>
        <Helmet>
          <title>{t("ops.guardrails.pageTitle") || "Guardrails — Operion Ops"}</title>
        </Helmet>
        <SectionWrapper className="pt-0">
          <EmptyState
            title={t("common.error") || "Error"}
            description={t("ops.guardrails.loadError") || "Failed to load guardrail violations. Please try again later."}
            icon={<AlertTriangle className="h-16 w-16" />}
          />
        </SectionWrapper>
      </>
    )
  }

  return (
    <>
      <Helmet>
        <title>{t("ops.guardrails.pageTitle") || "Guardrails — Operion Ops"}</title>
      </Helmet>

      <SectionWrapper className="pt-0">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldAlert className="h-5 w-5" />
                {t("ops.guardrails.title") || "Guardrail violations"}
              </CardTitle>
              <CardDescription>
                {t("ops.guardrails.description") || "Review automated guardrail catches and decide disposition."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {items.length === 0 ? (
                <EmptyState
                  title={t("ops.guardrails.noViolations") || "No violations"}
                  description={t("ops.guardrails.noViolationsDesc") || "All guardrails are passing."}
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="py-3 pr-4 font-medium">{t("ops.guardrails.colId") || "ID"}</th>
                        <th className="py-3 pr-4 font-medium">{t("ops.guardrails.colSeverity") || "Severity"}</th>
                        <th className="py-3 pr-4 font-medium">{t("ops.guardrails.colDiff") || "Diff excerpt"}</th>
                        <th className="py-3 pr-4 font-medium">{t("ops.guardrails.colTicket") || "Linked ticket"}</th>
                        <th className="py-3 pr-4 font-medium">{t("ops.guardrails.colStatus") || "Status"}</th>
                        <th className="py-3 pr-4 font-medium">{t("ops.guardrails.colActions") || "Actions"}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {items.map((v) => (
                        <tr key={v.id} className="align-top">
                          <td className="py-3 pr-4 font-mono text-xs">{v.guardrail_id}</td>
                          <td className="py-3 pr-4">{severityBadge(v.severity)}</td>
                          <td className="py-3 pr-4 max-w-xs">
                            <button
                              onClick={() => toggleExpand(v.id)}
                              className="flex items-center gap-1 text-left text-muted-foreground hover:text-foreground"
                            >
                              {expandedIds.has(v.id) ? (
                                <ChevronUp className="h-4 w-4 shrink-0" />
                              ) : (
                                <ChevronDown className="h-4 w-4 shrink-0" />
                              )}
                              <span className="block truncate font-mono text-xs">
                                {v.diff_excerpt.split("\n")[0]}
                              </span>
                            </button>
                            <AnimatePresence>
                              {expandedIds.has(v.id) && (
                                <motion.div
                                  initial={{ height: 0, opacity: 0 }}
                                  animate={{ height: "auto", opacity: 1 }}
                                  exit={{ height: 0, opacity: 0 }}
                                  transition={{ duration: 0.2 }}
                                  className="overflow-hidden"
                                >
                                  <pre className="mt-2 rounded-md border bg-accent/50 p-3 font-mono text-xs leading-relaxed">
                                    {v.diff_excerpt}
                                  </pre>
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </td>
                          <td className="py-3 pr-4">
                            {v.issue_id ? (
                              <a
                                href={`/admin/ops/tickets`}
                                className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                              >
                                {v.issue_id}
                                <ExternalLink className="h-3 w-3" />
                              </a>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </td>
                          <td className="py-3 pr-4">
                            <Badge variant={v.resolved ? "success" : "default"}>
                              {v.resolved
                                ? t("ops.guardrails.resolved") || "Resolved"
                                : t("ops.guardrails.active") || "Active"}
                            </Badge>
                          </td>
                          <td className="py-3 pr-4">
                            {!v.resolved && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => resolveGuardrail.mutate(v.id)}
                                disabled={resolveGuardrail.isPending}
                              >
                                <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                                {t("ops.guardrails.resolve") || "Resolve"}
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
