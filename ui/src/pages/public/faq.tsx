import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion, AnimatePresence } from "motion/react"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { PageHeader } from "@/components/shared/page-header"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { ChevronDown } from "lucide-react"

interface FaqItem {
  question: string
  answer: string
}

interface FaqCategory {
  category: string
  items: FaqItem[]
}

const faqData: FaqCategory[] = [
  {
    category: "General",
    items: [
      {
        question: "What is Operion ERP?",
        answer:
          "Operion ERP is a comprehensive enterprise logistics platform designed for fleet management, route planning, dispatch, and operational analytics. It combines powerful desktop software with cloud-based services.",
      },
      {
        question: "Is Operion a web application or desktop application?",
        answer:
          "Operion's primary product is a Windows desktop application that provides the full logistics management experience. Our website serves as your customer portal for account management, subscriptions, documentation, and support.",
      },
      {
        question: "Can I access Operion from multiple computers?",
        answer:
          "Yes, your Operion license allows installation on multiple devices per user. Your data syncs through our secure cloud infrastructure.",
      },
    ],
  },
  {
    category: "Pricing",
    items: [
      {
        question: "How does pricing work?",
        answer:
          "We offer three plans — Starter (€49/mo), Professional (€99/mo), and Enterprise (€249/mo). Pricing is based on the number of vehicles in your fleet. Annual billing saves you 20%.",
      },
      {
        question: "Is there a free trial?",
        answer:
          "Yes, all plans include a 14-day free trial. No credit card required to start.",
      },
      {
        question: "Can I switch plans later?",
        answer:
          "Absolutely. You can upgrade or downgrade at any time. Changes take effect at your next billing cycle.",
      },
    ],
  },
  {
    category: "Technical",
    items: [
      {
        question: "What are the system requirements?",
        answer:
          "Operion runs on Windows 10/11 (64-bit) with 8GB RAM minimum (16GB recommended), 2GB storage, and an Intel Core i5 or equivalent processor.",
      },
      {
        question: "Is my data secure?",
        answer:
          "Yes. We use AES-256 encryption at rest and TLS 1.3 in transit. Our infrastructure undergoes regular security audits and penetration testing.",
      },
      {
        question: "Does Operion work offline?",
        answer:
          "The desktop application can operate in offline mode. Data syncs automatically when your connection is restored.",
      },
    ],
  },
  {
    category: "Support",
    items: [
      {
        question: "What kind of support do you offer?",
        answer:
          "All plans include email support. Professional plans include priority support. Enterprise plans include 24/7 phone support and a dedicated account manager.",
      },
      {
        question: "Do you offer training?",
        answer:
          "Yes, we provide comprehensive documentation, video tutorials, and onboarding resources. Enterprise customers receive personalized onboarding sessions.",
      },
    ],
  },
]

function FaqAccordion({ items }: { items: FaqItem[] }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  return (
    <div className="space-y-3">
      {items.map((item, index) => {
        const isOpen = openIndex === index
        return (
          <Card
            key={index}
            className={cn(
              "overflow-hidden transition-all duration-300",
              isOpen && "border-primary/30 shadow-md"
            )}
          >
            <button
              onClick={() => setOpenIndex(isOpen ? null : index)}
              className="flex w-full items-center justify-between px-6 py-4 text-left transition-colors hover:bg-accent/50"
            >
              <span className="pr-4 text-sm font-medium text-foreground sm:text-base">
                {item.question}
              </span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-300",
                  isOpen && "rotate-180"
                )}
              />
            </button>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  key="content"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                  className="overflow-hidden"
                >
                  <div className="border-t border-border/60 px-6 py-4">
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {item.answer}
                    </p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        )
      })}
    </div>
  )
}

export default function FaqPage() {
  return (
    <>
      <Helmet>
        <title>FAQ - Operion ERP</title>
      </Helmet>

      <SectionWrapper>
        <PageHeader
          title="Frequently Asked Questions"
          description="Find answers to common questions about Operion ERP."
          className="text-center"
        />

        <div className="mt-16 space-y-12">
          {faqData.map((category) => (
            <motion.div
              key={category.category}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="mb-6 flex items-center gap-3">
                <Badge variant="default" className="px-3 py-1 text-xs">
                  {category.category}
                </Badge>
              </div>
              <FaqAccordion items={category.items} />
            </motion.div>
          ))}
        </div>
      </SectionWrapper>
    </>
  )
}
