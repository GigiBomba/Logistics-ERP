import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { CreditCard, Calendar, ArrowUpRight, Download, Wallet, Tag, Sparkles, Receipt } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Callout } from "@/components/ui/callout"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { EmptyState } from "@/components/shared/empty-state"
import { Timeline } from "@/components/shared/timeline"
import { ComparisonTable } from "@/components/shared/comparison-table"
// TODO: Implement when backend endpoint is ready
// import { useInvoices } from "@/services/queries"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { useLocale } from "@/i18n/locale-context"

const timelineItems = [
  { date: "Sep 1, 2026", title: "Plan Renewal", description: "Professional Plan renews at €99/month", status: "upcoming" as const },
  { date: "Aug 1, 2026", title: "Invoice Paid", description: "Invoice #INV-2026-008 paid successfully", status: "completed" as const },
  { date: "Jul 1, 2026", title: "Plan Activated", description: "Upgraded to Professional Plan (25 licenses)", status: "completed" as const },
  { date: "Jun 15, 2026", title: "Trial Started", description: "14-day free trial began", status: "completed" as const },
]

const comparisonColumns = [
  { label: "Starter", icon: undefined },
  { label: "Professional", icon: undefined },
  { label: "Enterprise", icon: undefined },
]

const comparisonRows = [
  { feature: "Licenses", values: ["5", "25", "Unlimited"] },
  { feature: "Vehicles", values: ["10", "100", "Unlimited"] },
  { feature: "Route Optimization", values: [true, true, true] },
  { feature: "Real-time Dispatch", values: [false, true, true] },
  { feature: "API Access", values: [false, true, true] },
  { feature: "Priority Support", values: [false, false, true] },
  { feature: "Custom Integrations", values: [false, false, true] },
  { feature: "Dedicated Account Manager", values: [false, false, true] },
]

const mockInvoices = [
  { id: "inv-1", number: "INV-2026-008", amount: 99.00, currency: "EUR", status: "paid" as const, issued_at: "2026-08-01", due_at: "2026-08-01", paid_at: "2026-08-01" },
  { id: "inv-2", number: "INV-2026-007", amount: 99.00, currency: "EUR", status: "paid" as const, issued_at: "2026-07-01", due_at: "2026-07-01", paid_at: "2026-07-01" },
  { id: "inv-3", number: "INV-2026-006", amount: 99.00, currency: "EUR", status: "paid" as const, issued_at: "2026-06-01", due_at: "2026-06-01", paid_at: "2026-06-01" },
]

export default function SubscriptionPage() {
  const { t } = useLocale()
  // TODO: Implement when backend endpoint is ready
  // const { data: invoices, isLoading: invoicesLoading } = useInvoices()
  // const displayInvoices = invoices || mockInvoices
  const invoicesLoading = false
  const displayInvoices = mockInvoices

  return (
    <>
      <Helmet><title>{t("subscription.title")} — Operion ERP</title></Helmet>
      <SectionWrapper>
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h1 className="text-3xl font-bold tracking-tight">{t("subscription.title")}</h1>
          <p className="mt-2 text-muted-foreground">{t("subscription.description")}</p>
        </motion.div>

        <Tabs defaultValue="plan" className="mt-8">
          <TabsList className="mb-6">
            <TabsTrigger value="plan">{t("subscription.plan")}</TabsTrigger>
            <TabsTrigger value="billing">{t("subscription.billing")}</TabsTrigger>
            <TabsTrigger value="history">{t("subscription.history")}</TabsTrigger>
          </TabsList>

          <TabsContent value="plan" className="space-y-8">
            <div className="grid gap-8 lg:grid-cols-3">
              {/* Current Plan */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }} className="lg:col-span-2">
                <Card className="border-primary/30">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2"><CreditCard className="h-5 w-5" /> {t("subscription.currentPlan")}</CardTitle>
                      <Badge variant="success">{t("common.active")}</Badge>
                    </div>
                    <CardDescription>{t("subscription.professionalPlanDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="flex items-baseline gap-1">
                        <span className="text-4xl font-bold">€99</span>
                        <span className="text-muted-foreground">{t("subscription.perMonth")}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">{t("subscription.renewsOn")} <strong>September 1, 2026</strong></span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button variant="outline" size="sm" disabled>{t("subscription.upgrade")} <ArrowUpRight className="ml-1 h-3 w-3" /></Button>
                        <Button variant="outline" size="sm" disabled>{t("subscription.downgrade")}</Button>
                        <Button variant="outline" size="sm" disabled>{t("common.cancel")}</Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Billing Status */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">{t("subscription.billingStatus")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{t("subscription.status")}</span>
                      <Badge variant="success">{t("subscription.paid")}</Badge>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{t("subscription.nextInvoice")}</span>
                      <span>Sep 1, 2026</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{t("subscription.licensesUsed")}</span>
                      <span>5 / 25</span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Renewal Info */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2"><Calendar className="h-4 w-4" /> {t("subscription.renewalInfo")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{t("subscription.nextBillingDate")}</span>
                      <span className="font-medium">Sep 1, 2026</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{t("subscription.amount")}</span>
                      <span className="font-medium">€99.00</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{t("subscription.billingCycle")}</span>
                      <span className="font-medium">{t("subscription.monthly")}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{t("subscription.paymentMethod")}</span>
                      <span className="font-medium">—</span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Upgrade Recommendation */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.25 }} className="lg:col-span-2">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2"><Sparkles className="h-4 w-4" /> {t("subscription.upgradeRecommendation")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Callout variant="info" title={t("subscription.basedOnUsage")}>
                      {t("subscription.upgradeRecommendationDesc")}
                    </Callout>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" disabled>{t("subscription.viewEnterprise")}</Button>
                      <Button variant="ghost" size="sm" disabled>{t("subscription.talkToSales")}</Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* Feature Comparison */}
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.3 }}>
              <h2 className="text-xl font-bold tracking-tight mb-4">{t("subscription.featureComparison")}</h2>
              <Card>
                <CardContent className="p-0">
                  <ComparisonTable columns={comparisonColumns} rows={comparisonRows} />
                </CardContent>
              </Card>
            </motion.div>

            {/* Subscription Timeline */}
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.35 }}>
              <h2 className="text-xl font-bold tracking-tight mb-4">{t("subscription.timeline")}</h2>
              <Card>
                <CardContent className="p-6">
                  <Timeline items={timelineItems} />
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          <TabsContent value="billing" className="space-y-8">
            <div className="grid gap-8 lg:grid-cols-2">
              {/* Payment Methods Placeholder */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Wallet className="h-5 w-5" /> {t("billing.paymentMethods")}</CardTitle>
                    <CardDescription>{t("billing.paymentMethodsDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <EmptyState title={t("billing.noPaymentMethods")} description={t("billing.noPaymentMethodsDesc")} />
                  </CardContent>
                </Card>
              </motion.div>

              {/* Coupon Code Placeholder */}
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Tag className="h-5 w-5" /> {t("billing.couponCode")}</CardTitle>
                    <CardDescription>{t("billing.couponCodeDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex gap-2">
                      <input
                        type="text"
                        placeholder={t("billing.enterCode")}
                        disabled
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                      />
                      <Button disabled>{t("billing.apply")}</Button>
                    </div>
                    <p className="text-xs text-muted-foreground">{t("billing.couponCodePlaceholder")}</p>
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* Upgrade / Downgrade Placeholders */}
            <div className="grid gap-8 lg:grid-cols-2">
              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">{t("subscription.upgradePlan")}</CardTitle>
                    <CardDescription>{t("subscription.upgradePlanDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground mb-4">{t("subscription.upgradePlaceholder")}</p>
                    <Button variant="outline" className="w-full" disabled>{t("common.comingSoon")}</Button>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.25 }}>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">{t("subscription.downgradePlan")}</CardTitle>
                    <CardDescription>{t("subscription.downgradePlanDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground mb-4">{t("subscription.downgradePlaceholder")}</p>
                    <Button variant="outline" className="w-full" disabled>{t("common.comingSoon")}</Button>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </TabsContent>

          <TabsContent value="history" className="space-y-8">
            {/* Invoice History */}
            <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }}>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><Receipt className="h-5 w-5" /> {t("billing.invoiceHistory")}</CardTitle>
                  <CardDescription>{t("billing.invoiceHistoryDesc")}</CardDescription>
                </CardHeader>
                <CardContent>
                  {invoicesLoading ? (
                    <div className="flex justify-center py-12">
                      <LoadingSpinner size="lg" />
                    </div>
                  ) : displayInvoices.length === 0 ? (
                    <EmptyState title={t("billing.noInvoices")} description={t("billing.noInvoicesDesc")} />
                  ) : (
                    <div className="space-y-3">
                      {displayInvoices.map((invoice: { id: string; number: string; amount: number; currency: string; status: string; issued_at: string; due_at: string; paid_at: string }) => (
                        <div key={invoice.id} className="flex items-center justify-between rounded-lg border p-4">
                          <div className="flex items-center gap-4">
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
                              <Receipt className="h-5 w-5 text-primary" />
                            </div>
                            <div>
                              <p className="text-sm font-medium">{invoice.number}</p>
                              <p className="text-xs text-muted-foreground">
                                {t("billing.issued")} {invoice.issued_at} · {t("billing.due")} {invoice.due_at}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-4">
                            <div className="text-right">
                              <p className="text-sm font-medium">
                                {invoice.amount.toFixed(2)} {invoice.currency}
                              </p>
                              <Badge variant={invoice.status === "paid" ? "success" : invoice.status === "open" ? "default" : "secondary"}>
                                {invoice.status}
                              </Badge>
                            </div>
                            <Button variant="ghost" size="sm" disabled>
                              <Download className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>
        </Tabs>
      </SectionWrapper>
    </>
  )
}
