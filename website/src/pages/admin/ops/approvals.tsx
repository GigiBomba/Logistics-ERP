import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion, AnimatePresence } from "motion/react"
import {
  FileCode2,
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertTriangle,
  GitPullRequest,
  TestTube2,
  ShieldCheck,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { useOpsApprovals, useOpsHandleApproval } from "@/services/queries"

export default function OpsApprovalsPage() {
  const { t } = useLocale()
  const { data: approvals, isLoading, isError } = useOpsApprovals()
  const handleApproval = useOpsHandleApproval()
  const [confirmAction, setConfirmAction] = useState<{ id: string; action: "approve" | "reject" } | null>(null)

  const items = approvals ?? []

  const riskBadge = (risk: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline" | "success"> = {
      low: "secondary",
      medium: "default",
      high: "destructive",
      critical: "destructive",
    }
    return <Badge variant={variants[risk] || "default"}>{risk}</Badge>
  }

  const handleConfirm = () => {
    if (!confirmAction) return
    handleApproval.mutate({ id: confirmAction.id, action: confirmAction.action })
    setConfirmAction(null)
  }

  if (isLoading) {
    return (
      <>
        <Helmet>
          <title>{t("ops.approvals.pageTitle") || "Approvals — Operion Ops"}</title>
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
          <title>{t("ops.approvals.pageTitle") || "Approvals — Operion Ops"}</title>
        </Helmet>
        <SectionWrapper className="pt-0">
          <EmptyState
            title={t("common.error") || "Error"}
            description={t("ops.approvals.loadError") || "Failed to load approvals. Please try again later."}
            icon={<AlertTriangle className="h-16 w-16" />}
          />
        </SectionWrapper>
      </>
    )
  }

  return (
    <>
      <Helmet>
        <title>{t("ops.approvals.pageTitle") || "Approvals — Operion Ops"}</title>
      </Helmet>

      <SectionWrapper className="pt-0">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="space-y-6"
        >
          {items.length === 0 ? (
            <EmptyState
              title={t("ops.approvals.noItems") || "No pending approvals"}
              description={t("ops.approvals.noItemsDesc") || "All changes have been reviewed."}
            />
          ) : (
            items.map((item) => (
              <Card key={item.issue_id} className="overflow-hidden">
                <CardHeader>
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <GitPullRequest className="h-5 w-5 text-muted-foreground" />
                        <CardTitle className="text-base">{item.summary}</CardTitle>
                      </div>
                      <CardDescription className="flex flex-wrap items-center gap-3">
                        <span className="font-mono text-xs">{item.issue_id}</span>
                        {riskBadge(item.risk_tier)}
                        {item.status !== "pending" && (
                          <Badge variant="outline">{item.status}</Badge>
                        )}
                        {item.has_elevated_scrutiny && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-200">
                            <AlertTriangle className="h-3 w-3" />
                            {t("ops.approvals.elevatedScrutiny") || "Elevated scrutiny"}
                          </span>
                        )}
                      </CardDescription>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <FileCode2 className="h-4 w-4" />
                        {item.files_changed} {t("ops.approvals.filesChanged") || "files"}
                      </div>
                      <div className="flex items-center gap-1">
                        <TestTube2 className="h-4 w-4" />
                        {item.tests_passed} {t("ops.approvals.tests") || "tests passed"}
                      </div>
                      <div className="flex items-center gap-1">
                        <ShieldCheck className="h-4 w-4" />
                        {item.invariants_passed} {t("ops.approvals.invariants") || "invariants checked"}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 pt-4">
                    <Button
                      variant="default"
                      className="bg-green-600 text-white hover:bg-green-700"
                      onClick={() => setConfirmAction({ id: item.issue_id, action: "approve" })}
                      disabled={handleApproval.isPending}
                    >
                      <CheckCircle2 className="mr-1 h-4 w-4" />
                      {t("ops.approvals.approve") || "Approve"}
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => setConfirmAction({ id: item.issue_id, action: "reject" })}
                      disabled={handleApproval.isPending}
                    >
                      <XCircle className="mr-1 h-4 w-4" />
                      {t("ops.approvals.reject") || "Reject"}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => handleApproval.mutate({ id: item.issue_id, action: "ask_question" })}
                      disabled={handleApproval.isPending}
                    >
                      <HelpCircle className="mr-1 h-4 w-4" />
                      {t("ops.approvals.askQuestion") || "Ask a question"}
                    </Button>
                  </div>
                </CardHeader>
              </Card>
            ))
          )}
        </motion.div>
      </SectionWrapper>

      {/* Confirmation dialog */}
      <AnimatePresence>
        {confirmAction && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
            onClick={() => setConfirmAction(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="w-full max-w-md rounded-xl border bg-background p-6 shadow-lg"
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className="text-lg font-semibold">
                {confirmAction.action === "approve"
                  ? t("ops.approvals.confirmApproveTitle") || "Approve this change?"
                  : t("ops.approvals.confirmRejectTitle") || "Reject this change?"}
              </h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {confirmAction.action === "approve"
                  ? t("ops.approvals.confirmApproveDesc") || "This will approve the change and update the review status."
                  : t("ops.approvals.confirmRejectDesc") || "This will reject the change and notify the author."}
              </p>
              <div className="mt-6 flex justify-end gap-2">
                <Button variant="outline" onClick={() => setConfirmAction(null)}>
                  {t("common.cancel") || "Cancel"}
                </Button>
                <Button
                  variant={confirmAction.action === "approve" ? "default" : "destructive"}
                  onClick={handleConfirm}
                  disabled={handleApproval.isPending}
                >
                  {handleApproval.isPending ? (
                    <LoadingSpinner size="sm" className="mr-2" />
                  ) : confirmAction.action === "approve" ? (
                    t("ops.approvals.confirmApprove") || "Yes, approve"
                  ) : (
                    t("ops.approvals.confirmReject") || "Yes, reject"
                  )}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
