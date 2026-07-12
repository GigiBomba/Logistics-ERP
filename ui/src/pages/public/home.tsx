import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { Link } from "react-router-dom"
import {
  MapPin,
  Radio,
  Send,
  Scan,
  BarChart3,
  Users,
  DollarSign,
  Truck,
  FileText,
  Shield,
  ArrowRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { FeatureCard } from "@/components/shared/feature-card"
import { TestimonialCard } from "@/components/shared/testimonial-card"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { CTASection } from "@/components/shared/cta-section"

const features = [
  {
    icon: MapPin,
    title: "Intelligent Route Planning",
    description:
      "Optimize routes in seconds with advanced algorithms that consider traffic, distance, and delivery windows.",
  },
  {
    icon: Radio,
    title: "Real-Time Fleet Tracking",
    description:
      "Monitor every vehicle in your fleet with live GPS tracking and instant status updates.",
  },
  {
    icon: Send,
    title: "Smart Dispatch",
    description:
      "Assign jobs automatically based on driver availability, proximity, and vehicle capacity.",
  },
  {
    icon: Scan,
    title: "OCR Document Processing",
    description:
      "Scan and digitize invoices, CMR documents, and receipts instantly with AI-powered OCR.",
  },
  {
    icon: BarChart3,
    title: "Advanced Analytics",
    description:
      "Gain actionable insights with customizable dashboards, reports, and KPI tracking.",
  },
  {
    icon: Users,
    title: "Driver Management",
    description:
      "Manage driver profiles, certifications, hours, and performance from a single dashboard.",
  },
]

const benefits = [
  {
    icon: DollarSign,
    title: "Reduce Operational Costs",
    description:
      "Cut fuel consumption by up to 20% with optimized routing and reduced idle time.",
  },
  {
    icon: Truck,
    title: "Increase Delivery Speed",
    description:
      "Complete more deliveries per day with intelligent job assignment and route optimization.",
  },
  {
    icon: FileText,
    title: "Eliminate Paperwork",
    description:
      "Digitize all documents with OCR. No more manual data entry or lost paperwork.",
  },
  {
    icon: Shield,
    title: "Scale With Confidence",
    description:
      "From 5 vehicles to 500, Operion grows with your business without complexity.",
  },
]

const testimonials = [
  {
    quote:
      "Operion transformed our operations. We saw a 30% improvement in delivery efficiency within the first three months. The route optimization alone saved us thousands in fuel costs.",
    author: "Andrei M.",
    role: "Operations Director",
    company: "TransLogistica",
  },
  {
    quote:
      "Having real-time visibility into our entire fleet has been a game changer. We can now respond to issues instantly and keep our customers informed at every step.",
    author: "Maria P.",
    role: "Fleet Manager",
    company: "EuroFleet",
  },
  {
    quote:
      "We scaled from 10 to 50 vehicles without adding a single dispatcher. Operion\u2019s smart dispatch and automation made it possible. It\u2019s like having an extra team member.",
    author: "Victor D.",
    role: "CEO",
    company: "CargoSpeed",
  },
]

export default function HomePage() {
  return (
    <div className="flex flex-col">
      <Helmet>
        <title>Operion ERP — Enterprise Logistics, Simplified</title>
      </Helmet>

      {/* Hero Section */}
      <section className="relative overflow-hidden px-4 py-24 sm:px-6 sm:py-32 lg:px-8">
        {/* Animated gradient background */}
        <div className="absolute inset-0 bg-gradient-to-b from-primary/10 via-primary/5 to-background" />
        <motion.div
          className="absolute inset-0 bg-gradient-to-b from-primary/5 via-primary/[0.08] to-background"
          animate={{ opacity: [0, 1, 0] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-primary/[0.08] via-transparent to-transparent" />
        <motion.div
          className="absolute -left-40 -top-40 h-80 w-80 rounded-full bg-primary/10 blur-3xl"
          animate={{ scale: [1, 1.15, 1], opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute -bottom-40 -right-40 h-80 w-80 rounded-full bg-primary/5 blur-3xl"
          animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut", delay: 2 }}
        />

        <div className="relative mx-auto max-w-4xl text-center">
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl lg:text-6xl"
          >
            Enterprise Logistics,{" "}
            <span className="text-primary">Simplified</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.6,
              delay: 0.15,
              ease: [0.22, 1, 0.36, 1],
            }}
            className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl"
          >
            Operion ERP gives your fleet the power of intelligent route planning,
            real-time dispatch, and complete operational visibility — all from
            one platform.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.6,
              delay: 0.3,
              ease: [0.22, 1, 0.36, 1],
            }}
            className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row"
          >
            <Button asChild size="lg">
              <Link to="/register">
                Start Free Trial
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link to="/features">See How It Works</Link>
            </Button>
          </motion.div>
        </div>
      </section>

      {/* Feature Highlights */}
      <SectionWrapper className="bg-muted/30">
        <div className="mx-auto max-w-3xl text-center">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl"
          >
            Everything you need to run your fleet
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
            className="mt-4 text-lg text-muted-foreground"
          >
            Powerful tools that work together to streamline every aspect of your
            logistics operation.
          </motion.p>
        </div>
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

      {/* Benefits Section */}
      <SectionWrapper>
        <div className="mx-auto max-w-3xl text-center">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl"
          >
            Built for real logistics results
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
            className="mt-4 text-lg text-muted-foreground"
          >
            Every feature is designed to solve the challenges that logistics
            companies face every day.
          </motion.p>
        </div>
        <div className="mt-12 grid gap-8 sm:grid-cols-2">
          {benefits.map((benefit, i) => (
            <motion.div
              key={benefit.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{
                duration: 0.5,
                delay: i * 0.1,
                ease: [0.22, 1, 0.36, 1],
              }}
              className="flex gap-4"
            >
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <benefit.icon className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-foreground">
                  {benefit.title}
                </h3>
                <p className="mt-1 text-muted-foreground">
                  {benefit.description}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Testimonials */}
      <SectionWrapper className="bg-muted/30">
        <div className="mx-auto max-w-3xl text-center">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl"
          >
            Trusted by logistics leaders
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
            className="mt-4 text-lg text-muted-foreground"
          >
            See how Operion is helping companies transform their fleet
            operations.
          </motion.p>
        </div>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {testimonials.map((testimonial, i) => (
            <TestimonialCard
              key={testimonial.author}
              quote={testimonial.quote}
              author={testimonial.author}
              role={testimonial.role}
              company={testimonial.company}
              index={i}
            />
          ))}
        </div>
      </SectionWrapper>

      {/* Mission Summary */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-3xl text-center"
        >
          <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Our Mission
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
            Our mission is to make enterprise logistics accessible, efficient,
            and sustainable. We believe that powerful technology should be
            available to every fleet, not just the largest corporations.
          </p>
        </motion.div>
      </SectionWrapper>

      {/* Footer CTA */}
      <SectionWrapper>
        <CTASection
          title="Ready to Transform Your Logistics?"
          description="Join hundreds of companies that trust Operion to power their fleet operations."
          primaryAction={{ label: "Start Free Trial", href: "/register" }}
          secondaryAction={{ label: "Talk to Sales", href: "/contact" }}
        />
      </SectionWrapper>
    </div>
  )
}
