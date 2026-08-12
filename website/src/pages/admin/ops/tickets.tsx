import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion, AnimatePresence } from "motion/react"
import {
  Ticket,
  X,
  Filter,
  Paperclip,
  Clock,
  User,
  AlertTriangle,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tooltip } from "@/components/ui/tooltip"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { useOpsTickets, useOpsTicket } from "@/services/queries"

const riskFilterOptions = ["all", "low", "medium", "high", "critical"] as const
const statusFilterOptions = ["all", "open", "in_progress", "resolved", "closed"] as const

export default function OpsTicketsPage() {
  const { t } = useLocale()
  const [riskFilter, setRiskFilter] = useState<string>("all")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: tickets, isLoading, isError } = useOpsTickets(
    riskFilter !== "all" || statusFilter !== "all"
      ? {
          ...(riskFilter !== "all" && { risk_tier: riskFilter }),
          ...(statusFilter !== "all" && { status: statusFilter }),
        }
      : undefined
  )
  const { data: detail, isLoading: detailLoading } = useOpsTicket(selectedId ?? "")

  const filteredTickets = tickets ?? []

  const riskBadge = (risk: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline" | "success"> = {
      low: "secondary",
      medium: "default",
      high: "destructive",
      critical: "destructive",
    }
    const labels: Record<string, string> = {
      low: t("ops.tickets.riskLow") || "Low",
      medium: t("ops.tickets.riskMedium") || "Medium",
      high: t("ops.tickets.riskHigh") || "High",
      critical: t("ops.tickets.riskCritical") || "Critical",
    }
    return <Badge variant={variants[risk] || "default"}>{labels[risk] || risk}</Badge>
  }

  const statusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline" | "success"> = {
      open: "default",
      in_progress: "secondary",
      resolved: "success",
      closed: "outline",
    }
    return <Badge variant={variants[status] || "default"}>{status.replace("_", " ")}</Badge>
  }

  const formatDate = (iso: string) => new Date(iso).toLocaleDateString()

  return (
    <>
      <Helmet>
        <title>{t("ops.tickets.pageTitle") || "Tickets — Operion Ops"}</title>
      </Helmet>

      <SectionWrapper className="pt-0">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Ticket className="h-5 w-5" />
                    {t("ops.tickets.title") || "Tickets"}
                  </CardTitle>
                  <CardDescription>{t("ops.tickets.description") || "Review and manage incoming issue tickets."}</CardDescription>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <Filter className="h-4 w-4 text-muted-foreground" />
                    <select
                      value={riskFilter}
                      onChange={(e) => setRiskFilter(e.target.value)}
                      className="h-8 rounded-md border border-input bg-transparent px-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    >
                      {riskFilterOptions.map((r) => (
                        <option key={r} value={r}>
                          {r === "all"
                            ? t("ops.tickets.allRisks") || "All risks"
                            : r.replace("_", " ").replace(/^\w/, (c) => c.toUpperCase())}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center gap-2">
                    <Filter className="h-4 w-4 text-muted-foreground" />
                    <select
                      value={statusFilter}
                      onChange={(e) => setStatusFilter(e.target.value)}
                      className="h-8 rounded-md border border-input bg-transparent px-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    >
                      {statusFilterOptions.map((s) => (
                        <option key={s} value={s}>
                          {s === "all"
                            ? t("ops.tickets.allStatuses") || "All statuses"
                            : s.replace("_", " ").replace(/^\w/, (c) => c.toUpperCase())}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex justify-center py-12">
                  <LoadingSpinner size="lg" />
                </div>
              ) : isError ? (
                <EmptyState
                  title={t("common.error") || "Error"}
                  description={t("ops.tickets.loadError") || "Failed to load tickets. Please try again later."}
                  icon={<AlertTriangle className="h-16 w-16" />}
                />
              ) : filteredTickets.length === 0 ? (
                <EmptyState
                  title={t("ops.tickets.noTickets") || "No tickets found"}
                  description={t("ops.tickets.noTicketsDesc") || "No tickets match the selected filters."}
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="py-3 pr-4 font-medium">{t("ops.tickets.colId") || "ID"}</th>
                        <th className="py-3 pr-4 font-medium">{t("ops.tickets.colSummary") || "Summary"}</th>
                        <th className="py-3 pr-4 font-medium">{t("ops.tickets.colRisk") || "Risk"}</th>
                        <th className="py-3 pr-4 font-medium">{t("ops.tickets.colStatus") || "Status"}</th>
                        <th className="py-3 pr-4 font-medium">{t("ops.tickets.colCustomer") || "Customer"}</th>
                        <th className="py-3 pr-4 font-medium">{t("ops.tickets.colCreated") || "Created"}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {filteredTickets.map((ticket) => (
                        <tr
                          key={ticket.issue_id}
                          className="cursor-pointer transition-colors hover:bg-accent/50"
                          onClick={() => setSelectedId(ticket.issue_id)}
                        >
                          <td className="py-3 pr-4 font-mono text-xs">{ticket.issue_id}</td>
                          <td className="py-3 pr-4 max-w-xs">
                            <Tooltip content={ticket.summary} side="top">
                              <span className="block truncate">{ticket.summary}</span>
                            </Tooltip>
                          </td>
                          <td className="py-3 pr-4">{riskBadge(ticket.risk_tier)}</td>
                          <td className="py-3 pr-4">{statusBadge(ticket.status)}</td>
                          <td className="py-3 pr-4 font-mono text-xs">{ticket.company_id || "—"}</td>
                          <td className="py-3 pr-4 text-muted-foreground">{formatDate(ticket.created_at)}</td>
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

      {/* Slide-over detail panel */}
      <AnimatePresence>
        {selectedId && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/40"
            onClick={() => setSelectedId(null)}
          >
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 300 }}
              className="absolute right-0 top-0 h-full w-full max-w-lg overflow-y-auto border-l bg-background shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              {detailLoading ? (
                <div className="flex justify-center py-12">
                  <LoadingSpinner size="lg" />
                </div>
              ) : detail ? (
                <>
                  <div className="flex items-center justify-between border-b p-4">
                    <h2 className="text-lg font-semibold">{detail.issue_id}</h2>
                    <Button variant="ghost" size="icon" onClick={() => setSelectedId(null)}>
                      <X className="h-4 w-4" />
                    </Button>
                  </div>

                  <div className="space-y-6 p-4">
                    <div className="flex items-center gap-2">
                      {riskBadge(detail.risk_tier)}
                      {statusBadge(detail.status)}
                    </div>

                    <div>
                      <h3 className="text-sm font-medium text-muted-foreground">{t("ops.tickets.detailSummary") || "Summary"}</h3>
                      <p className="mt-1 text-sm">{detail.summary}</p>
                    </div>

                    {detail.reproduction_steps && detail.reproduction_steps.length > 0 && (
                      <div>
                        <h3 className="text-sm font-medium text-muted-foreground">{t("ops.tickets.reproductionSteps") || "Reproduction steps"}</h3>
                        <ol className="mt-1 list-inside list-decimal space-y-1 text-sm">
                          {detail.reproduction_steps.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    )}

                    {detail.logs && (
                      <div>
                        <h3 className="text-sm font-medium text-muted-foreground">{t("ops.tickets.logs") || "Logs"}</h3>
                        <pre className="mt-1 max-h-48 overflow-auto rounded-md border bg-accent/50 p-3 font-mono text-xs leading-relaxed">
                          {detail.logs}
                        </pre>
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">{t("ops.tickets.detailCustomer") || "Customer"}:</span>
                        <span className="font-mono">{detail.customer_id}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">{t("ops.tickets.detailCreated") || "Created"}:</span>
                        <span>{formatDate(detail.created_at)}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">{t("ops.tickets.environment") || "Environment"}:</span>
                        <span>{detail.environment}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">{t("ops.tickets.appVersion") || "App version"}:</span>
                        <span>{detail.app_version}</span>
                      </div>
                    </div>

                    {detail.suspected_module && (
                      <div>
                        <h3 className="text-sm font-medium text-muted-foreground">{t("ops.tickets.suspectedModule") || "Suspected module"}</h3>
                        <p className="mt-1 text-sm font-mono">{detail.suspected_module}</p>
                      </div>
                    )}

                    {detail.linked_known_issue_id && (
                      <div className="rounded-md border bg-accent/50 p-3">
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <AlertTriangle className="h-4 w-4 text-amber-600" />
                          {t("ops.tickets.linkedKnownIssue") || "Linked known issue"}
                        </div>
                        <p className="mt-1 text-sm">
                          {detail.linked_known_issue_id}
                        </p>
                      </div>
                    )}

                    {detail.confidence_at_escalation !== null && (
                      <div>
                        <h3 className="text-sm font-medium text-muted-foreground">{t("ops.tickets.confidence") || "Confidence at escalation"}</h3>
                        <p className="mt-1 text-sm">{(detail.confidence_at_escalation * 100).toFixed(0)}%</p>
                      </div>
                    )}

                    {detail.attachments && detail.attachments.length > 0 && (
                      <div>
                        <h3 className="text-sm font-medium text-muted-foreground">{t("ops.tickets.attachments") || "Attachments"}</h3>
                        <div className="mt-3 space-y-2">
                          {detail.attachments.map((att: any, i: number) => (
                            <div
                              key={i}
                              className="flex items-center justify-between rounded-md border p-3"
                            >
                              <div className="flex items-center gap-3">
                                <Paperclip className="h-4 w-4 text-muted-foreground" />
                                <div>
                                  <p className="text-sm font-medium">{att.name || att.filename || `Attachment ${i + 1}`}</p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="flex justify-center py-12">
                  <p className="text-sm text-muted-foreground">{t("common.error") || "Failed to load ticket details."}</p>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
