import { Helmet } from "react-helmet-async"
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
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CtaBanner } from "@/components/shared/cta-banner"

const products = [
  {
    icon: Boxes,
    title: "Operion ERP",
    description:
      "Enterprise logistics management platform for route planning, fleet management, and dispatch.",
    badge: "Available",
    href: "/download",
    variant: "default" as const,
  },
  {
    icon: Terminal,
    title: "Operion Toolkit",
    description:
      "Command-line toolkit for automation, scripting, and custom integrations.",
    badge: "Available",
    href: "/developers/toolkit",
    variant: "default" as const,
  },
  {
    icon: Cloud,
    title: "Operion Cloud",
    description:
      "Cloud synchronization, real-time collaboration, and fleet data sharing across organizations.",
    badge: "Coming 2027",
    href: "#",
    variant: "secondary" as const,
  },
  {
    icon: Smartphone,
    title: "Operion Mobile",
    description:
      "Mobile companion app for drivers with offline mode, signature capture, and proof of delivery.",
    badge: "Coming 2027",
    href: "#",
    variant: "secondary" as const,
  },
  {
    icon: BarChart3,
    title: "Operion Analytics",
    description:
      "Advanced business intelligence with custom dashboards, predictive analytics, and KPI monitoring.",
    badge: "Planned",
    href: "#",
    variant: "outline" as const,
  },
]

export default function ProductsPage() {
  return (
    <>
      <Helmet>
        <title>Operion Products — Enterprise Logistics Suite</title>
        <meta
          name="description"
          content="Explore the Operion product ecosystem: ERP, Toolkit, Cloud, Mobile, and Analytics. Built for modern logistics teams."
        />
      </Helmet>

      <HeroSection
        title="Operion Products"
        description="A suite of tools for modern logistics teams. Each product is designed to work standalone or as part of a connected ecosystem."
        align="center"
        size="large"
      />

      {/* Product Cards */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Product Ecosystem"
          description="Five products, one vision. Choose what you need today, expand when you are ready."
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
          title="How Products Work Together"
          description="Operion is designed as a modular system. Start with the core and layer on capabilities as your operation grows."
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
              <div className="flex flex-col items-center gap-8 md:flex-row md:justify-center">
                {/* ERP */}
                <div className="flex w-full max-w-[200px] flex-col items-center gap-3 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
                    <Boxes className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="font-semibold tracking-tight">Operion ERP</p>
                    <p className="text-xs text-muted-foreground">Core platform</p>
                  </div>
                </div>

                {/* Arrow */}
                <div className="flex flex-col items-center gap-1 text-muted-foreground md:pt-0">
                  <ArrowRight className="hidden h-5 w-5 md:block" />
                  <span className="text-xs font-medium uppercase tracking-wider md:hidden">connects to</span>
                  <span className="hidden text-xs font-medium uppercase tracking-wider md:block">connects to</span>
                </div>

                {/* Toolkit */}
                <div className="flex w-full max-w-[200px] flex-col items-center gap-3 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-accent text-primary shadow-sm">
                    <Terminal className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="font-semibold tracking-tight">Operion Toolkit</p>
                    <p className="text-xs text-muted-foreground">Automation & scripting</p>
                  </div>
                </div>

                {/* Arrow */}
                <div className="flex flex-col items-center gap-1 text-muted-foreground">
                  <ArrowRight className="hidden h-5 w-5 md:block" />
                  <span className="text-xs font-medium uppercase tracking-wider">syncs via</span>
                </div>

                {/* Cloud */}
                <div className="flex w-full max-w-[200px] flex-col items-center gap-3 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-secondary text-secondary-foreground shadow-sm">
                    <Cloud className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="font-semibold tracking-tight">Operion Cloud</p>
                    <p className="text-xs text-muted-foreground">Fleet data sharing</p>
                  </div>
                </div>
              </div>

              <div className="mt-10 flex items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                <Layers className="h-4 w-4" />
                <span>
                  Mobile and Analytics layers consume data from the core stack via the Cloud layer.
                </span>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* CTA Banner */}
      <SectionWrapper className="pb-24">
        <CtaBanner
          title="Need help choosing the right products?"
          description="Our team can walk you through the ecosystem and recommend the best setup for your logistics operation."
          buttonText="Talk to sales"
          buttonHref="/enterprise"
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
