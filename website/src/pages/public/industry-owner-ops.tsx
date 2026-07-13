import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import {
  Receipt,
  Wallet,
  Search,
  FolderOpen,
  FileCheck,
  PiggyBank,
  PackageSearch,
  HardDrive,
  ArrowRight,
  ImageIcon,
  Zap,
  TrendingUp,
  DollarSign,
} from "lucide-react"
import { PageHeader, SectionHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { CtaBanner } from "@/components/shared/cta-banner"
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

function ScreenshotPlaceholder({ name }: { name: string }) {
  return (
    <div className="mt-8 rounded-xl border border-dashed bg-muted/30 p-10 text-center">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-muted">
        <ImageIcon className="h-7 w-7 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium text-muted-foreground">Screenshot: {name}</p>
      <p className="mt-1 text-xs text-muted-foreground/70">Preview coming soon</p>
    </div>
  )
}

const challenges = [
  {
    icon: Receipt,
    title: "Invoicing",
    description: "Creating and chasing invoices manually steals hours you could spend on the road earning.",
  },
  {
    icon: Wallet,
    title: "Expense Tracking",
    description: "Fuel, tolls, and maintenance receipts pile up, making tax season a stressful scramble.",
  },
  {
    icon: Search,
    title: "Load Finding",
    description: "Hours on load boards and broker calls mean less time driving and more time waiting.",
  },
  {
    icon: FolderOpen,
    title: "Compliance",
    description: "Organizing licenses, insurance, and permits without a system leads to missed renewals.",
  },
]

const solutions = [
  {
    icon: FileCheck,
    title: "Invoice Automation",
    description: "Generate professional invoices from delivery data in one tap and send them instantly.",
  },
  {
    icon: PiggyBank,
    title: "Expense Management",
    description: "Log fuel, tolls, and repairs on the go. Categorize everything for clean tax reporting.",
  },
  {
    icon: PackageSearch,
    title: "Load Matching",
    description: "See available loads matched to your route, capacity, and preferences in real time.",
  },
  {
    icon: HardDrive,
    title: "Document Storage",
    description: "Store licenses, insurance cards, and permits in one secure cloud archive with expiry alerts.",
  },
]

const workflow = [
  { step: "01", label: "Find Load", desc: "Matched to your route" },
  { step: "02", label: "Book Trip", desc: "Confirm & get details" },
  { step: "03", label: "Track Expenses", desc: "Log fuel & tolls live" },
  { step: "04", label: "Auto-Invoice", desc: "Generate on delivery" },
  { step: "05", label: "Get Paid", desc: "Faster with digital docs" },
]

const benefits = [
  {
    icon: Zap,
    title: "Faster Invoicing",
    description: "Generate professional invoices from delivery data in one tap and send them instantly — no more chasing paperwork.",
  },
  {
    icon: TrendingUp,
    title: "More Loads/Month",
    description: "See available loads matched to your route, capacity, and preferences so you spend less time hunting and more time hauling.",
  },
  {
    icon: DollarSign,
    title: "Faster Payments",
    description: "Digital invoices and proof-of-delivery documents help brokers process payments without delays or disputes.",
  },
  {
    icon: Wallet,
    title: "Money Saved",
    description: "Track fuel, tolls, and maintenance expenses on the go with auto-categorization for clean tax reporting and fewer surprises.",
  },
]

export default function IndustryOwnerOpsPage() {
  return (
    <>
      <Helmet>
        <title>Operion for Owner-Operators — Invoicing, Expenses & Load Matching</title>
        <meta
          name="description"
          content="Run your one-person business like a full dispatch office with automated invoicing, expense tracking, and load matching."
        />
        <link rel="canonical" href="https://operion.com/industries/owner-operators" />
      </Helmet>

      <PageHeader
        title="Operion for Owner-Operators"
        description="Run your one-person business like a full dispatch office without the overhead."
      />

      {/* Challenges */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Industry Challenges"
          description="Owner-operators do it all — driving, bookkeeping, and load hunting — often with nothing but a phone and a notebook."
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {challenges.map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
            >
              <Card className="h-full">
                <CardHeader>
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-lg">{item.title}</CardTitle>
                  <CardDescription className="text-sm leading-relaxed">{item.description}</CardDescription>
                </CardHeader>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Solutions */}
      <SectionWrapper>
        <SectionHeader
          title="How Operion Helps"
          description="Tools built for solo operators who need enterprise power without enterprise complexity."
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {solutions.map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
            >
              <Card className="group h-full transition-shadow hover:shadow-md">
                <CardHeader>
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 transition-colors group-hover:bg-emerald-600 group-hover:text-white dark:bg-emerald-950 dark:text-emerald-300">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-lg">{item.title}</CardTitle>
                  <CardDescription className="text-sm leading-relaxed">{item.description}</CardDescription>
                </CardHeader>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Workflow */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Workflow Example"
          description="A complete trip lifecycle for an owner-operator using Operion."
          className="mb-12"
        />
        <div className="flex flex-wrap items-start justify-center gap-4">
          {workflow.map((step, i) => (
            <motion.div
              key={step.step}
              initial={{ opacity: 0, x: -10 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.3, delay: i * 0.1 }}
              className="flex items-center gap-4"
            >
              <div className="flex flex-col items-center text-center">
                <Badge variant="outline" className="mb-2 text-xs font-mono">
                  {step.step}
                </Badge>
                <div className="rounded-xl border bg-card p-4 shadow-sm min-w-[140px]">
                  <p className="text-sm font-semibold">{step.label}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{step.desc}</p>
                </div>
              </div>
              {i < workflow.length - 1 && (
                <ArrowRight className="hidden h-4 w-4 text-muted-foreground lg:block" />
              )}
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Benefits */}
      <SectionWrapper>
        <SectionHeader
          title="Key Benefits"
          description="How owner-operators benefit from tools that simplify paperwork and streamline operations."
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {benefits.map((benefit, i) => (
            <motion.div
              key={benefit.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
            >
              <Card className="h-full">
                <CardHeader>
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                    <benefit.icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-lg">{benefit.title}</CardTitle>
                  <CardDescription className="text-sm leading-relaxed">{benefit.description}</CardDescription>
                </CardHeader>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Screenshot */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="See It in Action"
          description="The owner-operator mobile app puts dispatch, invoicing, and expenses in your pocket."
          className="mb-8"
        />
        <ScreenshotPlaceholder name="Owner-Operator Mobile App" />
      </SectionWrapper>

      {/* CTA */}
      <SectionWrapper className="pb-8 md:pb-12">
        <CtaBanner
          title="Ready to transform your owner-operator business?"
          description="Start your free trial and get back on the road with less paperwork and more profit."
          buttonText="Start Free Trial"
          buttonHref="/register"
        />
      </SectionWrapper>
    </>
  )
}
