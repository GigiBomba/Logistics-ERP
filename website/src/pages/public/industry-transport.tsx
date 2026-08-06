import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import {
  Route,
  Users,
  Fuel,
  PackageSearch,
  Brain,
  Radio,
  BarChart3,
  Clock,
  ArrowRight,
  Truck,
  Timer,
} from "lucide-react"
import { PageHeader, SectionHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { StatCard } from "@/components/shared/stat-card"
import { CtaBanner } from "@/components/shared/cta-banner"
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

function DispatchBoardVisual() {
  const drivers = [
    { name: "Alex D.", status: "on-time", eta: "10:24" },
    { name: "Maria L.", status: "delayed", eta: "11:05" },
    { name: "Jonas K.", status: "on-time", eta: "09:45" },
    { name: "Sofia R.", status: "loading", eta: "12:00" },
  ]
  return (
    <div className="mt-8 rounded-xl border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm font-medium">Live Dispatch</span>
        </div>
        <span className="text-xs text-muted-foreground">4 active routes</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {drivers.map((d, i) => (
          <motion.div
            key={d.name}
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center justify-between rounded-lg border p-3"
          >
            <div className="flex items-center gap-3">
              <div className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold text-white ${d.status === "delayed" ? "bg-red-500" : d.status === "loading" ? "bg-amber-500" : "bg-green-600"}`}>
                {d.name.charAt(0)}
              </div>
              <div>
                <p className="text-sm font-medium">{d.name}</p>
                <p className="text-xs text-muted-foreground capitalize">{d.status}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm font-semibold">{d.eta}</p>
              <p className="text-xs text-muted-foreground">ETA</p>
            </div>
          </motion.div>
        ))}
      </div>
      <div className="mt-4 rounded-lg bg-muted/40 p-4">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
          <Route className="h-3.5 w-3.5" />
          <span>Route density — Bucharest hub</span>
        </div>
        <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            whileInView={{ width: "72%" }}
            viewport={{ once: true }}
            transition={{ duration: 1.2, ease: "easeOut" }}
            className="h-full rounded-full bg-primary/70"
          />
        </div>
      </div>
    </div>
  )
}

const challenges = [
  {
    icon: Route,
    title: "Route Inefficiency",
    description: "Static routes miss traffic patterns, causing wasted fuel and missed delivery windows.",
  },
  {
    icon: Users,
    title: "Driver Management",
    description: "Disorganized schedules and unclear communication lead to compliance risks and turnover.",
  },
  {
    icon: Fuel,
    title: "Rising Fuel Costs",
    description: "Without optimization, fuel becomes the fastest-growing line item in your budget.",
  },
  {
    icon: PackageSearch,
    title: "Delivery Tracking",
    description: "Customers demand real-time visibility, but manual updates create gaps and complaints.",
  },
]

const solutions = [
  {
    icon: Brain,
    title: "AI-Powered Routing",
    description: "Algorithms optimize for time, distance, and fuel simultaneously with live traffic data.",
  },
  {
    icon: Radio,
    title: "Fleet GPS Tracking",
    description: "Monitor every vehicle's location and status instantly on an interactive live map.",
  },
  {
    icon: BarChart3,
    title: "Fuel Analytics",
    description: "Track consumption patterns, identify inefficiencies, and cut fuel spend by up to 23%.",
  },
  {
    icon: Clock,
    title: "Real-Time ETAs",
    description: "Automatically update customers with accurate arrival times based on live conditions.",
  },
]

const workflow = [
  { step: "01", label: "Plan Route", desc: "AI optimizes multi-stop routes" },
  { step: "02", label: "Assign Driver", desc: "Match based on proximity & hours" },
  { step: "03", label: "Track Live", desc: "GPS updates every 30 seconds" },
  { step: "04", label: "Deliver", desc: "Capture proof of delivery" },
  { step: "05", label: "Analyze", desc: "Review performance & costs" },
]

const stats = [
  { value: "23%", label: "Fuel Cost Reduction", icon: Fuel, trend: { direction: "down" as const, value: "23%" } },
  { value: "18%", label: "More Deliveries/Day", icon: Truck, trend: { direction: "up" as const, value: "18%" } },
  { value: "94%", label: "On-Time Delivery Rate", icon: Timer, trend: { direction: "up" as const, value: "6%" } },
  { value: "40%", label: "Less Admin Time", icon: Clock, trend: { direction: "down" as const, value: "40%" } },
]

export default function IndustryTransportPage() {
  return (
    <>
      <SeoHead
        title="Operion for Transport Companies — Route Optimization & Fleet Tracking"
        description="Cut fuel costs and deliver on time with AI-powered routing, real-time GPS tracking, and automated dispatch for transport companies."
        canonical="https://operionerp.xyz/industries/transport"
      />

      <PageHeader
        title="Operion for Transport Companies"
        description="Cut fuel costs and deliver on time with AI-powered routing and real-time fleet visibility."
      />

      {/* Challenges */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Industry Challenges"
          description="Transport companies face daily pressure to move more freight with fewer resources."
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
          description="Purpose-built tools that turn daily transport chaos into predictable, profitable operations."
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
          description="A typical day using Operion in a transport operation."
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
          description="Real results from transport companies using Operion daily."
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

      {/* Live Dispatch Board */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="See It in Action"
          description="The Operion transport dashboard gives you complete visibility from dispatch to delivery."
          className="mb-8"
        />
        <DispatchBoardVisual />
      </SectionWrapper>

      {/* CTA */}
      <SectionWrapper className="pb-8 md:pb-12">
        <CtaBanner
          title="Ready to transform your transport operations?"
          description="Start your free trial and see how AI routing and real-time tracking cut costs from day one."
          buttonText="Start Free Trial"
          buttonHref="/register"
        />
      </SectionWrapper>
    </>
  )
}
