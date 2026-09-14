import { useState, type FormEvent } from "react"
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
  Plus,
  Trash2,
  Loader2,
  X,
  Pencil,
} from "lucide-react"
import { Elements, PaymentElement, useStripe, useElements } from "@stripe/react-stripe-js"
import { loadStripe } from "@stripe/stripe-js"
import { toast } from "sonner"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { CopyButton } from "@/components/ui/copy-button"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { Callout } from "@/components/ui/callout"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import { envConfig } from "@/config/env"
import {
  useInvoices,
  usePaymentMethods,
  useSetupIntent,
  useRemovePaymentMethod,
  useCompany,
  useUpdateCompany,
} from "@/services/queries"
import { formatDate, formatCurrency } from "@/lib/utils"
import type { PaymentMethod } from "@/api/endpoints"
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

/** Stripe.js loader — null when no publishable key is configured. */
const stripePromise = envConfig.stripePublishableKey
  ? loadStripe(envConfig.stripePublishableKey)
  : null

/* ─── Inline lightweight modal (no Dialog component in UI kit) ─── */
function InlineModal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
}) {
  const { t } = useLocale()
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="billing-modal-title"
    >
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        transition={{ duration: 0.15 }}
        className="relative w-full max-w-md rounded-xl border bg-card p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 id="billing-modal-title" className="text-lg font-semibold">
            {title}
          </h3>
          <button
            onClick={onClose}
            className="rounded-md p-1 hover:bg-muted"
            aria-label={t("common.close")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {children}
      </motion.div>
    </div>
  )
}

/* ─── Stripe PaymentElement form ─── */
function AddCardForm({
  onSuccess,
  onCancel,
}: {
  onSuccess: () => void
  onCancel: () => void
}) {
  const { t } = useLocale()
  const stripe = useStripe()
  const elements = useElements()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!stripe || !elements) return
    setSubmitting(true)
    setError(null)
    const { error: stripeError } = await stripe.confirmSetup({
      elements,
      redirect: "if_required",
    })
    setSubmitting(false)
    if (stripeError) {
      setError(stripeError.message ?? t("billing.addCardFailed"))
      return
    }
    onSuccess()
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <PaymentElement />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex justify-end gap-3">
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
        <Button type="submit" size="sm" isLoading={submitting} disabled={!stripe || !elements}>
          {t("billing.addCard")}
        </Button>
      </div>
    </form>
  )
}

export default function BillingPage() {
  const { t } = useLocale()
  const { data: invoices, isLoading, isError, error, refetch } = useInvoices()
  const {
    data: paymentMethods,
    isLoading: paymentMethodsLoading,
    refetch: refetchPaymentMethods,
  } = usePaymentMethods()
  const setupIntent = useSetupIntent()
  const removePaymentMethod = useRemovePaymentMethod()
  const { data: company } = useCompany()
  const updateCompany = useUpdateCompany()

  const [addCardOpen, setAddCardOpen] = useState(false)
  const [clientSecret, setClientSecret] = useState<string | null>(null)
  const [removeTarget, setRemoveTarget] = useState<PaymentMethod | null>(null)
  const [editingVat, setEditingVat] = useState(false)
  const [vatInput, setVatInput] = useState("")

  const paymentMethodList = paymentMethods?.payment_methods ?? []
  const hasPaymentMethods = paymentMethodList.length > 0

  const closeAddCard = () => {
    setAddCardOpen(false)
    setClientSecret(null)
  }

  const handleOpenAddCard = () => {
    if (!stripePromise) {
      toast.error(t("billing.stripeNotConfigured"))
      return
    }
    setClientSecret(null)
    setAddCardOpen(true)
    setupIntent.mutate(undefined, {
      onSuccess: (secret) => setClientSecret(secret),
      onError: () => {
        closeAddCard()
        toast.error(t("billing.setupIntentFailed"))
      },
    })
  }

  const handleCardAdded = () => {
    closeAddCard()
    toast.success(t("billing.cardAdded"))
    refetchPaymentMethods()
  }

  const handleRemoveCard = () => {
    if (!removeTarget) return
    removePaymentMethod.mutate(removeTarget.id, {
      onSuccess: () => {
        toast.success(t("billing.cardRemoved"))
        setRemoveTarget(null)
      },
      onError: () => toast.error(t("billing.removeCardFailed")),
    })
  }

  const startEditVat = () => {
    setVatInput(company?.vat_number ?? "")
    setEditingVat(true)
  }

  const handleSaveVat = () => {
    updateCompany.mutate(
      { vat_number: vatInput },
      {
        onSuccess: () => {
          toast.success(t("billing.vatSaved"))
          setEditingVat(false)
        },
        onError: () => toast.error(t("billing.vatSaveFailed")),
      }
    )
  }

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

            {/* ── Payment Methods ── */}
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1.5">
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <CreditCard className="h-5 w-5" />
                      {t("billing.paymentMethods")}
                    </CardTitle>
                    <CardDescription>{t("billing.paymentMethodsDesc")}</CardDescription>
                  </div>
                  {hasPaymentMethods && (
                    <Button size="sm" onClick={handleOpenAddCard}>
                      <Plus className="mr-1 h-4 w-4" />
                      {t("billing.addCard")}
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {paymentMethodsLoading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-16 w-full rounded-lg" />
                    <Skeleton className="h-16 w-full rounded-lg" />
                  </div>
                ) : hasPaymentMethods ? (
                  <div className="space-y-3">
                    {paymentMethodList.map((pm) => (
                      <div
                        key={pm.id}
                        className="flex items-center justify-between rounded-lg border p-3"
                      >
                        <div className="flex items-center gap-3">
                          <CreditCard className="h-4 w-4 shrink-0 text-muted-foreground" />
                          <div>
                            <p className="text-sm font-medium capitalize">
                              {pm.card.brand} •••• {pm.card.last4}
                              {pm.is_default && (
                                <Badge variant="secondary" className="ml-2">
                                  {t("billing.default")}
                                </Badge>
                              )}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {t("billing.expires")} {String(pm.card.exp_month).padStart(2, "0")}/
                              {pm.card.exp_year}
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`${t("billing.removeCard")} ${pm.card.brand} ${pm.card.last4}`}
                          onClick={() => setRemoveTarget(pm)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title={t("billing.noPaymentMethods")}
                    description={t("billing.noPaymentMethodsHint")}
                    icon={<CreditCard className="h-12 w-12" />}
                    action={
                      <Button onClick={handleOpenAddCard}>
                        <Plus className="mr-2 h-4 w-4" />
                        {t("billing.addCard")}
                      </Button>
                    }
                  />
                )}
              </CardContent>
            </Card>
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

            {/* Tax info */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t("billing.taxInfo")}</CardTitle>
                <CardDescription>{t("billing.taxInfoDesc")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1">
                  <label htmlFor="billing-vat" className="text-xs text-muted-foreground">
                    {t("billing.vatId")}
                  </label>
                  {editingVat ? (
                    <div className="flex items-center gap-2">
                      <Input
                        id="billing-vat"
                        value={vatInput}
                        onChange={(e) => setVatInput(e.target.value)}
                        placeholder={t("billing.vatPlaceholder")}
                      />
                      <Button
                        size="sm"
                        onClick={handleSaveVat}
                        isLoading={updateCompany.isPending}
                      >
                        {t("common.save")}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditingVat(false)}
                        disabled={updateCompany.isPending}
                      >
                        {t("common.cancel")}
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between gap-2">
                      <p className={company?.vat_number ? "text-sm font-medium" : "text-sm text-muted-foreground italic"}>
                        {company?.vat_number || "—"}
                      </p>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={t("billing.editVat")}
                        onClick={startEditVat}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">{t("billing.billingAddress")}</label>
                  <p className="text-sm text-muted-foreground">
                    {[company?.address, company?.city, company?.country]
                      .filter(Boolean)
                      .join(", ") || "—"}
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Contact */}
            <Card>
              <CardContent className="pt-6">
                <Button variant="outline" className="w-full" asChild>
                  <a href="mailto:support@operionerp.xyz">
                    <Mail className="mr-2 h-4 w-4" />
                    {t("billing.contactSupport")}
                  </a>
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>

      {/* ── Add card modal ── */}
      <InlineModal open={addCardOpen} onClose={closeAddCard} title={t("billing.addCardTitle")}>
        {!clientSecret ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : stripePromise ? (
          <Elements stripe={stripePromise} options={{ clientSecret }}>
            <AddCardForm onSuccess={handleCardAdded} onCancel={closeAddCard} />
          </Elements>
        ) : (
          <p className="text-sm text-muted-foreground">{t("billing.stripeNotConfigured")}</p>
        )}
      </InlineModal>

      {/* ── Remove card confirmation modal ── */}
      <InlineModal
        open={!!removeTarget}
        onClose={() => setRemoveTarget(null)}
        title={t("billing.confirmRemoveCard")}
      >
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {t("billing.confirmRemoveCardDesc")}
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="outline" size="sm" onClick={() => setRemoveTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleRemoveCard}
              isLoading={removePaymentMethod.isPending}
            >
              {t("billing.removeCard")}
            </Button>
          </div>
        </div>
      </InlineModal>
    </>
  )
}
