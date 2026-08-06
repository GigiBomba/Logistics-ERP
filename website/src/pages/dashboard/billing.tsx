import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import {
  Clock,
  Mail,
  FileText,
  Download,
  CreditCard,
  AlertCircle,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Receipt,
  Building2,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CopyButton } from "@/components/ui/copy-button"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { Callout } from "@/components/ui/callout"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import { useInvoices } from "@/services/queries"
import { formatDate, formatCurrency } from "@/lib/utils"
import type { InvoiceStatus } from "@/types"

const STATUS_BADGE: Record<InvoiceStatus, "success" | "default" | "secondary" | "outline"> = {
  paid: "success",
  open: "default",
  void: "secondary",
  draft: "outline",
}

const STATUS_ICONS: Record<InvoiceStatus, typeof CheckCircle2> = {
  paid: CheckCircle2,
  open: Clock,
  void: XCircle,
  draft: FileText,
}

export default function BillingPage() {
  const { t } = useLocale()
  const { data: invoices, isLoading, isError, error, refetch } = useInvoices()

  return (
    <>
      <Helmet>
        <title>{t("billing.pageTitle")}</title>
      </Helmet>

      <SectionWrapper>
        {/* Page Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">{t("billing.heading")}</h1>
              <p className="mt-2 text-muted-foreground">
                {t("billing.description")}
              </p>
            </div>
          </div>
        </motion.div>

        <div className="mt-8 grid gap-8 lg:grid-cols-3">
          {/* ── Main content ── */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="lg:col-span-2 space-y-6"
          >
            {/* ── Loading state ── */}
            {isLoading && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Receipt className="h-5 w-5" />
                    {t("billing.invoices")}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Skeleton className="h-12 w-full rounded-lg" />
                  <Skeleton className="h-12 w-full rounded-lg" />
                  <Skeleton className="h-12 w-full rounded-lg" />
                </CardContent>
              </Card>
            )}

            {/* ── Error state ── */}
            {isError && !isLoading && (
              <Card className="border-destructive/30">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <AlertCircle className="h-5 w-5 text-destructive" />
                    {t("billing.invoices")}
                  </CardTitle>
                  <CardDescription>{t("billing.description")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Callout variant="danger" title={t("billing.unableToLoadInvoices")}>
                    <p className="text-sm">
                      {error instanceof Error ? error.message : t("billing.unexpectedError")}
                      {" "}{t("billing.apiMayNotBeAvailable")}
                    </p>
                  </Callout>

                  <div className="flex flex-wrap gap-3">
                    <Button variant="default" onClick={() => refetch()}>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      {t("common.retry")}
                    </Button>
                    <Button variant="outline" asChild>
                      <a href="mailto:support@operionerp.xyz">
                        <Mail className="mr-2 h-4 w-4" />
                        {t("billing.contactSupport")}
                      </a>
                    </Button>
                  </div>

                  <Separator />

                  <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
                    <p className="font-medium text-foreground mb-2">{t("billing.apiNotYetAvailable")}</p>
                    <p>
                      {t("billing.backendUnderDevelopment")}
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* ── Invoice History ── */}
            {!isLoading && !isError && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Receipt className="h-5 w-5" />
                    {t("billing.invoiceHistory")}
                  </CardTitle>
                  <CardDescription>{t("billing.invoiceHistoryDesc")}</CardDescription>
                </CardHeader>
                <CardContent>
                  {!invoices || invoices.length === 0 ? (
                    <EmptyState
                      title={t("billing.noInvoices")}
                      description={t("billing.noInvoicesDesc")}
                      icon={<FileText className="h-12 w-12" />}
                    />
                  ) : (
                    <div className="divide-y">
                      {invoices.map((invoice) => {
                        const StatusIcon = STATUS_ICONS[invoice.status]
                        return (
                          <div
                            key={invoice.id}
                            className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
                          >
                            <div className="flex items-start gap-3 min-w-0">
                              <StatusIcon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                              <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                  <p className="text-sm font-medium truncate">
                                    {invoice.number}
                                  </p>
                                  <CopyButton
                                    text={invoice.number}
                                    aria-label={`Copy invoice number ${invoice.number}`}
                                    className="h-6 px-2 py-0"
                                  />
                                </div>
                                <p className="text-xs text-muted-foreground">
                                  {t("billing.issued")}: {formatDate(invoice.issued_at)}
                                  {invoice.due_at && (
                                    <> &middot; {t("billing.due")}: {formatDate(invoice.due_at)}</>
                                  )}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-3 shrink-0 ml-4">
                              <div className="text-right">
                                <p className="text-sm font-medium">
                                  {formatCurrency(invoice.amount, invoice.currency)}
                                </p>
                                <Badge variant={STATUS_BADGE[invoice.status]}>
                                  <StatusIcon className="mr-1 h-3 w-3 inline" />
                                  {invoice.status}
                                </Badge>
                              </div>
                              {invoice.pdf_url && (
                                <Button variant="ghost" size="icon" asChild>
                                  <a
                                    href={invoice.pdf_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    aria-label={`Download ${invoice.number}`}
                                  >
                                    <Download className="h-4 w-4" />
                                  </a>
                                </Button>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* ── Payment Methods (placeholder) ── */}
            {!isLoading && !isError && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <CreditCard className="h-5 w-5" />
                    {t("billing.paymentMethods")}
                  </CardTitle>
                  <CardDescription>{t("billing.paymentMethodsDesc")}</CardDescription>
                </CardHeader>
                <CardContent>
                  <EmptyState
                    title={t("billing.noPaymentMethods")}
                    description={t("billing.noPaymentMethodsDesc")}
                    icon={<CreditCard className="h-12 w-12" />}
                  />
                </CardContent>
              </Card>
            )}
          </motion.div>

          {/* ── Sidebar ── */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 }}
            className="space-y-6"
          >
            {/* Billing summary card */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t("billing.overview")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {isLoading ? (
                  <>
                    <Skeleton className="h-5 w-full" />
                    <Skeleton className="h-5 w-3/4" />
                    <Skeleton className="h-5 w-1/2" />
                  </>
                ) : isError ? (
                  <p className="text-sm text-muted-foreground">
                    Billing overview unavailable.
                  </p>
                ) : (
                  <>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("billing.invoices")}</span>
                      <span className="font-medium">
                        {invoices?.length ?? 0} total
                      </span>
                    </div>
                    <Separator />
                    <Button variant="outline" className="w-full" asChild>
                      <a href="/dashboard/subscription">
                        <Building2 className="mr-2 h-4 w-4" />
                        {t("billing.viewInSubscription")}
                      </a>
                    </Button>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Tax info placeholder */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t("billing.taxInfo")}</CardTitle>
                <CardDescription>{t("billing.taxInfoDesc")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">{t("billing.vatId")}</label>
                  <p className="text-sm text-muted-foreground italic">—</p>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">{t("billing.billingAddress")}</label>
                  <p className="text-sm text-muted-foreground italic">—</p>
                </div>
                <p className="text-xs text-muted-foreground">
                  Tax configuration will be available in a future update.
                </p>
              </CardContent>
            </Card>

            {/* Contact */}
            <Card>
              <CardContent className="pt-6">
                <Button variant="outline" className="w-full" asChild>
                  <a href="mailto:support@operionerp.xyz">
                    <Mail className="mr-2 h-4 w-4" />
                    Contact Support
                  </a>
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>
    </>
  )
}
