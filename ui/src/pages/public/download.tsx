import { Helmet } from "react-helmet-async"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { PageHeader } from "@/components/shared/page-header"
import { EmptyState } from "@/components/shared/empty-state"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { motion } from "motion/react"
import { Download, ExternalLink, FileCode, PackageOpen } from "lucide-react"

const systemRequirements = [
  { label: "Operating System", value: "Windows 10 (64-bit) or Windows 11 (64-bit)" },
  { label: "RAM", value: "8 GB minimum (16 GB recommended)" },
  { label: "Storage", value: "2 GB available space" },
  { label: "Processor", value: "Intel Core i5 or equivalent (i7 recommended)" },
  { label: "Additional", value: ".NET Framework 4.8 or later, DirectX 11 compatible GPU" },
]

export default function DownloadPage() {
  return (
    <div className="flex flex-col">
      <Helmet>
        <title>Download - Operion ERP</title>
      </Helmet>

      {/* Header */}
      <SectionWrapper className="pb-0">
        <PageHeader
          title="Download Operion Desktop"
          description="Get the latest version of the Operion ERP desktop application for Windows."
        />
      </SectionWrapper>

      {/* Primary Download Card */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <Card className="relative overflow-hidden border-primary/20 bg-card/95 shadow-lg">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-primary/5" />
            <CardHeader className="relative pb-2">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-md">
                  <Download className="h-6 w-6" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-foreground sm:text-2xl">
                    Operion ERP 1.0.0
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    Released September 1, 2026
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="relative space-y-5">
              <div className="flex flex-col gap-4 rounded-lg bg-muted/50 p-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="success" className="text-xs">
                      Windows
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      Windows 10/11 (64-bit)
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    File size: 245 MB
                  </p>
                </div>
                <Button size="lg" asChild>
                  <a href="#download-windows">
                    <Download className="mr-2 h-4 w-4" />
                    Download for Windows
                  </a>
                </Button>
              </div>
              <p className="text-sm italic text-muted-foreground">
                macOS and Linux versions coming soon
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* System Requirements */}
      <SectionWrapper className="bg-muted/30">
        <PageHeader
          title="System Requirements"
          description="Ensure your system meets these minimum requirements."
          className="mb-8"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="overflow-hidden rounded-xl border border-border/60"
        >
          <table className="w-full text-sm">
            <tbody>
              {systemRequirements.map((req, i) => (
                <tr
                  key={req.label}
                  className={i % 2 === 0 ? "bg-muted/30" : "bg-background"}
                >
                  <td className="whitespace-nowrap px-5 py-3 font-medium text-foreground">
                    {req.label}
                  </td>
                  <td className="w-full px-5 py-3 text-muted-foreground">
                    {req.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </motion.div>
      </SectionWrapper>

      {/* Release Notes */}
      <SectionWrapper>
        <PageHeader
          title="Release Notes"
          description="What's new in Operion ERP 1.0.0."
          className="mb-8"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="space-y-4"
        >
          <Card>
            <CardContent className="p-6">
              <div className="mb-3 flex items-center gap-2">
                <Badge variant="default">v1.0.0</Badge>
                <span className="text-sm text-muted-foreground">
                  September 1, 2026
                </span>
              </div>
              <ul className="list-inside list-disc space-y-1.5 text-sm text-muted-foreground">
                <li>Initial release of Operion ERP Desktop</li>
                <li>Full-featured enterprise resource planning interface</li>
                <li>Real-time inventory and order management</li>
                <li>Advanced logistics and route optimization</li>
                <li>Integrated financial reporting and analytics</li>
                <li>Multi-user collaboration with role-based access</li>
                <li>Offline support with automatic synchronization</li>
              </ul>
            </CardContent>
          </Card>
          <Button variant="link" size="sm" asChild>
            <a href="#release-notes" className="gap-1">
              View full release notes
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </Button>
        </motion.div>
      </SectionWrapper>

      {/* Checksums */}
      <SectionWrapper className="bg-muted/30">
        <PageHeader
          title="File Checksums"
          description="Verify the integrity of your download."
          className="mb-8"
        />
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <FileCode className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium text-foreground">SHA-256</p>
                <p className="text-sm text-muted-foreground">Coming soon</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </SectionWrapper>

      {/* Version History */}
      <SectionWrapper>
        <PageHeader
          title="Version History"
          description="Previous versions of Operion ERP Desktop."
          className="mb-8"
        />
        <EmptyState
          title="No previous versions available"
          description="No previous versions available yet."
          icon={PackageOpen}
        />
      </SectionWrapper>

      {/* Toolkit Download */}
      <SectionWrapper className="bg-muted/30">
        <PageHeader
          title="Operion Toolkit"
          description="Command-line utilities and integration tools for advanced users."
          className="mb-8"
        />
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Download className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">
                  Operion Toolkit
                </p>
                <p className="text-sm text-muted-foreground">
                  Coming soon &mdash; Command-line utilities and integration tools for
                  advanced users.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </SectionWrapper>
    </div>
  )
}
