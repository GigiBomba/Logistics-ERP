import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import {
  Scale,
  FileText,
  GitBranch,
  ShieldAlert,
  FileCheck,
  PackageOpen,
  Scan,
  Map,
  ArrowRight,
  Zap,
  Truck,
  XCircle,
  CheckCircle2,
} from "lucide-react"
import { PageHeader, SectionHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { CtaBanner } from "@/components/shared/cta-banner"
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

function BeforeAfterVisual() {
  return (
    <div className="mt-8 grid gap-4 md:grid-cols-2">
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        whileInView={{ opacity: 1, x: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="rounded-xl border border-red-200 bg-red-50/50 p-6 dark:border-red-900 dark:bg-red-950/20"
      >
        <p className="text-xs font-bold uppercase tracking-wider text-red-700 dark:text-red-300 mb-4">Before Operion</p>
        <ul className="space-y-3">
          {[
            "CMRs typed manually in spreadsheets",
            "Load matching via phone calls & email",
            "Customs docs prepared one by one",
            "Multi-leg tracking in separate tools",
          ].map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-red-800 dark:text-red-200">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
              {item}
            </li>
          ))}
        </ul>
      </motion.div>
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        whileInView={{ opacity: 1, x: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay: 0.15 }}
        className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-6 dark:border-emerald-900 dark:bg-emerald-950/20"
      >
        <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-300 mb-4">After Operion</p>
        <ul className="space-y-3">
          {[
            "CMRs generated automatically from shipment data",
            "AI matches loads to carriers in seconds",
            "Customs declarations pre-filled & validated",
            "Unified multi-leg tracking in one view",
          ].map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-emerald-800 dark:text-emerald-200">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
              {item}
            </li>
          ))}
        </ul>
      </motion.div>
    </div>
  )
}

const challenges = [
  {
    icon: Scale,
    title: "Load Matching",
    description: "Finding the right carrier for every shipment manually wastes hours and leaves money on the table.",
  },
  {
    icon: FileText,
    title: "Documentation",
    description: "CMRs, invoices, and customs paperwork multiply errors when handled across spreadsheets and email.",
  },
  {
    icon: GitBranch,
    title: "Multi-Leg Trips",
    description: "Coordinating handoffs between trucks, trains, and ships creates visibility gaps and delays.",
  },
  {
    icon: ShieldAlert,
    title: "Customs Compliance",
    description: "Missing or incorrect customs documents can halt shipments at borders for days.",
  },
]

const solutions = [
  {
    icon: FileCheck,
    title: "CMR Automation",
    description: "Generate accurate CMRs, invoices, and customs declarations automatically from shipment data.",
  },
  {
    icon: PackageOpen,
    title: "Load Optimization",
    description: "Match shipments to available capacity based on weight, dimensions, route, and cost.",
  },
  {
    icon: Scan,
    title: "Document OCR",
    description: "Scan and digitize bills of lading, packing lists, and certificates for instant digital records.",
  },
  {
    icon: Map,
    title: "Trip Planning",
    description: "Plan complex multi-leg journeys with automatic handoff alerts and unified tracking.",
  },
]

const workflow = [
  { step: "01", label: "Receive Order", desc: "Import from TMS or email" },
  { step: "02", label: "Match Load", desc: "AI finds best carrier" },
  { step: "03", label: "Generate Docs", desc: "CMR & customs auto-filled" },
  { step: "04", label: "Track Shipment", desc: "Unified multi-leg view" },
  { step: "05", label: "Clear Customs", desc: "Digital document handoff" },
  { step: "06", label: "Deliver", desc: "Proof of delivery captured" },
]

const benefits = [
  {
    icon: FileText,
    title: "Faster Documentation",
    description: "Generate CMRs, invoices, and customs documents automatically from shipment data — no more manual re-typing.",
  },
  {
    icon: Truck,
    title: "Better Load Utilization",
    description: "Match shipments to available capacity across your network based on weight, route, and cost parameters.",
  },
  {
    icon: FileCheck,
    title: "Document Accuracy",
    description: "Reduce errors caused by manual data entry across spreadsheets and email chains with automated document generation.",
  },
  {
    icon: Zap,
    title: "Less Manual Entry",
    description: "Eliminate duplicate data entry by connecting your TMS, accounting, and document workflows in one platform.",
  },
]

export default function IndustryFreightPage() {
  return (
    <>
      <SeoHead
        title="Operion for Freight Forwarders — Document Automation & Load Matching"
        description="Streamline multi-leg shipments and automate documentation from first mile to last with Operion's freight forwarding tools."
        canonical="https://operionerp.xyz/industries/freight"
      />

      <PageHeader
        title="Operion for Freight Forwarders"
        description="Streamline multi-leg shipments and automate documentation from first mile to last."
      />

      {/* Challenges */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Industry Challenges"
          description="Freight forwarders juggle carriers, customs, and paperwork across every time zone."
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
          description="End-to-end tools that connect every leg of the journey with accurate, instant documentation."
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
          description="How a freight forwarder moves cargo from origin to destination with Operion."
          className="mb-12"
        />
        <div className="flex flex-wrap items-start justify-center gap-4">
          {workflow.map((step, i) => (
            <motion.div
              key={step.step}
              initial={{ opacity: 0, x: -10 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.3, delay: i * 0.08 }}
              className="flex items-center gap-3"
            >
              <div className="flex flex-col items-center text-center">
                <Badge variant="outline" className="mb-2 text-xs font-mono">
                  {step.step}
                </Badge>
                <div className="rounded-xl border bg-card p-4 shadow-sm min-w-[130px]">
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
          description="How freight forwarders benefit from automated documentation and streamlined operations."
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

      {/* Before / After */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="See It in Action"
          description="The freight operations hub keeps every shipment, document, and handoff in one place."
          className="mb-8"
        />
        <BeforeAfterVisual />
      </SectionWrapper>

      {/* CTA */}
      <SectionWrapper className="pb-8 md:pb-12">
        <CtaBanner
          title="Ready to transform your freight operations?"
          description="Start your free trial and automate the paperwork that slows you down."
          buttonText="Start Free Trial"
          buttonHref="/register"
        />
      </SectionWrapper>
    </>
  )
}
