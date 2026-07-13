import { Helmet } from "react-helmet-async"
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
  ImageIcon,
  Truck,
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
      <Helmet>
        <title>Operion for Transport Companies — Route Optimization & Fleet Tracking</title>
        <meta
          name="description"
          content="Cut fuel costs and deliver on time with AI-powered routing, real-time GPS tracking, and automated dispatch for transport companies."
        />
        <link rel="canonical" href="https://operion.com/industries/transport" />
      </Helmet>

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

      {/* Screenshot */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="See It in Action"
          description="The Operion transport dashboard gives you complete visibility from dispatch to delivery."
          className="mb-8"
        />
        <ScreenshotPlaceholder name="Transport Dispatch Dashboard" />
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
