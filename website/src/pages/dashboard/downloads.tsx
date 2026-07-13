import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import { Download, ChevronRight, Package, Monitor, HardDrive, Cpu } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/empty-state"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { downloadConfig } from "@/config/site"

export default function DashboardDownloadsPage() {
  return (
    <>
      <Helmet><title>Downloads — Operion ERP</title></Helmet>
      <SectionWrapper>
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h1 className="text-3xl font-bold tracking-tight">Downloads</h1>
          <p className="mt-2 text-muted-foreground">Download the latest Operion desktop application and tools.</p>
        </motion.div>

        <div className="mt-8 grid gap-8 lg:grid-cols-3">
          {/* Desktop Installer */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.1 }} className="lg:col-span-2">
            <Card className="border-primary/30 bg-muted/20">
              <CardContent className="p-8">
                <div className="flex flex-col items-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-6">
                    <Download className="h-8 w-8 text-primary" />
                  </div>
                  <Badge variant="success" className="mb-3">Latest Release</Badge>
                  <h2 className="text-2xl font-bold">Operion ERP {downloadConfig.latestVersion}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">Released {downloadConfig.releaseDate} • {downloadConfig.fileSize}</p>
                  <p className="mt-1 text-sm text-muted-foreground">Windows 10/11 (64-bit)</p>
                  <Button size="xl" className="mt-6" asChild>
                    <a href={downloadConfig.windowsInstaller}>
                      <Download className="mr-2 h-4 w-4" />
                      Download for Windows
                    </a>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* System Requirements */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.15 }}>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">System Requirements</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  { icon: Monitor, label: "OS", val: downloadConfig.systemRequirements.os[0] },
                  { icon: Cpu, label: "CPU", val: "Intel Core i5+" },
                  { icon: HardDrive, label: "RAM", val: "8 GB (16 GB rec.)" },
                ].map((r) => (
                  <div key={r.label} className="flex items-center gap-2 text-sm">
                    <r.icon className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">{r.label}:</span>
                    <span className="font-medium">{r.val}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </motion.div>

          {/* Previous Versions */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Previous Versions</CardTitle>
                <CardDescription>Access earlier releases</CardDescription>
              </CardHeader>
              <CardContent>
                <EmptyState title="No previous versions" description="Previous releases will appear here." />
              </CardContent>
            </Card>
          </motion.div>

          {/* Toolkit */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.25 }}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><Package className="h-4 w-4" /> Toolkit</CardTitle>
                <CardDescription>CLI tools and utilities</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center">
                  <Package className="mx-auto h-8 w-8 text-muted-foreground/40" />
                  <p className="mt-3 text-sm font-medium">Coming Soon</p>
                  <p className="mt-1 text-xs text-muted-foreground">Available shortly after launch</p>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Release Notes */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.3 }}>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Release Notes</CardTitle>
                <CardDescription>See what's new</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">Release notes for version {downloadConfig.latestVersion} and all future releases will be available here.</p>
                <Button variant="link" className="mt-2 h-auto p-0" asChild>
                  <Link to="/download">View full release notes <ChevronRight className="ml-1 h-3 w-3" /></Link>
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>
    </>
  )
}
