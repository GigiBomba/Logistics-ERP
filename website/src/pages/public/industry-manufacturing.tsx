import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import {
  Link2,
  Boxes,
  Clock,
  Building2,
  Eye,
  PackageCheck,
  Route,
  Network,
  ArrowRight,
  TrendingUp,
  Timer,
  Recycle,
} from "lucide-react"
import { PageHeader, SectionHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { CtaBanner } from "@/components/shared/cta-banner"
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

function SupplyChainVisual() {
  const steps = [
    { icon: Boxes, label: "Demand Signal", desc: "Production plan triggers replenishment", color: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300" },
    { icon: PackageCheck, label: "Inventory Check", desc: "Auto-sync stock levels across warehouses", color: "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300" },
    { icon: Route, label: "JIT Routing", desc: "Time-window constrained last-mile routes", color: "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300" },
    { icon: Network, label: "Delivery", desc: "To line or warehouse dock on schedule", color: "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300" },
    { icon: Building2, label: "Production", desc: "Continuous flow maintained", color: "bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-950 dark:text-fuchsia-300" },
  ]
  return (
    <div className="mt-8 rounded-xl border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between mb-6">
        <span className="text-sm font-medium">Supply Chain Flow</span>
        <span className="text-xs text-muted-foreground">Live synchronization</span>
      </div>
      <div className="flex flex-wrap items-start justify-center gap-3">
        {steps.map((step, i) => {
          const Icon = step.icon
          return (
            <div key={step.label} className="flex items-center gap-3">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="flex flex-col items-center text-center min-w-[120px]"
              >
                <div className={`mb-2 flex h-10 w-10 items-center justify-center rounded-lg ${step.color}`}>
                  <Icon className="h-5 w-5" />
                </div>
                <p className="text-xs font-semibold">{step.label}</p>
                <p className="text-[10px] text-muted-foreground max-w-[120px]">{step.desc}</p>
              </motion.div>
              {i < steps.length - 1 && (
                <ArrowRight className="hidden h-4 w-4 text-muted-foreground md:block mt-[-12px]" />
              )}
            </div>
          )
        })}
      </div>
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.5 }}
          className="rounded-lg border p-3 text-center"
        >
          <p className="text-lg font-bold">12</p>
          <p className="text-xs text-muted-foreground">Active inbound routes</p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.6 }}
          className="rounded-lg border p-3 text-center"
        >
          <p className="text-lg font-bold">98.2%</p>
          <p className="text-xs text-muted-foreground">On-time to dock</p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.7 }}
          className="rounded-lg border p-3 text-center"
        >
          <p className="text-lg font-bold">3</p>
          <p className="text-xs text-muted-foreground">Facilities synced</p>
        </motion.div>
      </div>
    </div>
  )
}

const challenges = [
  {
    icon: Link2,
    title: "Supply Chain Visibility",
    description: "Silos between suppliers, warehouses, and production floors create blind spots and buffer stock bloat.",
  },
  {
    icon: Boxes,
    title: "Inventory Management",
    description: "Overstock ties up capital; understock stops production lines. Both are expensive mistakes.",
  },
  {
    icon: Clock,
    title: "Just-in-Time Delivery",
    description: "JIT demands precise timing. A single late delivery can halt an entire production shift.",
  },
  {
    icon: Building2,
    title: "Multi-Facility Coordination",
    description: "Coordinating inbound and outbound logistics across plants, warehouses, and distribution centers is complex.",
  },
]

const solutions = [
  {
    icon: Eye,
    title: "Supply Chain Visibility",
    description: "Real-time dashboards show supplier status, inbound shipments, and warehouse levels across your network.",
  },
  {
    icon: PackageCheck,
    title: "Inventory Integration",
    description: "Sync stock levels with logistics automatically so replenishment triggers without manual orders.",
  },
  {
    icon: Route,
    title: "JIT Routing",
    description: "Optimize last-mile routes to production lines with time-window constraints and dock scheduling.",
  },
  {
    icon: Network,
    title: "Multi-Site Management",
    description: "Manage routes, vehicles, and deliveries across multiple facilities from a single unified platform.",
  },
]

const workflow = [
  { step: "01", label: "Demand Signal", desc: "Production plan triggers" },
  { step: "02", label: "Inventory Check", desc: "Auto-sync stock levels" },
  { step: "03", label: "Route Optimize", desc: "JIT window routing" },
  { step: "04", label: "JIT Delivery", desc: "To line or warehouse" },
  { step: "05", label: "Production Line", desc: "Continuous flow maintained" },
]

const benefits = [
  {
    icon: Boxes,
    title: "Inventory Reduction",
    description: "Sync stock levels with logistics automatically so replenishment triggers without manual orders or buffer stock.",
  },
  {
    icon: TrendingUp,
    title: "Faster Throughput",
    description: "Optimize last-mile routes to production lines with time-window constraints and dock scheduling.",
  },
  {
    icon: Timer,
    title: "On-Time Delivery",
    description: "JIT routing and real-time tracking help maintain precise delivery windows to keep production lines running.",
  },
  {
    icon: Recycle,
    title: "Less Waste",
    description: "Reduce overstock and emergency shipments by connecting demand signals directly to inbound logistics.",
  },
]

export default function IndustryManufacturingPage() {
  return (
    <>
      <SeoHead
        title="Operion for Manufacturing Logistics — JIT & Multi-Site Management"
        description="Connect suppliers, warehouses, and production lines with synchronized just-in-time delivery and multi-site logistics management."
        canonical="https://operionerp.xyz/industries/manufacturing"
      />

      <PageHeader
        title="Operion for Manufacturing Logistics"
        description="Connect suppliers, warehouses, and production lines with synchronized just-in-time delivery."
      />

      {/* Challenges */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Industry Challenges"
          description="Manufacturing logistics must balance minimal inventory with maximum uptime across a distributed supply network."
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
          description="Unify your supply chain from raw material inbound to finished goods outbound with precision routing."
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
          description="A synchronized manufacturing supply cycle from demand signal to production line."
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
          description="How manufacturers benefit from synchronized logistics and multi-site coordination."
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

      {/* Supply Chain Flow */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="See It in Action"
          description="The manufacturing supply dashboard connects demand, inventory, and inbound logistics in one synchronized view."
          className="mb-8"
        />
        <SupplyChainVisual />
      </SectionWrapper>

      {/* CTA */}
      <SectionWrapper className="pb-8 md:pb-12">
        <CtaBanner
          title="Ready to transform your manufacturing operations?"
          description="Start your free trial and synchronize your supply chain from supplier to production line."
          buttonText="Start Free Trial"
          buttonHref="/register"
        />
      </SectionWrapper>
    </>
  )
}
