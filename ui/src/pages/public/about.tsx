import { Helmet } from "react-helmet-async"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { PageHeader } from "@/components/shared/page-header"
import { FeatureCard } from "@/components/shared/feature-card"
import { motion } from "motion/react"
import {
  HeartHandshake,
  Shield,
  Lightbulb,
  Eye,
  Lock,
  Handshake,
} from "lucide-react"

const values = [
  {
    icon: HeartHandshake,
    title: "Customer First",
    description:
      "Every feature we build starts with real customer needs. We listen, we learn, and we deliver.",
  },
  {
    icon: Shield,
    title: "Reliability",
    description:
      "Your operations depend on our software. We maintain 99.9% uptime and rigorous testing standards.",
  },
  {
    icon: Lightbulb,
    title: "Innovation",
    description:
      "We invest heavily in R&D to bring cutting-edge AI and optimization technology to the logistics industry.",
  },
  {
    icon: Eye,
    title: "Transparency",
    description:
      "Clear pricing, honest communication, and no hidden fees. What you see is what you get.",
  },
  {
    icon: Lock,
    title: "Security",
    description:
      "Enterprise-grade encryption, SOC 2 compliance, and regular security audits protect your data.",
  },
  {
    icon: Handshake,
    title: "Partnership",
    description:
      "We don't just sell software — we partner with our customers to help them succeed.",
  },
]

export default function AboutPage() {
  return (
    <div className="flex flex-col">
      <Helmet>
        <title>About - Operion ERP</title>
      </Helmet>

      {/* Header */}
      <SectionWrapper className="pb-0">
        <PageHeader
          title="About Operion"
          description="We're building the future of enterprise logistics software."
        />
      </SectionWrapper>

      {/* Our Story */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-3xl"
        >
          <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Our Story
          </h2>
          <div className="mt-6 space-y-4 text-base leading-relaxed text-muted-foreground">
            <p>
              Operion was founded in 2024 with a clear mission: to make
              enterprise-grade logistics software accessible to fleets of every
              size. We saw that existing solutions were either too complex and
              expensive for mid-sized operators, or too simplistic to handle
              real-world logistics challenges. Operion bridges that gap —
              providing powerful, intuitive tools that grow with your business.
            </p>
          </div>
        </motion.div>
      </SectionWrapper>

      {/* Our Values */}
      <SectionWrapper className="bg-muted/30">
        <PageHeader
          title="Our Values"
          description="The principles that guide every decision we make."
          className="mb-8 text-center"
        />
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {values.map((value, i) => (
            <FeatureCard
              key={value.title}
              icon={value.icon}
              title={value.title}
              description={value.description}
              index={i}
            />
          ))}
        </div>
      </SectionWrapper>

      {/* Team */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-3xl text-center"
        >
          <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Our Team
          </h2>
          <p className="mt-6 text-base leading-relaxed text-muted-foreground">
            Our team combines decades of experience in logistics, software
            engineering, and AI. We're headquartered in Europe with team members
            across the continent.
          </p>
        </motion.div>
      </SectionWrapper>
    </div>
  )
}
