import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import {
  CreditCard,
  Receipt,
  Download,
  Calendar,
  Wallet,
  Landmark,
  FileText,
  ArrowUpRight,
  Plus,
  ArrowDownToLine,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { Callout } from "@/components/ui/callout"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import { EmptyState } from "@/components/shared/empty-state"
import type { Invoice } from "@/types"

const mockInvoices: Invoice[] = [
  { id: "inv-1", number: "INV-2026-008", amount: 99.0, currency: "EUR", status: "paid", issued_at: "2026-08-01", due_at: "2026-08-01", paid_at: "2026-08-01" },
  { id: "inv-2", number: "INV-2026-007", amount: 99.0, currency: "EUR", status: "paid", issued_at: "2026-07-01", due_at: "2026-07-01", paid_at: "2026-07-01" },
  { id: "inv-3", number: "INV-2026-006", amount: 99.0, currency: "EUR", status: "paid", issued_at: "2026-06-01", due_at: "2026-06-01", paid_at: "2026-06-01" },
  { id: "inv-4", number: "INV-2026-005", amount: 99.0, currency: "EUR", status: "paid", issued_at: "2026-05-01", due_at: "2026-05-01", paid_at: "2026-05-01" },
  { id: "inv-5", number: "INV-2026-004", amount: 99.0, currency: "EUR", status: "open", issued_at: "2026-04-01", due_at: "2026-04-01" },
  { id: "inv-6", number: "INV-2026-003", amount: 49.0, currency: "EUR", status: "void", issued_at: "2026-03-01", due_at: "2026-03-01" },
]

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function formatCurrency(amount: number, currency: string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(amount)
}

function getInvoiceBadgeVariant(status: string) {
  switch (status) {
    case "paid":
      return "success"
    case "open":
      return "default"
    case "void":
      return "secondary"
    default:
      return "outline"
  }
}

export default function BillingPage() {
  const { t } = useLocale()
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
            <Button disabled>
              <ArrowDownToLine className="mr-2 h-4 w-4" />
              {t("billing.exportData")}
            </Button>
          </div>
        </motion.div>

        <Tabs defaultValue="overview" className="mt-8">
          <TabsList className="mb-6">
            <TabsTrigger value="overview">{t("billing.overview")}</TabsTrigger>
            <TabsTrigger value="invoices">{t("billing.invoices")}</TabsTrigger>
            <TabsTrigger value="payment-methods">{t("billing.paymentMethods")}</TabsTrigger>
            <TabsTrigger value="tax-info">{t("billing.taxInfo")}</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-8">
            <div className="grid gap-6 lg:grid-cols-3">
              <motion.div
                className="lg:col-span-2"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
              >
                <Card className="border-primary/30">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2">
                        <CreditCard className="h-5 w-5" /> {t("billing.currentPlan")}
                      </CardTitle>
                      <Badge variant="success">{t("billing.active")}</Badge>
                    </div>
                    <CardDescription>
                      {t("billing.professionalPlanDesc")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-baseline gap-1">
                      <span className="text-4xl font-bold">€99</span>
                      <span className="text-muted-foreground">/month</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <Calendar className="h-4 w-4 text-muted-foreground" />
                      <span className="text-muted-foreground">
                        {t("billing.nextBilling")} <strong>September 1, 2026</strong>
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" size="sm" disabled>
                        {t("billing.changePlan")}
                      </Button>
                      <Button variant="ghost" size="sm" asChild>
                        <Link to="/dashboard/subscription">
                          {t("billing.viewSubscription")} <ArrowUpRight className="ml-1 h-3 w-3" />
                        </Link>
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
                    <CardTitle className="text-base flex items-center gap-2">
                      <Calendar className="h-4 w-4" /> {t("billing.nextBilling")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Date</span>
                      <span className="font-medium">Sep 1, 2026</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Amount</span>
                      <span className="font-medium">€99.00</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Cycle</span>
                      <span className="font-medium">Monthly</span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.2 }}
            >
              <h2 className="text-xl font-bold tracking-tight mb-4">{t("billing.usageSummary")}</h2>
              <div className="grid gap-4 sm:grid-cols-3">
                <Card>
                  <CardContent className="p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{t("billing.licenses")}</span>
                      <Badge variant="outline">12 / 25</Badge>
                    </div>
                    <Progress value={48} />
                    <p className="text-xs text-muted-foreground">48% of license seats used</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{t("billing.apiCalls")}</span>
                      <Badge variant="outline">—</Badge>
                    </div>
                    <Progress value={0} />
                    <p className="text-xs text-muted-foreground">{t("billing.apiComingSoon")}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{t("billing.storage")}</span>
                      <Badge variant="outline">2.3 GB / 10 GB</Badge>
                    </div>
                    <Progress value={23} />
                    <p className="text-xs text-muted-foreground">23% of storage limit used</p>
                  </CardContent>
                </Card>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.25 }}
            >
              <Card>
                <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
                      <FileText className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">{t("billing.billingHistory")}</p>
                      <p className="text-xs text-muted-foreground">
                        {t("billing.billingHistoryDesc")}
                      </p>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link to="/dashboard/subscription">{t("billing.viewInSubscription")}</Link>
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          {/* Invoices Tab */}
          <TabsContent value="invoices" className="space-y-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
            >
              <Card>
                <CardHeader>
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Receipt className="h-5 w-5" /> {t("billing.invoices")}
                      </CardTitle>
                      <CardDescription>{t("billing.invoicesDesc")}</CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <select
                        disabled
                        className="h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option>{t("billing.allYears")}</option>
                        <option>2026</option>
                        <option>2025</option>
                      </select>
                      <select
                        disabled
                        className="h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option>All Statuses</option>
                        <option>Paid</option>
                        <option>Open</option>
                        <option>Void</option>
                      </select>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {mockInvoices.map((invoice, index) => (
                      <motion.div
                        key={invoice.id}
                        initial={{ opacity: 0, y: 10 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.03 * index }}
                        className="flex items-center justify-between rounded-lg border p-4"
                      >
                        <div className="flex items-center gap-4">
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
                            <Receipt className="h-5 w-5 text-primary" />
                          </div>
                          <div>
                            <p className="text-sm font-medium">{invoice.number}</p>
                            <p className="text-xs text-muted-foreground">
                              {t("billing.issued")} {formatDate(invoice.issued_at)} · {t("billing.due")} {formatDate(invoice.due_at)}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          <div className="text-right">
                            <p className="text-sm font-medium">
                              {formatCurrency(invoice.amount, invoice.currency)}
                            </p>
                            <Badge variant={getInvoiceBadgeVariant(invoice.status)}>
                              {invoice.status}
                            </Badge>
                          </div>
                          <Button variant="ghost" size="sm" disabled>
                            <Download className="h-4 w-4" />
                          </Button>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          {/* Payment Methods Tab */}
          <TabsContent value="payment-methods" className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Wallet className="h-5 w-5" /> {t("billing.paymentMethods")}
                    </CardTitle>
                    <CardDescription>{t("billing.paymentMethodsDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <EmptyState
                      icon={<CreditCard className="h-16 w-16" />}
                      title="Payment methods coming soon"
                      description="You'll be able to add and manage credit cards, direct debit, and other payment methods."
                    />
                    <div className="flex items-center gap-3 pt-4">
                      <div className="flex h-8 w-12 items-center justify-center rounded border bg-muted text-xs font-bold text-muted-foreground">
                        VISA
                      </div>
                      <div className="flex h-8 w-12 items-center justify-center rounded border bg-muted text-xs font-bold text-muted-foreground">
                        MC
                      </div>
                      <div className="flex h-8 w-12 items-center justify-center rounded border bg-muted text-xs font-bold text-muted-foreground">
                        AMEX
                      </div>
                    </div>
                    <Button disabled>
                      <Plus className="mr-2 h-4 w-4" />
                      Add Payment Method
                    </Button>
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
                    <CardTitle className="text-base">Billing Contact</CardTitle>
                    <CardDescription>Email address for billing notifications.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <label htmlFor="billing-email" className="text-sm font-medium">
                        {t("support.email")}
                      </label>
                      <input
                        id="billing-email"
                        type="email"
                        defaultValue="billing@example.com"
                        disabled
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Billing contact management will be available in a future update.
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </TabsContent>

          {/* Tax Info Tab */}
          <TabsContent value="tax-info" className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Landmark className="h-5 w-5" /> {t("billing.taxInfo")}
                    </CardTitle>
                    <CardDescription>{t("billing.taxInfoDesc")}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <label htmlFor="vat-id" className="text-sm font-medium">
                        {t("billing.vatId")}
                      </label>
                      <input
                        id="vat-id"
                        type="text"
                        placeholder={t("billing.vatPlaceholder")}
                        disabled
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="billing-address" className="text-sm font-medium">
                        {t("billing.billingAddress")}
                      </label>
                      <textarea
                        id="billing-address"
                        rows={3}
                        placeholder={t("billing.billingAddressPlaceholder")}
                        disabled
                        className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="tax-cert" className="text-sm font-medium">
                        {t("billing.taxExemption")}
                      </label>
                      <div className="flex items-center gap-2">
                        <input
                          id="tax-cert"
                          type="file"
                          disabled
                          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Upload a PDF of your tax exemption certificate if applicable.
                      </p>
                    </div>
                    <Button disabled>Save Tax Information</Button>
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
                    <CardTitle className="text-base">Tax Settings</CardTitle>
                    <CardDescription>Configure how tax is applied to your invoices.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Callout variant="info">
                      Tax settings will be available in a future update. For now, all invoices include VAT at the standard rate for your billing country.
                    </Callout>
                    <div className="space-y-2">
                      <label htmlFor="country" className="text-sm font-medium">
                        Billing Country
                      </label>
                      <select
                        id="country"
                        disabled
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option>Romania</option>
                        <option>Germany</option>
                        <option>United Kingdom</option>
                        <option>United States</option>
                      </select>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </TabsContent>
        </Tabs>
      </SectionWrapper>
    </>
  )
}
