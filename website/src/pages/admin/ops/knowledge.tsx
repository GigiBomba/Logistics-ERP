import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion, AnimatePresence } from "motion/react"
import {
  BookOpen,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { useOpsKnowledgeDrafts, useOpsApproveKnowledgeDoc, useOpsRejectKnowledgeDoc } from "@/services/queries"

export default function OpsKnowledgePage() {
  const { t } = useLocale()
  const { data: drafts, isLoading, isError } = useOpsKnowledgeDrafts()
  const approveDoc = useOpsApproveKnowledgeDoc()
  const rejectDoc = useOpsRejectKnowledgeDoc()
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  const items = drafts ?? []

  const toggleExpand = (id: number) => {
    const next = new Set(expandedIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setExpandedIds(next)
  }

  const corpusBadge = (corpus: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline" | "success"> = {
      internal: "secondary",
      public: "default",
    }
    return <Badge variant={variants[corpus] || "default"}>{corpus}</Badge>
  }

  const statusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline" | "success"> = {
      pending: "default",
      approved: "success",
      rejected: "destructive",
    }
    return <Badge variant={variants[status] || "outline"}>{status}</Badge>
  }

  if (isLoading) {
    return (
      <>
        <Helmet>
          <title>{t("ops.knowledge.pageTitle") || "Knowledge — Operion Ops"}</title>
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
          <title>{t("ops.knowledge.pageTitle") || "Knowledge — Operion Ops"}</title>
        </Helmet>
        <SectionWrapper className="pt-0">
          <EmptyState
            title={t("common.error") || "Error"}
            description={t("ops.knowledge.loadError") || "Failed to load knowledge drafts. Please try again later."}
            icon={<AlertTriangle className="h-16 w-16" />}
          />
        </SectionWrapper>
      </>
    )
  }

  return (
    <>
      <Helmet>
        <title>{t("ops.knowledge.pageTitle") || "Knowledge — Operion Ops"}</title>
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
                <BookOpen className="h-5 w-5" />
                {t("ops.knowledge.title") || "Knowledge drafts"}
              </CardTitle>
              <CardDescription>
                {t("ops.knowledge.description") || "Review, edit, and approve pending knowledge base drafts."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {items.length === 0 ? (
                <EmptyState
                  title={t("ops.knowledge.noDrafts") || "No pending drafts"}
                  description={t("ops.knowledge.noDraftsDesc") || "All knowledge drafts have been reviewed."}
                />
              ) : (
                <div className="space-y-4">
                  {items.map((draft) => (
                    <div
                      key={draft.id}
                      className="rounded-lg border p-4 transition-colors hover:bg-accent/30"
                    >
                      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-semibold">{draft.doc_id || `Draft #${draft.id}`}</h3>
                            {corpusBadge(draft.corpus)}
                            {statusBadge(draft.status)}
                          </div>
                          {draft.section && (
                            <p className="text-xs text-muted-foreground">
                              {t("ops.knowledge.section") || "Section"}: {draft.section}
                            </p>
                          )}
                          <p className="text-xs text-muted-foreground font-mono">ID: {draft.id}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {draft.status === "pending" && (
                            <>
                              <Button
                                variant="default"
                                size="sm"
                                onClick={() => approveDoc.mutate(String(draft.id))}
                                disabled={approveDoc.isPending || rejectDoc.isPending}
                              >
                                <CheckCircle2 className="mr-1 h-4 w-4" />
                                {t("ops.knowledge.approve") || "Approve"}
                              </Button>
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => rejectDoc.mutate(String(draft.id))}
                                disabled={approveDoc.isPending || rejectDoc.isPending}
                              >
                                <XCircle className="mr-1 h-4 w-4" />
                                {t("ops.knowledge.reject") || "Reject"}
                              </Button>
                            </>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleExpand(draft.id)}
                          >
                            {expandedIds.has(draft.id) ? (
                              <>
                                <ChevronUp className="mr-1 h-4 w-4" />
                                {t("common.showLess") || "Show less"}
                              </>
                            ) : (
                              <>
                                <ChevronDown className="mr-1 h-4 w-4" />
                                {t("common.showMore") || "Show more"}
                              </>
                            )}
                          </Button>
                        </div>
                      </div>

                      <AnimatePresence>
                        {expandedIds.has(draft.id) && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                              {draft.content}
                            </p>
                            <p className="mt-3 text-xs text-muted-foreground">
                              {t("ops.knowledge.lastUpdated") || "Last updated"}: {new Date(draft.last_updated).toLocaleString()}
                            </p>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
