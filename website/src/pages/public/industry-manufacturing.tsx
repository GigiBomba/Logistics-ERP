import { Helmet } from "react-helmet-async"
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
  ImageIcon,
  TrendingUp,
  Timer,
  Recycle,
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
      <Helmet>
        <title>Operion for Manufacturing Logistics — JIT & Multi-Site Management</title>
        <meta
          name="description"
          content="Connect suppliers, warehouses, and production lines with synchronized just-in-time delivery and multi-site logistics management."
        />
        <link rel="canonical" href="https://operion.com/industries/manufacturing" />
      </Helmet>

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

      {/* Screenshot */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="See It in Action"
          description="The manufacturing supply dashboard connects demand, inventory, and inbound logistics in one synchronized view."
          className="mb-8"
        />
        <ScreenshotPlaceholder name="Manufacturing Supply Dashboard" />
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
