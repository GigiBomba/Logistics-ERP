import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import {
  CalendarDays,
  Thermometer,
  MapPinOff,
  Tractor,
  Maximize2,
  Snowflake,
  Route,
  Wrench,
  ArrowRight,
  Leaf,
  TrendingUp,
  Fuel,
  ShieldCheck,
} from "lucide-react"
import { PageHeader, SectionHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { StatCard } from "@/components/shared/stat-card"
import { CtaBanner } from "@/components/shared/cta-banner"
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

function SeasonalTimelineVisual() {
  const months = [
    { label: "Mar", event: "Planting", active: false },
    { label: "Apr", event: "Spray", active: false },
    { label: "May", event: "Growth", active: false },
    { label: "Jun", event: "Prep", active: true },
    { label: "Jul", event: "Harvest", active: true },
    { label: "Aug", event: "Peak", active: true },
    { label: "Sep", event: "Storage", active: false },
    { label: "Oct", event: "Delivery", active: false },
  ]
  return (
    <div className="mt-8 rounded-xl border bg-card p-6 shadow-sm space-y-6">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Seasonal Logistics Calendar</span>
        <span className="text-xs text-muted-foreground">2026 cycle</span>
      </div>
      <div className="relative">
        <div className="absolute left-0 right-0 top-1/2 h-0.5 bg-muted -translate-y-1/2" />
        <div className="relative flex justify-between">
          {months.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.06 }}
              className="flex flex-col items-center gap-2"
            >
              <div className={`h-3 w-3 rounded-full border-2 ${m.active ? "border-amber-500 bg-amber-500" : "border-muted bg-background"}`} />
              <span className={`text-xs font-medium ${m.active ? "text-amber-700 dark:text-amber-300" : "text-muted-foreground"}`}>{m.label}</span>
              <span className={`text-[10px] ${m.active ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground/60"}`}>{m.event}</span>
            </motion.div>
          ))}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 }}
          className="rounded-lg border p-3"
        >
          <div className="flex items-center gap-2 mb-1">
            <Snowflake className="h-4 w-4 text-blue-500" />
            <span className="text-xs font-medium">Cold Chain</span>
          </div>
          <p className="text-xs text-muted-foreground">2°C to 6°C maintained across 340 km route</p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.4 }}
          className="rounded-lg border p-3"
        >
          <div className="flex items-center gap-2 mb-1">
            <Route className="h-4 w-4 text-primary" />
            <span className="text-xs font-medium">Rural Routes</span>
          </div>
          <p className="text-xs text-muted-foreground">Unpaved road weight limits auto-applied</p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.5 }}
          className="rounded-lg border p-3"
        >
          <div className="flex items-center gap-2 mb-1">
            <Tractor className="h-4 w-4 text-amber-600" />
            <span className="text-xs font-medium">Equipment</span>
          </div>
          <p className="text-xs text-muted-foreground">Harvesters synced to delivery windows</p>
        </motion.div>
      </div>
    </div>
  )
}

const challenges = [
  {
    icon: CalendarDays,
    title: "Seasonal Peaks",
    description: "Harvest and planting seasons create sudden spikes in volume that overwhelm planning systems.",
  },
  {
    icon: Thermometer,
    title: "Perishable Goods",
    description: "Temperature-sensitive produce loses value with every minute of delay or improper handling.",
  },
  {
    icon: MapPinOff,
    title: "Rural Routes",
    description: "Poor road data and limited connectivity make route planning for remote farms unreliable.",
  },
  {
    icon: Tractor,
    title: "Equipment Tracking",
    description: "Harvesters, trailers, and trucks move between fields and storage without central visibility.",
  },
]

const solutions = [
  {
    icon: Maximize2,
    title: "Seasonal Scaling",
    description: "Scale routes, vehicles, and drivers up or down instantly to match harvest and planting cycles.",
  },
  {
    icon: Snowflake,
    title: "Temperature Monitoring",
    description: "Integrate IoT sensors to monitor cold chain integrity from field to processing facility.",
  },
  {
    icon: Route,
    title: "Rural Route Optimization",
    description: "Specialized algorithms account for unpaved roads, weight limits, and seasonal access changes.",
  },
  {
    icon: Wrench,
    title: "Equipment Management",
    description: "Track tractors, trailers, and harvesters with maintenance schedules tied to usage hours.",
  },
]

const workflow = [
  { step: "01", label: "Harvest Schedule", desc: "Sync with crop calendar" },
  { step: "02", label: "Route Plan", desc: "Rural-optimized paths" },
  { step: "03", label: "Monitor Temp", desc: "Cold chain alerts live" },
  { step: "04", label: "Delivery", desc: "To market or processor" },
  { step: "05", label: "Traceability", desc: "Full chain of custody" },
]

const stats = [
  { value: "12%", label: "Less Spoilage", icon: Leaf, trend: { direction: "down" as const, value: "12%" } },
  { value: "30%", label: "Faster Harvest Delivery", icon: TrendingUp, trend: { direction: "up" as const, value: "30%" } },
  { value: "25%", label: "Fuel Savings", icon: Fuel, trend: { direction: "down" as const, value: "25%" } },
  { value: "100%", label: "Traceability", icon: ShieldCheck, trend: { direction: "up" as const, value: "100%" } },
]

export default function IndustryAgriculturePage() {
  return (
    <>
      <SeoHead
        title="Operion for Agriculture Logistics — Seasonal Scaling & Cold Chain"
        description="Move perishable goods from farm to market with precision timing, temperature monitoring, and rural route optimization."
        canonical="https://operionerp.xyz/industries/agriculture"
      />

      <PageHeader
        title="Operion for Agriculture Logistics"
        description="Move perishable goods from farm to market with precision timing and full traceability."
      />

      {/* Challenges */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Industry Challenges"
          description="Agriculture logistics operate on nature's schedule, with narrow windows and zero tolerance for spoilage."
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
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
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
          description="Built for the realities of farm-to-market logistics: seasonal bursts, rural roads, and perishable cargo."
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
          description="From harvest to market shelf with full visibility and temperature control."
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
          description="Agriculture logistics teams using Operion protect product quality and farm profitability."
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

      {/* Seasonal Timeline */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="See It in Action"
          description="The agriculture dashboard connects harvest schedules, routes, and cold chain data in one view."
          className="mb-8"
        />
        <SeasonalTimelineVisual />
      </SectionWrapper>

      {/* CTA */}
      <SectionWrapper className="pb-8 md:pb-12">
        <CtaBanner
          title="Ready to transform your agriculture operations?"
          description="Start your free trial and protect every harvest with smarter logistics."
          buttonText="Start Free Trial"
          buttonHref="/register"
        />
      </SectionWrapper>
    </>
  )
}
