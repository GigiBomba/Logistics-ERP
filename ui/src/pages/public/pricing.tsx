import { Helmet } from "react-helmet-async"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { PageHeader } from "@/components/shared/page-header"
import { CTASection } from "@/components/shared/cta-section"
import { PricingCard } from "@/components/shared/pricing-card"
import { motion } from "motion/react"
import { cn } from "@/lib/utils"
import { ChevronDown } from "lucide-react"
import { useState } from "react"

const plans = [
  {
    name: "Starter",
    price: "€49",
    period: "/month",
    description: "Essential tools for small fleets getting started with digital operations.",
    features: [
      "Up to 5 vehicles",
      "Route planning & optimization",
      "Basic GPS tracking",
      "Email support",
      "1 user license included",
    ],
    ctaLabel: "Start free trial",
    ctaHref: "/register",
  },
  {
    name: "Professional",
    price: "€99",
    period: "/month",
    description: "Advanced features for growing fleets that need more power and flexibility.",
    features: [
      "Up to 25 vehicles",
      "Everything in Starter",
      "Advanced dispatch",
      "OCR document processing",
      "Analytics dashboard",
      "Priority support",
      "5 user licenses included",
      "API access",
    ],
    highlighted: true,
    ctaLabel: "Start free trial",
    ctaHref: "/register",
  },
  {
    name: "Enterprise",
    price: "€249",
    period: "/month",
    description: "Full platform access for large operations with custom requirements.",
    features: [
      "Unlimited vehicles",
      "Everything in Professional",
      "Custom integrations",
      "Dedicated account manager",
      "24/7 phone support",
      "Custom onboarding",
      "20 user licenses included",
      "SLA guarantee",
    ],
    ctaLabel: "Start free trial",
    ctaHref: "/register",
  },
]

const yearlyPlans = [
  { name: "Starter", price: "€39" },
  { name: "Professional", price: "€79" },
  { name: "Enterprise", price: "€199" },
]

const faqs = [
  {
    question: "Can I change plans?",
    answer:
      "Yes, upgrade or downgrade anytime. Changes take effect at the next billing cycle. Your data and settings remain intact throughout the transition.",
  },
  {
    question: "Is there a free trial?",
    answer:
      "Yes, all plans include a 14-day free trial. No credit card required. You get full access to every feature in your chosen plan with no restrictions.",
  },
  {
    question: "What payment methods do you accept?",
    answer:
      "We accept credit cards, bank transfers, and SEPA direct debit. Invoicing is available for annual Enterprise plans upon request.",
  },
  {
    question: "Can I add more vehicles mid-cycle?",
    answer:
      "Yes, additional vehicle slots can be added at any time. Prorated billing applies, so you only pay for what you use for the remainder of the billing period.",
  },
]

function FaqItem({
  question,
  answer,
  isOpen,
  onToggle,
}: {
  question: string
  answer: string
  isOpen: boolean
  onToggle: () => void
}) {
  return (
    <div className="border-b border-border/60 last:border-b-0">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between py-5 text-left transition-colors hover:text-foreground"
        aria-expanded={isOpen}
      >
        <span className="text-base font-medium text-foreground">{question}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
            isOpen && "rotate-180"
          )}
        />
      </button>
      <motion.div
        initial={false}
        animate={{
          height: isOpen ? "auto" : 0,
          opacity: isOpen ? 1 : 0,
        }}
        transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        className="overflow-hidden"
      >
        <p className="pb-5 text-sm leading-relaxed text-muted-foreground">{answer}</p>
      </motion.div>
    </div>
  )
}

export default function PricingPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  return (
    <div className="flex flex-col">
      <Helmet>
        <title>Pricing - Operion ERP</title>
      </Helmet>

      {/* Header */}
      <SectionWrapper>
        <PageHeader
          title="Simple, Transparent Pricing"
          description="Choose the plan that fits your fleet. All plans include a 14-day free trial."
          className="text-center"
        />
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className="mt-4 text-center text-sm text-muted-foreground"
        >
          Save up to 20% with annual billing —
          <span className="text-primary">
            {yearlyPlans.map((p, i) => (
              <span key={p.name}>
                {" "}{p.name}{" "}
                <span className="font-medium text-foreground">{p.price}</span>
                /month{i < yearlyPlans.length - 1 ? "," : ""}
              </span>
            ))}
          </span>
        </motion.p>
      </SectionWrapper>

      {/* Pricing Cards */}
      <SectionWrapper className="bg-muted/30">
        <div className="grid gap-8 lg:grid-cols-3 lg:gap-6">
          {plans.map((plan, i) => (
            <PricingCard
              key={plan.name}
              name={plan.name}
              price={plan.price}
              period={plan.period}
              description={plan.description}
              features={plan.features}
              highlighted={plan.highlighted}
              ctaLabel={plan.ctaLabel}
              ctaHref={plan.ctaHref}
              index={i}
            />
          ))}
        </div>
      </SectionWrapper>

      {/* FAQ */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-2xl"
        >
          <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl text-center">
            Frequently Asked Questions
          </h2>
          <div className="mt-10 divide-y divide-border/60 rounded-xl border border-border/60 bg-card/50 px-6">
            {faqs.map((faq, i) => (
              <FaqItem
                key={i}
                question={faq.question}
                answer={faq.answer}
                isOpen={openFaq === i}
                onToggle={() => setOpenFaq(openFaq === i ? null : i)}
              />
            ))}
          </div>
        </motion.div>
      </SectionWrapper>

      {/* CTA */}
      <SectionWrapper>
        <CTASection
          title="Start Your Free Trial Today"
          description="Join thousands of logistics professionals who trust Operion to run their fleet operations. No credit card required."
          primaryAction={{ label: "Get started", href: "/register" }}
        />
      </SectionWrapper>
    </div>
  )
}
