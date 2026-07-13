import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import {
  Wrench,
  UserCheck,
  Radio,
  DollarSign,
  Bell,
  Gauge,
  MapPin,
  BarChart3,
  ArrowRight,
  ImageIcon,
  Timer,
} from "lucide-react"
import { PageHeader, SectionHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { StatCard } from "@/components/shared/stat-card"
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
    icon: Wrench,
    title: "Maintenance Scheduling",
    description: "Missed service intervals lead to breakdowns, expensive repairs, and vehicles off the road.",
  },
  {
    icon: UserCheck,
    title: "Driver Compliance",
    description: "Tracking tachograph hours, licenses, and certifications manually is error-prone and risky.",
  },
  {
    icon: Radio,
    title: "Vehicle Tracking",
    description: "Without live location data, you cannot respond to delays or verify driver routes.",
  },
  {
    icon: DollarSign,
    title: "Cost Control",
    description: "Spreadsheets hide the true cost of depreciation, fuel, and maintenance per vehicle.",
  },
]

const solutions = [
  {
    icon: Bell,
    title: "Maintenance Alerts",
    description: "Automated reminders for oil changes, inspections, and part replacements based on mileage or time.",
  },
  {
    icon: Gauge,
    title: "Tachograph Integration",
    description: "Download and analyze driver hours automatically to ensure legal compliance across your fleet.",
  },
  {
    icon: MapPin,
    title: "GPS Tracking",
    description: "Real-time location, geofencing, and route history for every asset in your fleet.",
  },
  {
    icon: BarChart3,
    title: "Expense Analytics",
    description: "Break down costs per vehicle, per route, and per driver to find savings and inefficiencies.",
  },
]

const workflow = [
  { step: "01", label: "Schedule", desc: "Auto-maintenance calendar" },
  { step: "02", label: "Monitor", desc: "Tacho & compliance checks" },
  { step: "03", label: "Track", desc: "Live GPS & geofencing" },
  { step: "04", label: "Review", desc: "Cost & performance reports" },
  { step: "05", label: "Optimize", desc: "Adjust fleet allocation" },
]

const stats = [
  { value: "30%", label: "Less Downtime", icon: Wrench, trend: { direction: "down" as const, value: "30%" } },
  { value: "100%", label: "Compliance Rate", icon: UserCheck, trend: { direction: "up" as const, value: "12%" } },
  { value: "15%", label: "Lower Fleet Costs", icon: DollarSign, trend: { direction: "down" as const, value: "15%" } },
  { value: "12h", label: "Faster Repairs", icon: Timer, trend: { direction: "down" as const, value: "12h" } },
]

export default function IndustryFleetPage() {
  return (
    <>
      <Helmet>
        <title>Operion for Fleet Managers — Maintenance, Compliance & Cost Control</title>
        <meta
          name="description"
          content="Keep every vehicle maintained, compliant, and profitable with unified fleet intelligence, GPS tracking, and automated maintenance alerts."
        />
        <link rel="canonical" href="https://operion.com/industries/fleet" />
      </Helmet>

      <PageHeader
        title="Operion for Fleet Managers"
        description="Keep every vehicle maintained, compliant, and profitable with unified fleet intelligence."
      />

      {/* Challenges */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Industry Challenges"
          description="Fleet managers balance safety, compliance, and profitability across dozens of moving assets."
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
          description="Proactive fleet management that prevents problems before they become expensive surprises."
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
          description="A proactive fleet management cycle with Operion."
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

      {/* Stats */}
      <SectionWrapper>
        <SectionHeader
          title="Key Benefits"
          description="Fleet managers using Operion report measurable improvements across uptime and cost."
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
            >
              <StatCard {...stat} />
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Screenshot */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="See It in Action"
          description="The fleet dashboard gives you health, location, and cost data for every asset at a glance."
          className="mb-8"
        />
        <ScreenshotPlaceholder name="Fleet Health Dashboard" />
      </SectionWrapper>

      {/* CTA */}
      <SectionWrapper className="pb-8 md:pb-12">
        <CtaBanner
          title="Ready to transform your fleet operations?"
          description="Start your free trial and replace reactive maintenance with proactive fleet intelligence."
          buttonText="Start Free Trial"
          buttonHref="/register"
        />
      </SectionWrapper>
    </>
  )
}
