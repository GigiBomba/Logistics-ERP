import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion, AnimatePresence } from "motion/react"
import {
  CreditCard,
  Truck,
  Shield,
  Mail,
  ArrowUpRight,
  AlertCircle,
  RefreshCw,
  Calendar,
  CheckCircle2,
  XCircle,
  Clock,
  Zap,
  Headphones,
  Code2,
  Loader2,
  ChevronRight,
  X,
  Info,
  ExternalLink,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Callout } from "@/components/ui/callout"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import {
  useSubscription,
  useCreatePortalSession,
  useCreateCheckoutSession,
  useUpdateBillingTerm,
  useToggleAddon,
  useCancelSubscription,
  useReactivateSubscription,
} from "@/services/queries"
import { trackEvent } from "@/services/analytics"
import { formatDate, formatCurrency } from "@/lib/utils"
import { getTrialState, daysLeftInTrial } from "@/lib/trial"
import { toast } from "sonner"
import type { SubscriptionStatus } from "@/types"

const STATUS_VARIANTS: Record<SubscriptionStatus, "default" | "success" | "destructive" | "secondary" | "outline"> = {
  active: "success",
  trialing: "default",
  past_due: "destructive",
  payment_deferred: "secondary",
  canceled: "secondary",
  locked: "outline",
}

const STATUS_ICONS: Record<SubscriptionStatus, typeof CheckCircle2> = {
  active: CheckCircle2,
  trialing: Clock,
  past_due: AlertCircle,
  payment_deferred: Clock,
  canceled: XCircle,
  locked: XCircle,
}

/* ─── Inline lightweight modal (no Dialog component in UI kit) ─── */
function InlineModal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  const { t } = useLocale()
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        transition={{ duration: 0.15 }}
        className="relative w-full max-w-md rounded-xl border bg-card p-6 shadow-xl"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 id="modal-title" className="text-lg font-semibold">{title}</h3>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-muted" aria-label={t("common.close")}>
            <X className="h-4 w-4" />
          </button>
        </div>
        {children}
      </motion.div>
    </div>
  )
}

/* ─── Inline toggle switch ─── */
function ToggleSwitch({ checked, onChange, disabled, ariaLabel }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; ariaLabel?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`
        relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors
        ${checked ? "bg-primary" : "bg-muted-foreground/25"}
        ${disabled ? "opacity-50 cursor-not-allowed" : ""}
      `}
    >
      <span
        className={`
          inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform
          ${checked ? "translate-x-5" : "translate-x-0"}
        `}
      />
    </button>
  )
}

export default function SubscriptionPage() {
  const { t } = useLocale()
  const { data: subscription, isLoading, isError, error, refetch } = useSubscription()
  const portalMutation = useCreatePortalSession()
  const checkoutMutation = useCreateCheckoutSession()
  const billingTermMutation = useUpdateBillingTerm()
  const toggleAddonMutation = useToggleAddon()
  const cancelMutation = useCancelSubscription()
  const reactivateMutation = useReactivateSubscription()

  // Modal states
  const [termModalOpen, setTermModalOpen] = useState(false)
  const [pendingTerm, setPendingTerm] = useState<"monthly" | "annual" | null>(null)
  const [cancelModalOpen, setCancelModalOpen] = useState(false)

  // ── Loading state ──────────────────────────────────────
  if (isLoading) {
    return (
      <>
        <Helmet><title>{t("subscription.title")} — Operion ERP</title></Helmet>
        <SectionWrapper>
          <div className="space-y-4">
            <Skeleton className="h-9 w-48" />
            <Skeleton className="h-5 w-96" />
            <div className="mt-8 grid gap-8 lg:grid-cols-3">
              <div className="lg:col-span-2 space-y-4">
                <Skeleton className="h-48 w-full rounded-xl" />
                <Skeleton className="h-64 w-full rounded-xl" />
              </div>
              <div>
                <Skeleton className="h-48 w-full rounded-xl" />
              </div>
            </div>
          </div>
        </SectionWrapper>
      </>
    )
  }

  // ── Error state ────────────────────────────────────────
  if (isError) {
    return (
      <>
        <Helmet><title>{t("subscription.title")} — Operion ERP</title></Helmet>
        <SectionWrapper>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
            <h1 className="text-3xl font-bold tracking-tight">{t("subscription.title")}</h1>
            <p className="mt-2 text-muted-foreground">{t("subscription.description")}</p>
          </motion.div>

          <div className="mt-8 grid gap-8 lg:grid-cols-3">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
              className="lg:col-span-2"
            >
              <Card className="border-destructive/30">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AlertCircle className="h-5 w-5 text-destructive" />
                    {t("subscription.title")}
                  </CardTitle>
                  <CardDescription>{t("subscription.description")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Callout variant="danger" title={t("subscription.unableToLoadSubscription")}>
                    <p className="text-sm">
                      {error instanceof Error ? error.message : t("subscription.unexpectedError")}
                      {" "}{t("subscription.apiMayNotBeAvailable")}
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
                        {t("subscription.contactSupport")}
                      </a>
                    </Button>
                  </div>

                  <Separator />

                  <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
                    <p className="font-medium text-foreground mb-2">{t("subscription.apiNotYetAvailable")}</p>
                    <p>
                      {t("subscription.backendUnderDevelopment")}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.15 }}
            >
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t("subscription.currentStatus")}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t("subscription.status")}</span>
                    <Badge variant="outline">{t("subscription.comingSoonBadge")}</Badge>
                  </div>
                  <p className="border-t pt-3 text-xs text-muted-foreground">
                    {t("subscription.comingSoonNote")}
                  </p>
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </SectionWrapper>
      </>
    )
  }

  // ── Empty / no subscription state ──────────────────────
  if (!subscription) {
    return (
      <>
        <Helmet><title>{t("subscription.title")} — Operion ERP</title></Helmet>
        <SectionWrapper>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
            <h1 className="text-3xl font-bold tracking-tight">{t("subscription.title")}</h1>
            <p className="mt-2 text-muted-foreground">{t("subscription.description")}</p>
          </motion.div>

          <div className="mt-8 grid gap-8 lg:grid-cols-3">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
              className="lg:col-span-2"
            >
              <Card className="border-primary/30">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CreditCard className="h-5 w-5" />
                    {t("subscription.title")}
                  </CardTitle>
                  <CardDescription>{t("subscription.description")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <Callout variant="info" title={t("subscription.comingSoonWhat")}>
                    {t("subscription.comingSoonWhatDesc")}
                  </Callout>

                  <div className="space-y-4">
                    <h4 className="text-sm font-semibold">{t("subscription.includes")}</h4>
                    <ul className="space-y-3 text-sm text-muted-foreground">
                      <li className="flex items-center gap-3">
                        <Truck className="h-4 w-4 shrink-0 text-primary" />
                        {t("subscription.includesTrucks")}
                      </li>
                      <li className="flex items-center gap-3">
                        <Shield className="h-4 w-4 shrink-0 text-primary" />
                        {t("subscription.includesFeatures")}
                      </li>
                      <li className="flex items-center gap-3">
                        <Mail className="h-4 w-4 shrink-0 text-primary" />
                        {t("subscription.includesSupport")}
                      </li>
                    </ul>
                  </div>

                  <div className="flex flex-wrap gap-3">
                    <Button
                      onClick={() => {
                        trackEvent("checkout_started", "subscription", "no_subscription_upgrade")
                        checkoutMutation.mutate(undefined, {
                          onSuccess: (res) => {
                            if ("mock" in res.data && res.data.mock) {
                              trackEvent("checkout_completed", "subscription", "mock_mode")
                              toast.info(t("subscription.checkout.demoMode"))
                            } else if ("url" in res.data && res.data.url) {
                              window.location.href = res.data.url
                            }
                          },
                          onError: () => toast.error(t("subscription.checkoutFailed")),
                        })
                      }}
                      disabled={checkoutMutation.isPending}
                    >
                      {checkoutMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ChevronRight className="mr-2 h-4 w-4" />}
                      {t("subscription.upgrade")}
                    </Button>
                    <Button variant="outline" asChild>
                      <a href="mailto:support@operionerp.xyz">
                        {t("subscription.contactSupport")}
                        <ArrowUpRight className="ml-1 h-4 w-4" />
                      </a>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.15 }}
            >
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t("subscription.currentStatus")}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t("subscription.status")}</span>
                    <Badge>{t("subscription.preLaunch")}</Badge>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t("subscription.truckCount")}</span>
                    <span className="font-medium text-muted-foreground">—</span>
                  </div>
                  <p className="border-t pt-3 text-xs text-muted-foreground">
                    {t("subscription.comingSoonNote")}
                  </p>
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </SectionWrapper>
      </>
    )
  }

  // ── Data state ─────────────────────────────────────────
  const StatusIcon = STATUS_ICONS[subscription.status]

  const trialState = getTrialState(subscription)
  const trialDaysLeft = daysLeftInTrial(subscription)

  const monthlyErpTotal = (subscription.licensed_truck_count * subscription.price_per_truck_erp_cents) / 100
  const monthlyAiTotal = subscription.ai_copilot_enabled
    ? (subscription.licensed_truck_count * subscription.price_per_truck_ai_cents) / 100
    : 0
  const monthlyPrioritySupport = subscription.priority_support_enabled ? subscription.priority_support_price_cents / 100 : 0
  const monthlyApiAccess = subscription.api_access_enabled ? subscription.api_access_price_cents / 100 : 0
  const addonTotal = monthlyAiTotal + monthlyPrioritySupport + monthlyApiAccess
  const subtotal = monthlyErpTotal + addonTotal
  const annualDiscount = subscription.billing_term === "annual" ? subtotal * (subscription.annual_discount_pct / 100) : 0
  const serviceCredit = subscription.service_credit_cents / 100
  const total = subtotal - annualDiscount - serviceCredit
  const isAnnual = subscription.billing_term === "annual"

  const addons = [
    {
      key: "ai_copilot" as const,
      label: t("subscription.addonAiCopilot"),
      icon: Zap,
      price: subscription.price_per_truck_ai_cents / 100,
      enabled: subscription.ai_copilot_enabled,
      perTruck: true,
    },
    {
      key: "priority_support" as const,
      label: t("subscription.addonPrioritySupport"),
      icon: Headphones,
      price: subscription.priority_support_price_cents / 100,
      enabled: subscription.priority_support_enabled,
      perTruck: false,
    },
    {
      key: "api_access" as const,
      label: t("subscription.addonApiAccess"),
      icon: Code2,
      price: subscription.api_access_price_cents / 100,
      enabled: subscription.api_access_enabled,
      perTruck: false,
    },
  ]

  const handleTermClick = (term: "monthly" | "annual") => {
    if (term === subscription.billing_term) return
    setPendingTerm(term)
    setTermModalOpen(true)
  }

  const confirmTermChange = () => {
    if (!pendingTerm) return
    billingTermMutation.mutate(pendingTerm, {
      onSuccess: () => {
        toast.success(t("subscription.billingTermChanged").replace("{term}", pendingTerm))
        setTermModalOpen(false)
        setPendingTerm(null)
      },
      onError: (err: any) => {
        const msg = err?.response?.data?.detail || err?.message || t("subscription.billingTermChangeFailed")
        toast.error(msg)
      },
    })
  }

  const handleAddonToggle = (addonKey: typeof addons[number]["key"], nextEnabled: boolean) => {
    toggleAddonMutation.mutate(
      { addon: addonKey, enabled: nextEnabled },
      {
        onSuccess: () => {
          const label = addons.find((a) => a.key === addonKey)?.label
          toast.success(t("subscription.addonToggled").replace("{name}", label ?? addonKey).replace("{state}", nextEnabled ? t("common.enabled") : t("common.disabled")))
        },
        onError: (err: any) => {
          const msg = err?.response?.data?.detail || err?.message || t("subscription.addonUpdateFailed")
          toast.error(msg)
        },
      }
    )
  }

  const handleCheckout = () => {
    trackEvent("checkout_started", "subscription", subscription.status)
    checkoutMutation.mutate(undefined, {
      onSuccess: (res) => {
        if ("mock" in res.data && res.data.mock) {
          trackEvent("checkout_completed", "subscription", "mock_mode")
          toast.info(t("subscription.checkout.demoMode"))
        } else if ("url" in res.data && res.data.url) {
          window.location.href = res.data.url
        }
      },
      onError: () => toast.error(t("subscription.checkoutFailed")),
    })
  }

  return (
    <>
      <Helmet><title>{t("subscription.title")} — Operion ERP</title></Helmet>
      <SectionWrapper>
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">{t("subscription.title")}</h1>
              <p className="mt-2 text-muted-foreground">{t("subscription.description")}</p>
            </div>
            <div className="flex items-center gap-2">
              {subscription.status === "canceled" && (
                <Badge variant="destructive" className="shrink-0">
                  <XCircle className="mr-1 h-3 w-3" />
                  {t("subscription.canceled")}
                </Badge>
              )}
              {trialState === "expiring_soon" && (
                <Badge className="shrink-0 border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                  <Clock className="mr-1 h-3 w-3" />
                  {t("subscription.trialEndsIn").replace("{days}", String(trialDaysLeft))}
                </Badge>
              )}
            </div>
          </div>
        </motion.div>

        <div className="mt-8 grid gap-8 lg:grid-cols-3">
          {/* ── Main subscription details ── */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="lg:col-span-2 space-y-6"
          >
            {/* Plan Card */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <CreditCard className="h-5 w-5" />
                    {t("subscription.currentPlan")}
                  </CardTitle>
                  <Badge variant={STATUS_VARIANTS[subscription.status]}>
                    <StatusIcon className="mr-1 h-3 w-3 inline" />
                    {subscription.status.charAt(0).toUpperCase() + subscription.status.slice(1)}
                  </Badge>
                </div>
                <CardDescription>
                  {t("subscription.perTruckBilling")}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Per-truck price */}
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold">
                    {formatCurrency(subscription.price_per_truck_erp_cents / 100)}
                  </span>
                  <span className="text-muted-foreground">{t("subscription.perTruckPerMonth")}</span>
                  <Badge variant="secondary" className="ml-2">
                    {isAnnual ? t("subscription.annual") : t("subscription.monthly")}
                  </Badge>
                </div>

                <Separator />

                {/* Period */}
                <div className="grid gap-4 sm:grid-cols-2">
                  {subscription.current_period_end && (
                    <>
                      <div>
                        <p className="text-xs text-muted-foreground">{t("subscription.renewsOn")}</p>
                        <p className="text-sm font-medium">{formatDate(subscription.current_period_end)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">{t("subscription.nextBillingDate")}</p>
                        <p className="text-sm font-medium">{formatDate(subscription.current_period_end)}</p>
                      </div>
                    </>
                  )}
                  {!subscription.current_period_end && subscription.trial_ends_at && (
                    <div>
                      <p className="text-xs text-muted-foreground">{t("subscription.trialEnds")}</p>
                      <p className="text-sm font-medium">{formatDate(subscription.trial_ends_at)}</p>
                    </div>
                  )}
                </div>

                {/* Price breakdown */}
                <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
                  <h4 className="text-sm font-semibold mb-2">{t("subscription.priceBreakdown")}</h4>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                      {t("subscription.trucksTimesPrice")
                        .replace("{count}", String(subscription.licensed_truck_count))
                        .replace("{price}", formatCurrency(subscription.price_per_truck_erp_cents / 100))}
                    </span>
                    <span className="font-medium">{formatCurrency(monthlyErpTotal)}</span>
                  </div>
                  {subscription.ai_copilot_enabled && (
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">
                        {t("subscription.aiCopilotTimesPrice")
                          .replace("{count}", String(subscription.licensed_truck_count))
                          .replace("{price}", formatCurrency(subscription.price_per_truck_ai_cents / 100))}
                      </span>
                      <span className="font-medium">{formatCurrency(monthlyAiTotal)}</span>
                    </div>
                  )}
                  {subscription.priority_support_enabled && (
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("subscription.prioritySupportFixed")}</span>
                      <span className="font-medium">{formatCurrency(monthlyPrioritySupport)}</span>
                    </div>
                  )}
                  {subscription.api_access_enabled && (
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t("subscription.apiAccessFixed")}</span>
                      <span className="font-medium">{formatCurrency(monthlyApiAccess)}</span>
                    </div>
                  )}
                  <Separator />
                  {isAnnual && annualDiscount > 0 && (
                    <div className="flex items-center justify-between text-sm text-green-600">
                      <span>{t("subscription.annualDiscount").replace("{percent}", String(subscription.annual_discount_pct))}</span>
                      <span>-{formatCurrency(annualDiscount)}</span>
                    </div>
                  )}
                  {serviceCredit > 0 && (
                    <div className="flex items-center justify-between text-sm text-green-600">
                      <span>{t("subscription.serviceCredit")}</span>
                      <span>-{formatCurrency(serviceCredit)}</span>
                    </div>
                  )}
                  <div className="flex items-center justify-between text-sm font-semibold">
                    <span>{t("subscription.total")}</span>
                    <span>{formatCurrency(Math.max(0, total))}</span>
                  </div>
                </div>

                {/* Features derived from enabled addons */}
                {(subscription.ai_copilot_enabled || subscription.priority_support_enabled || subscription.api_access_enabled) && (
                  <>
                    <Separator />
                    <div>
                      <h4 className="text-sm font-semibold mb-3">{t("subscription.includedFeatures")}</h4>
                      <ul className="grid gap-2 sm:grid-cols-2">
                        {subscription.ai_copilot_enabled && (
                          <li className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Zap className="h-4 w-4 shrink-0 text-primary" />
                            {t("subscription.addonAiCopilot")}
                          </li>
                        )}
                        {subscription.priority_support_enabled && (
                          <li className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Headphones className="h-4 w-4 shrink-0 text-primary" />
                            {t("subscription.addonPrioritySupport")}
                          </li>
                        )}
                        {subscription.api_access_enabled && (
                          <li className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Code2 className="h-4 w-4 shrink-0 text-primary" />
                            {t("subscription.addonApiAccess")}
                          </li>
                        )}
                      </ul>
                    </div>
                  </>
                )}

                {/* Licensed truck count + Fleet Manager note */}
                <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t("subscription.licensedTrucks")}</span>
                    <span className="font-medium">{subscription.licensed_truck_count}</span>
                  </div>
                  {subscription.pending_truck_count != null && subscription.pending_truck_count !== subscription.licensed_truck_count && (
                    <div className="flex items-center justify-between text-sm text-amber-600">
                      <span>{t("subscription.pendingChange")}</span>
                      <span className="font-medium">{subscription.pending_truck_count}</span>
                    </div>
                  )}
                  <div className="flex items-start gap-2 text-xs text-muted-foreground">
                    <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                    <span>{t("subscription.fleetManagerNote")}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Billing Term */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Calendar className="h-4 w-4" />
                  {t("subscription.billingCycle")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2">
                  <Button
                    variant={isAnnual ? "outline" : "default"}
                    size="sm"
                    onClick={() => handleTermClick("monthly")}
                    disabled={billingTermMutation.isPending}
                  >
                    {t("subscription.monthly")}
                  </Button>
                  <Button
                    variant={isAnnual ? "default" : "outline"}
                    size="sm"
                    onClick={() => handleTermClick("annual")}
                    disabled={billingTermMutation.isPending}
                  >
                    {t("subscription.annual")}
                  </Button>
                </div>
                {isAnnual && (
                  <p className="mt-3 text-xs text-green-600 font-medium">
                    {t("subscription.savingWithAnnual").replace("{percent}", String(subscription.annual_discount_pct))}
                  </p>
                )}
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("subscription.billingTermChangeNote")}
                </p>
                {billingTermMutation.isPending && (
                  <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    {t("subscription.updatingBillingTerm")}
                  </div>
                )}
                {billingTermMutation.isError && (
                  <Callout variant="danger" className="mt-3" title={t("common.errorTitle")}>
                    <p className="text-sm">
                      {(billingTermMutation.error as any)?.response?.data?.detail ||
                        (billingTermMutation.error as any)?.message ||
                        t("subscription.unableToChangeBillingTerm")}
                    </p>
                  </Callout>
                )}
              </CardContent>
            </Card>

            {/* Add-ons */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t("subscription.addons")}</CardTitle>
                <CardDescription>{t("subscription.addonsDesc")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {addons.map((addon) => {
                  const Icon = addon.icon
                  const priceLabel = addon.perTruck
                    ? `+${formatCurrency(addon.price)}${t("subscription.perTruckPerMonth")}`
                    : `+${formatCurrency(addon.price)}${t("subscription.perMonth")}`
                  const isPending = toggleAddonMutation.isPending && toggleAddonMutation.variables?.addon === addon.key
                  return (
                    <div
                      key={addon.key}
                      className={`flex items-center justify-between rounded-lg border p-3 ${addon.enabled ? "border-primary/40 bg-primary/5" : ""}`}
                    >
                      <div className="flex items-center gap-3">
                        <Icon className={`h-4 w-4 ${addon.enabled ? "text-primary" : "text-muted-foreground"}`} />
                        <div>
                          <p className="text-sm font-medium">{addon.label}</p>
                          <p className="text-xs text-muted-foreground">{priceLabel}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {isPending && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
                        <ToggleSwitch
                          checked={addon.enabled}
                          onChange={(next) => handleAddonToggle(addon.key, next)}
                          disabled={toggleAddonMutation.isPending}
                          ariaLabel={t("subscription.toggleAddon").replace("{name}", addon.label)}
                        />
                      </div>
                    </div>
                  )
                })}
                {toggleAddonMutation.isError && (
                  <Callout variant="danger" title={t("common.errorTitle")}>
                    <p className="text-sm">
                      {(toggleAddonMutation.error as any)?.response?.data?.detail ||
                        (toggleAddonMutation.error as any)?.message ||
                        t("subscription.unableToUpdateAddon")}
                    </p>
                  </Callout>
                )}
              </CardContent>
            </Card>

            {/* Cancel / Reactivate */}
            {subscription.status === "canceled" ? (
              <Card className="border-primary/30">
                <CardHeader>
                  <CardTitle className="text-base">{t("subscription.reactivate.title")}</CardTitle>
                  <CardDescription>{t("subscription.reactivate.description")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button
                    variant="default"
                    onClick={() =>
                      reactivateMutation.mutate(undefined, {
                        onSuccess: () => toast.success(t("subscription.reactivated")),
                        onError: (err: any) => toast.error(err?.response?.data?.detail || err?.message || t("subscription.reactivateFailed")),
                      })
                    }
                    disabled={reactivateMutation.isPending}
                  >
                    {reactivateMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                    {t("subscription.reactivate.title")}
                  </Button>
                  {reactivateMutation.isError && (
                    <Callout variant="danger" title={t("common.errorTitle")}>
                      <p className="text-sm">
                        {(reactivateMutation.error as any)?.response?.data?.detail ||
                          (reactivateMutation.error as any)?.message ||
                          t("subscription.unableToReactivate")}
                      </p>
                    </Callout>
                  )}
                </CardContent>
              </Card>
            ) : (
              <Card className="border-destructive/20">
                <CardHeader>
                  <CardTitle className="text-base text-destructive">{t("subscription.modal.cancelTitle")}</CardTitle>
                  <CardDescription>{t("subscription.modal.cancelBody")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button
                    variant="outline"
                    className="border-destructive/30 text-destructive hover:bg-destructive/5"
                    onClick={() => setCancelModalOpen(true)}
                  >
                    <XCircle className="mr-2 h-4 w-4" />
                    {t("subscription.cancelSubscription")}
                  </Button>
                </CardContent>
              </Card>
            )}
          </motion.div>

          {/* ── Status Sidebar ── */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 }}
            className="space-y-6"
          >
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t("subscription.currentStatus")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{t("subscription.status")}</span>
                  <Badge variant={STATUS_VARIANTS[subscription.status]}>
                    <StatusIcon className="mr-1 h-3 w-3 inline" />
                    {subscription.status}
                  </Badge>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{t("subscription.truckCount")}</span>
                  <span className="font-medium">{subscription.licensed_truck_count}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{t("subscription.billingTerm")}</span>
                  <Badge variant="secondary">
                    {isAnnual ? t("subscription.annual") : t("subscription.monthly")}
                  </Badge>
                </div>
                {subscription.payment_deferred_until && (
                  <Callout variant="warning" title={t("subscription.paymentDeferred")}>
                    {t("subscription.paymentDeferredUntil").replace("{date}", formatDate(subscription.payment_deferred_until))}
                  </Callout>
                )}
                {trialState === "expiring_soon" && (
                  <Callout variant="warning" title={t("subscription.trialEndingSoon")}>
                    {t("subscription.trialEndingSoonBody")
                      .replace("{days}", String(trialDaysLeft))
                      .replace("{unit}", trialDaysLeft === 1 ? t("subscription.day") : t("subscription.days"))}
                  </Callout>
                )}
                {trialState === "expired" && (
                  <Callout variant="warning" title={t("subscription.trialEnded")}>
                    {t("subscription.trialEndedBody")}
                    {" "}{t("subscription.subscriptionStatus").replace("{status}", subscription.status)}
                  </Callout>
                )}
              </CardContent>
            </Card>

            {/* Manage Billing */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t("subscription.billing")}</CardTitle>
                <CardDescription>{t("subscription.billingDesc")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button
                  variant="default"
                  className="w-full"
                  onClick={handleCheckout}
                  disabled={checkoutMutation.isPending}
                >
                  {checkoutMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t("subscription.opening")}
                    </>
                  ) : (
                    <>
                      <CreditCard className="mr-2 h-4 w-4" />
                      {t("subscription.upgradePay")}
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => {
                    portalMutation.mutate(undefined, {
                      onSuccess: (res) => {
                        if ("url" in res.data && res.data.url) {
                          window.location.href = res.data.url
                        }
                      },
                      onError: (_err) => {
                        toast.error(t("subscription.billingPortalUnavailable"))
                      },
                    })
                  }}
                  disabled={portalMutation.isPending}
                >
                  {portalMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t("subscription.opening")}
                    </>
                  ) : (
                    <>
                      <ExternalLink className="mr-2 h-4 w-4" />
                      {t("subscription.manageBilling")}
                    </>
                  )}
                </Button>
                {checkoutMutation.isError && (
                  <Callout variant="danger" title={t("subscription.checkoutError")}>
                    <p className="text-sm">
                      {(checkoutMutation.error as any)?.response?.data?.detail ||
                        (checkoutMutation.error as any)?.message ||
                        t("subscription.checkoutFailedShort")}
                    </p>
                  </Callout>
                )}
              </CardContent>
            </Card>

            {/* Contact card */}
            <Card>
              <CardContent className="pt-6">
                <Button variant="outline" className="w-full" asChild>
                  <a href="mailto:support@operionerp.xyz">
                    <Mail className="mr-2 h-4 w-4" />
                    {t("subscription.contactSupport")}
                  </a>
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>

      {/* ── Billing Term Confirmation Modal ── */}
      <AnimatePresence>
        {termModalOpen && (
          <InlineModal
            open={termModalOpen}
            onClose={() => { setTermModalOpen(false); setPendingTerm(null) }}
            title={t("subscription.confirmBillingTermChange")}
          >
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {pendingTerm === "annual" ? (
                  t("subscription.modal.confirmTermChange").replace("{discount}", String(subscription.annual_discount_pct))
                ) : (
                  <>
                    {t("subscription.switchingToMonthly1")}{" "}
                    <strong>{t("subscription.monthlyBilling")}</strong>{" "}
                    {t("subscription.switchingToMonthly2")}
                  </>
                )}
              </p>
              {pendingTerm === "monthly" && (
                <Callout variant="warning" title={t("subscription.important")}>
                  <p className="text-sm">{t("subscription.annualToMonthlyNote")}</p>
                </Callout>
              )}
              <div className="flex gap-3 justify-end">
                <Button variant="outline" size="sm" onClick={() => { setTermModalOpen(false); setPendingTerm(null) }}>
                  {t("subscription.keepTerm").replace("{term}", subscription.billing_term)}
                </Button>
                <Button
                  size="sm"
                  onClick={confirmTermChange}
                  disabled={billingTermMutation.isPending}
                >
                  {billingTermMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  {t("subscription.confirmTerm").replace("{term}", pendingTerm ?? "")}
                </Button>
              </div>
            </div>
          </InlineModal>
        )}
      </AnimatePresence>

      {/* ── Cancel Confirmation Modal ── */}
      <AnimatePresence>
        {cancelModalOpen && (
          <InlineModal
            open={cancelModalOpen}
            onClose={() => setCancelModalOpen(false)}
            title={t("subscription.cancelYourSubscription")}
          >
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {t("subscription.cancelBody1")}{" "}
                <strong>{subscription.current_period_end ? formatDate(subscription.current_period_end) : t("subscription.endOfBillingPeriod")}</strong>
                {t("subscription.cancelBody2")}
              </p>
              <Callout variant="warning" title={t("subscription.reactivateLater")}>
                <p className="text-sm">{t("subscription.reactivate.description")}</p>
              </Callout>
              <div className="flex gap-3 justify-end">
                <Button variant="outline" size="sm" onClick={() => setCancelModalOpen(false)}>
                  {t("subscription.keepSubscription")}
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() =>
                    cancelMutation.mutate(undefined, {
                      onSuccess: () => {
                        toast.success(t("subscription.canceledSuccess"))
                        setCancelModalOpen(false)
                      },
                      onError: (err: any) => {
                        toast.error(err?.response?.data?.detail || err?.message || t("subscription.cancelFailed"))
                      },
                    })
                  }
                  disabled={cancelMutation.isPending}
                >
                  {cancelMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  {t("subscription.yesCancel")}
                </Button>
              </div>
              {cancelMutation.isError && (
                <Callout variant="danger" className="mt-2" title={t("common.errorTitle")}>
                  <p className="text-sm">
                    {(cancelMutation.error as any)?.response?.data?.detail ||
                      (cancelMutation.error as any)?.message ||
                      t("subscription.unableToCancel")}
                  </p>
                </Callout>
              )}
            </div>
          </InlineModal>
        )}
      </AnimatePresence>
    </>
  )
}
