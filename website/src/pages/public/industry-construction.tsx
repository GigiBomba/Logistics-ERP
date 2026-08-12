import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import {
  Package,
  HardHat,
  Hammer,
  Truck,
  ClipboardList,
  CalendarClock,
  Anchor,
  Handshake,
  ArrowRight,
  Timer,
  TrendingDown,
  TrendingUp,
  CheckCircle2,
} from "lucide-react"
import { PageHeader, SectionHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { StatCard } from "@/components/shared/stat-card"
import { CtaBanner } from "@/components/shared/cta-banner"
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

function SiteBoardVisual() {
  const sites = [
    { name: "Site A — Residential", status: "active", deliveries: 3, next: "08:30", equipment: "Crane #2" },
    { name: "Site B — Office Park", status: "waiting", deliveries: 1, next: "10:00", equipment: "Mixer #1" },
    { name: "Site C — Highway", status: "active", deliveries: 5, next: "07:00", equipment: "Excavator #4" },
  ]
  return (
    <div className="mt-8 rounded-xl border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium">Site Coordination Board</span>
        <span className="text-xs text-muted-foreground">3 active sites</span>
      </div>
      <div className="space-y-3">
        {sites.map((site, i) => (
          <motion.div
            key={site.name}
            initial={{ opacity: 0, x: -10 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className="rounded-lg border p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className={`h-2 w-2 rounded-full ${site.status === "active" ? "bg-green-500" : "bg-amber-500"}`} />
                <span className="text-sm font-medium">{site.name}</span>
              </div>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${site.status === "active" ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300" : "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"}`}>
                {site.status}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
              <div className="rounded-md bg-muted/50 p-2">
                <p className="font-semibold text-foreground">{site.deliveries}</p>
                <p>Deliveries today</p>
              </div>
              <div className="rounded-md bg-muted/50 p-2">
                <p className="font-semibold text-foreground">{site.next}</p>
                <p>Next window</p>
              </div>
              <div className="rounded-md bg-muted/50 p-2">
                <p className="font-semibold text-foreground">{site.equipment}</p>
                <p>Equipment</p>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
      <div className="mt-4 rounded-lg bg-muted/40 p-3 flex items-center gap-2 text-xs text-muted-foreground">
        <HardHat className="h-3.5 w-3.5" />
        <span>All sites comply with today&apos;s safety checklist</span>
      </div>
    </div>
  )
}

const challenges = [
  {
    icon: Package,
    title: "Material Delivery",
    description: "Late or incorrect material deliveries stall crews and push project timelines into costly overruns.",
  },
  {
    icon: HardHat,
    title: "Site Coordination",
    description: "Multiple deliveries arriving uncoordinated create congestion, safety risks, and idle labor.",
  },
  {
    icon: Hammer,
    title: "Heavy Equipment",
    description: "Moving excavators, cranes, and mixers between sites requires permits, escorts, and precise timing.",
  },
  {
    icon: Truck,
    title: "Multiple Suppliers",
    description: "Managing dozens of suppliers with different lead times and delivery windows is a full-time job.",
  },
]

const solutions = [
  {
    icon: ClipboardList,
    title: "Material Tracking",
    description: "Track every pallet and load from supplier to site with real-time status and delivery confirmation.",
  },
  {
    icon: CalendarClock,
    title: "Site Scheduling",
    description: "Coordinate delivery windows with site readiness to prevent congestion and keep crews productive.",
  },
  {
    icon: Anchor,
    title: "Equipment Logistics",
    description: "Plan heavy equipment moves with route restrictions, permit tracking, and escort coordination.",
  },
  {
    icon: Handshake,
    title: "Supplier Coordination",
    description: "Centralize supplier communications, orders, and delivery schedules in one shared platform.",
  },
]

const workflow = [
  { step: "01", label: "Order Materials", desc: "Sync with project timeline" },
  { step: "02", label: "Schedule Delivery", desc: "Align with site readiness" },
  { step: "03", label: "Track Equipment", desc: "Permits & escorts managed" },
  { step: "04", label: "Site Receive", desc: "Confirm & sign off" },
  { step: "05", label: "Invoice", desc: "Auto-match to delivery" },
]

const stats = [
  { value: "40%", label: "Fewer Delays", icon: Timer, trend: { direction: "down" as const, value: "40%" } },
  { value: "22%", label: "Lower Transport Costs", icon: TrendingDown, trend: { direction: "down" as const, value: "22%" } },
  { value: "95%", label: "Site Accuracy", icon: CheckCircle2, trend: { direction: "up" as const, value: "8%" } },
  { value: "3x", label: "Faster Billing", icon: TrendingUp, trend: { direction: "up" as const, value: "3x" } },
]

export default function IndustryConstructionPage() {
  return (
    <>
      <SeoHead
        title="Operion for Construction Logistics — Site Coordination & Equipment"
        description="Coordinate material deliveries and heavy equipment across multiple sites without delays using Operion's construction logistics tools."
        canonical="https://operionerp.xyz/industries/construction"
      />

      <PageHeader
        title="Operion for Construction Logistics"
        description="Coordinate material deliveries and heavy equipment across multiple sites without delays."
      />

      {/* Challenges */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Industry Challenges"
          description="Construction logistics must align perfectly with project timelines, crew schedules, and safety requirements."
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
          description="Connect suppliers, schedules, and sites so projects stay on time and on budget."
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
          description="A typical construction material and equipment delivery cycle with Operion."
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
          description="Construction firms using Operion keep sites running smoothly and projects profitable."
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

      {/* Site Coordination Board */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="See It in Action"
          description="The construction logistics board shows every delivery, equipment move, and site status in real time."
          className="mb-8"
        />
        <SiteBoardVisual />
      </SectionWrapper>

      {/* CTA */}
      <SectionWrapper className="pb-8 md:pb-12">
        <CtaBanner
          title="Ready to transform your construction logistics?"
          description="Start your free trial and keep every site on schedule with coordinated deliveries."
          buttonText="Start Free Trial"
          buttonHref="/register"
        />
      </SectionWrapper>
    </>
  )
}
