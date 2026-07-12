import { SectionWrapper } from "@/components/shared/section-wrapper"
import { PageHeader } from "@/components/shared/page-header"
import { FeatureCard } from "@/components/shared/feature-card"
import { CTASection } from "@/components/shared/cta-section"
import { Badge } from "@/components/ui/badge"
import { motion } from "motion/react"
import {
  BarChart3,
  Users,
  Zap,
  Shield,
  Globe,
  Layers,
} from "lucide-react"

const features = [
  {
    icon: BarChart3,
    title: "Real-time Analytics",
    description:
      "Track every metric that matters with live dashboards and customizable reports.",
  },
  {
    icon: Users,
    title: "Team Collaboration",
    description:
      "Work together seamlessly with role-based access and shared workspaces.",
  },
  {
    icon: Zap,
    title: "Workflow Automation",
    description:
      "Eliminate repetitive tasks with smart triggers and automated pipelines.",
  },
  {
    icon: Shield,
    title: "Enterprise Security",
    description:
      "SOC 2 compliant with end-to-end encryption and advanced access controls.",
  },
  {
    icon: Globe,
    title: "Global Operations",
    description:
      "Multi-currency, multi-language, and multi-entity support out of the box.",
  },
  {
    icon: Layers,
    title: "Modular Architecture",
    description:
      "Pick the modules you need and scale up as your business grows.",
  },
]

export default function HomePage() {
  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="relative overflow-hidden px-4 py-24 sm:px-6 sm:py-32 lg:px-8">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          >
            <Badge variant="default" className="mb-6">
              Now in public beta
            </Badge>
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
            className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl lg:text-6xl"
          >
            Enterprise resource planning,
            <br />
            <span className="text-primary">reimagined.</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground"
          >
            Operion helps modern teams manage inventory, finance, and operations
            in one unified platform. Built for scale, designed for clarity.
          </motion.p>
        </div>
      </section>

      {/* Features */}
      <SectionWrapper className="bg-muted/30">
        <PageHeader
          title="Everything you need"
          description="A complete toolkit for running your business operations with confidence."
          className="text-center"
        />
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature, i) => (
            <FeatureCard
              key={feature.title}
              icon={feature.icon}
              title={feature.title}
              description={feature.description}
              index={i}
            />
          ))}
        </div>
      </SectionWrapper>

      {/* CTA */}
      <SectionWrapper>
        <CTASection
          title="Ready to streamline your operations?"
          description="Join thousands of teams already using Operion to run their business smarter."
          primaryAction={{ label: "Start free trial", href: "/signup" }}
          secondaryAction={{ label: "View pricing", href: "/pricing" }}
        />
      </SectionWrapper>
    </div>
  )
}
