import { SeoHead } from "@/components/seo/seo-head"
import { Link } from "react-router"
import { motion } from "motion/react"
import {
  ArrowRight,
  Boxes,
  Cloud,
  Smartphone,
  BarChart3,
  Terminal,
  Layers,
  Sparkles,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { useLocale } from "@/i18n/locale-context"
import { SectionHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CtaBanner } from "@/components/shared/cta-banner"

const products = [
  {
    icon: Boxes,
    title: "Operion Core",
    description:
      "AI logistics operating system. Tell Operion what outcome you want \u2014 find a return load, dispatch a truck, generate documents \u2014 and it executes the full workflow autonomously.",
    badge: "Available",
    href: "/features",
    variant: "default" as const,
  },
  {
    icon: Sparkles,
    title: "Operion AI Dispatch",
    description:
      "Autonomous dispatch engine that searches freight exchanges, checks driver legality, calculates profitability, creates dispatches, generates CMRs and invoices, and notifies drivers \u2014 all from a single instruction.",
    badge: "Available",
    href: "/features",
    variant: "default" as const,
  },
  {
    icon: Smartphone,
    title: "Operion Mobile",
    description:
      "Driver companion app with live GPS tracking, signature capture, proof of delivery, and real-time messaging \u2014 fully integrated with the autonomous dispatch engine.",
    badge: "Available",
    href: "/download",
    variant: "default" as const,
  },
  {
    icon: Terminal,
    title: "Operion Toolkit",
    description:
      "Command-line toolkit for automation, scripting, and custom workflow integrations with the autonomous dispatch engine.",
    badge: "Available",
    href: "/developers/toolkit",
    variant: "default" as const,
  },
  {
    icon: Cloud,
    title: "Operion Cloud",
    description:
      "Cloud synchronization and real-time fleet data sharing across organizations \u2014 extending autonomous dispatch capabilities across your entire operation.",
    badge: "Coming 2027",
    href: "#",
    variant: "secondary" as const,
  },
  {
    icon: BarChart3,
    title: "Operion Analytics",
    description:
      "Self-updating business intelligence powered by every autonomous dispatch. Profitability, fleet utilization, and empty-kilometer trends without manual report building.",
    badge: "Planned",
    href: "#",
    variant: "outline" as const,
  },
]

export default function ProductsPage() {
  const { t } = useLocale()
  return (
    <>
      <SeoHead title="Autonomous Logistics Operating System \u2014 Operion Products" description="Explore the Operion autonomous logistics operating system. The AI dispatch engine that turns dispatcher intent into executed workflows. Mobile, Toolkit, Cloud, and Analytics extend the core." canonical="https://operionerp.xyz/products" />

      <HeroSection
        title="The Autonomous Logistics Operating System"
        description="Not a collection of separate tools. A single AI-driven system where you state the outcome and Operion executes the workflow \u2014 from freight discovery to driver notification."
        align="center"
        size="large"
      />

      {/* Product Cards */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Capabilities That Work Together"
          description="One AI operating system, multiple capability layers. The dispatch engine is the core; mobile, toolkit, cloud, and analytics extend what you can automate."
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((product, i) => (
            <motion.div
              key={product.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
            >
              <Card className="group h-full transition-shadow hover:shadow-md">
                <CardHeader>
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                    <product.icon className="h-5 w-5" />
                  </div>
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-lg">{product.title}</CardTitle>
                    <Badge variant={product.variant} className="text-[10px]">
                      {product.badge}
                    </Badge>
                  </div>
                  <CardDescription className="text-sm leading-relaxed">
                    {product.description}
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  <Button
                    variant={product.href === "#" ? "outline" : "default"}
                    size="sm"
                    asChild
                    className="mt-2"
                  >
                    <Link to={product.href}>
                      {product.href === "#" ? "Learn more" : "Get started"}
                      <ArrowRight className="ml-1 h-4 w-4" />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* How Products Work Together */}
      <SectionWrapper>
        <SectionHeader
          title="How the Autonomous System Fits Together"
          description="Start with the core dispatch engine. Add mobile for driver connectivity, toolkit for custom automation, and analytics for self-updating intelligence \u2014 all powered by the same AI operating system."
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <Card className="overflow-hidden">
            <CardContent className="p-8 md:p-12">
              <div className="flex flex-col items-center gap-6 md:flex-row md:flex-wrap md:justify-center">
                {/* ERP */}
                <div className="flex w-full max-w-[180px] flex-col items-center gap-3 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
                    <Boxes className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="font-semibold tracking-tight">{t("products.core")}</p>
                    <p className="text-xs text-muted-foreground">{t("products.coreDesc")}</p>
                  </div>
                </div>

                {/* Arrow */}
                <ArrowRight className="hidden h-5 w-5 text-muted-foreground md:block" />

                {/* Mobile */}
                <div className="flex w-full max-w-[180px] flex-col items-center gap-3 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-accent text-primary shadow-sm">
                    <Smartphone className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="font-semibold tracking-tight">{t("products.mobile")}</p>
                    <p className="text-xs text-muted-foreground">{t("products.mobileDesc")}</p>
                  </div>
                </div>

                {/* Arrow */}
                <ArrowRight className="hidden h-5 w-5 text-muted-foreground md:block" />

                {/* Toolkit */}
                <div className="flex w-full max-w-[180px] flex-col items-center gap-3 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-secondary text-secondary-foreground shadow-sm">
                    <Terminal className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="font-semibold tracking-tight">{t("products.toolkit")}</p>
                    <p className="text-xs text-muted-foreground">{t("products.toolkitDesc")}</p>
                  </div>
                </div>

                {/* Arrow */}
                <ArrowRight className="hidden h-5 w-5 text-muted-foreground md:block" />

                {/* AI */}
                <div className="flex w-full max-w-[180px] flex-col items-center gap-3 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/20 text-primary shadow-sm">
                    <Sparkles className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="font-semibold tracking-tight">{t("products.ai")}</p>
                    <p className="text-xs text-muted-foreground">{t("products.aiDesc")}</p>
                  </div>
                </div>
              </div>

              <div className="mt-10 flex items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                <Layers className="h-4 w-4" />
                <span>
                  Every capability is designed around the autonomous dispatch engine. State the outcome. Operion executes the workflow.
                </span>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* CTA Banner */}
      <SectionWrapper className="pb-24">
        <CtaBanner
          title="Ready to dispatch with a single instruction?"
          description="Tell Operion what outcome you want and watch it execute the logistics workflow \u2014 from freight discovery to driver notification. Free during the current phase."
          buttonText="Try Autonomous Dispatching"
          buttonHref="/features"
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
