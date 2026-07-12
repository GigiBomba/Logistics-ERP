import { Helmet } from "react-helmet-async"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { PageHeader } from "@/components/shared/page-header"
import { CTASection } from "@/components/shared/cta-section"
import { Card, CardContent } from "@/components/ui/card"
import { motion } from "motion/react"
import { Shield, Sparkles, Headset } from "lucide-react"

const beliefs = [
  {
    title: "Technology Should Empower, Not Complicate",
    description:
      "We design Operion to be powerful yet intuitive. You shouldn't need a degree in computer science to run your fleet efficiently.",
  },
  {
    title: "Efficiency Drives Sustainability",
    description:
      "Optimized routes mean less fuel consumption, fewer emissions, and a smaller carbon footprint. Good logistics is green logistics.",
  },
  {
    title: "Every Fleet Deserves Great Tools",
    description:
      "Whether you operate 5 vehicles or 500, you deserve software that works as hard as you do. We're democratizing enterprise logistics technology.",
  },
  {
    title: "Data-Driven Decisions Beat Gut Feelings",
    description:
      "We help you turn raw operational data into actionable insights. Stop guessing, start optimizing.",
  },
]

const stats = [
  {
    icon: Shield,
    value: "99.9%",
    label: "Uptime SLA",
  },
  {
    icon: Sparkles,
    value: "Monthly",
    label: "Feature Updates",
  },
  {
    icon: Headset,
    value: "24/7",
    label: "Customer Support",
  },
]

export default function MissionPage() {
  return (
    <div className="flex flex-col">
      <Helmet>
        <title>Our Mission - Operion ERP</title>
      </Helmet>

      {/* Header */}
      <SectionWrapper className="pb-0">
        <PageHeader
          title="Our Mission"
          description="Why we exist and what drives us every day."
        />
      </SectionWrapper>

      {/* Mission Statement */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-4xl text-center"
        >
          <div className="rounded-2xl bg-gradient-to-br from-primary/10 via-primary/5 to-transparent px-6 py-16 sm:px-12 sm:py-20">
            <h2 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl lg:text-5xl">
              To make enterprise logistics accessible, efficient, and
              sustainable for every fleet, everywhere.
            </h2>
          </div>
        </motion.div>
      </SectionWrapper>

      {/* What We Believe */}
      <SectionWrapper className="bg-muted/30">
        <PageHeader
          title="What We Believe"
          description="Our core convictions that shape everything we build."
          className="mb-8"
        />
        <div className="grid gap-6 sm:grid-cols-2">
          {beliefs.map((belief, i) => (
            <motion.div
              key={belief.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{
                duration: 0.5,
                delay: i * 0.1,
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              <Card className="h-full border-border/60 bg-card/50 backdrop-blur-sm">
                <CardContent className="p-6">
                  <h3 className="text-base font-semibold text-foreground">
                    {belief.title}
                  </h3>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    {belief.description}
                  </p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Our Commitment */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-3xl text-center"
        >
          <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Our Commitment
          </h2>
          <p className="mt-6 text-base leading-relaxed text-muted-foreground">
            We're committed to continuous improvement. Every month, we ship
            improvements based on real customer feedback. Our roadmap is public,
            our development process is transparent, and our success is measured
            by your success.
          </p>
        </motion.div>

        <div className="mt-10 grid gap-6 sm:grid-cols-3">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{
                duration: 0.5,
                delay: i * 0.1,
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              <Card className="text-center">
                <CardContent className="p-6">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <stat.icon className="h-6 w-6" />
                  </div>
                  <p className="mt-4 text-2xl font-bold text-foreground">
                    {stat.value}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {stat.label}
                  </p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* CTA */}
      <SectionWrapper>
        <CTASection
          title="Join Us on This Journey"
          description="Be part of the future of logistics. Start using Operion ERP today."
          primaryAction={{ label: "Get started", href: "/register" }}
        />
      </SectionWrapper>
    </div>
  )
}
