import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { BookOpen, MapPin, Radio, Send, Scan, BarChart3, Users, FileText, ChevronRight, Search } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { SectionWrapper } from "@/components/shared/section-wrapper"

const categories = [
  { icon: BookOpen, title: "Getting Started", description: "Installation, setup, and first steps with Operion.", count: 5, href: "/docs/getting-started" },
  { icon: MapPin, title: "Route Planning", description: "Learn how to create and optimize routes.", count: 8, href: "/docs/route-planning" },
  { icon: Radio, title: "Fleet Tracking", description: "Real-time GPS tracking and fleet monitoring.", count: 6, href: "/docs/fleet-tracking" },
  { icon: Send, title: "Dispatch", description: "Job assignment, driver management, and dispatch workflows.", count: 7, href: "/docs/dispatch" },
  { icon: Scan, title: "OCR & Documents", description: "Document scanning, OCR, and digital archiving.", count: 4, href: "/docs/ocr" },
  { icon: BarChart3, title: "Analytics", description: "Reports, dashboards, and KPI tracking.", count: 5, href: "/docs/analytics" },
  { icon: Users, title: "Administration", description: "User management, permissions, and account settings.", count: 6, href: "/docs/administration" },
  { icon: FileText, title: "API Reference", description: "Integrate Operion with your existing systems.", count: 3, href: "/docs/api" },
]

export default function DocumentationPage() {
  return (
    <>
      <Helmet><title>Documentation — Operion ERP</title></Helmet>
      <SectionWrapper>
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h1 className="text-3xl font-bold tracking-tight">Documentation</h1>
          <p className="mt-2 text-muted-foreground">Learn how to get the most out of Operion ERP.</p>
        </motion.div>

        {/* Search Placeholder */}
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }} className="mt-8">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input className="pl-10" placeholder="Search documentation... (coming soon)" disabled />
          </div>
        </motion.div>

        {/* Categories */}
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {categories.map((cat, i) => (
            <motion.div
              key={cat.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 + i * 0.05 }}
            >
              <Link to={cat.href}>
                <Card className="h-full transition-shadow hover:shadow-md">
                  <CardContent className="p-5">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent mb-4">
                      <cat.icon className="h-5 w-5 text-primary" />
                    </div>
                    <h3 className="font-semibold text-sm">{cat.title}</h3>
                    <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{cat.description}</p>
                    <div className="mt-3 flex items-center justify-between">
                      <Badge variant="secondary" className="text-xs">{cat.count} articles</Badge>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </motion.div>
          ))}
        </div>

        {/* Tutorials Placeholder */}
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.5 }} className="mt-12">
          <Card>
            <CardHeader>
              <CardTitle>Video Tutorials</CardTitle>
              <CardDescription>Step-by-step video guides for common workflows.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8">
                <BookOpen className="mx-auto h-10 w-10 text-muted-foreground/40" />
                <p className="mt-3 text-sm font-medium">Coming Soon</p>
                <p className="mt-1 text-xs text-muted-foreground">Video tutorials will be available at launch.</p>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
