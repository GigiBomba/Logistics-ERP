import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { Download, Monitor, HardDrive, Cpu, CheckCircle2, History } from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { SectionHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ReleaseCard } from "@/components/shared/release-card"
import type { Release } from "@/components/shared/release-card"
import { CtaBanner } from "@/components/shared/cta-banner"
import { toolkitConfig } from "@/config/site"

const systemRequirements = [
  { icon: Monitor, label: "Operating System", value: "Windows 10/11 (64-bit), macOS 13+, Ubuntu 22.04+" },
  { icon: Cpu, label: "Processor", value: "Intel Core i3 or Apple Silicon M1 equivalent" },
  { icon: HardDrive, label: "RAM & Storage", value: "4 GB RAM minimum, 500 MB available space" },
  { icon: CheckCircle2, label: "Dependencies", value: "Node.js 18+ or .NET 8 Runtime" },
]

const installationSteps = [
  {
    title: "Download the installer",
    description: `Grab the latest toolkit v${toolkitConfig.latestVersion} for your platform using the button below.`,
  },
  {
    title: "Run the installer",
    description: "Execute the installer and follow the setup wizard. The toolkit will add itself to your system PATH automatically.",
  },
  {
    title: "Verify the installation",
    description: "Open a terminal and run operion --version to confirm the toolkit is installed and accessible.",
  },
]

const includedFeatures = [
  {
    title: "CLI Interface",
    description: "A unified command-line interface for managing routes, fleets, jobs, and drivers directly from the terminal.",
  },
  {
    title: "Authentication Helper",
    description: "Secure token management with automatic refresh, scoped profiles, and SSO integration support.",
  },
  {
    title: "Data Import / Export",
    description: "Bulk import CSV and JSON datasets, or export reports and audit logs in multiple formats.",
  },
  {
    title: "Local Development Server",
    description: "Spin up a local mock server to test webhooks, simulate API responses, and prototype integrations.",
  },
  {
    title: "Schema Validator",
    description: "Validate payloads against Operion API schemas before sending requests to catch errors early.",
  },
  {
    title: "Log Analyzer",
    description: "Parse and filter application logs with built-in query syntax for faster debugging and auditing.",
  },
]

const releaseHistory: Release[] = [
  {
    version: "1.0.0",
    release_date: "2026-09-01",
    type: "toolkit",
    size_mb: 42,
    downloads_url: toolkitConfig.downloadUrl,
    sections: [
      {
        title: "New",
        items: [
          "Initial public release of the Operion Toolkit",
          "CLI interface for route, fleet, and job management",
          "Authentication helper with token refresh",
          "Local development server with mock API support",
        ],
      },
      {
        title: "Improvements",
        items: [
          "Cross-platform installer for Windows, macOS, and Linux",
          "Auto-updater with rollback support",
        ],
      },
    ],
  },
  {
    version: "0.9.2",
    release_date: "2026-08-15",
    type: "toolkit",
    size_mb: 38,
    sections: [
      {
        title: "New",
        items: [
          "Schema validator for API request payloads",
          "Log analyzer with query syntax support",
        ],
      },
      {
        title: "Fixes",
        items: [
          "Resolved token refresh race condition on slow networks",
          "Fixed path escaping issue on Windows PowerShell",
        ],
      },
    ],
  },
  {
    version: "0.9.0",
    release_date: "2026-07-20",
    type: "toolkit",
    size_mb: 35,
    sections: [
      {
        title: "New",
        items: [
          "Beta release for early access partners",
          "Data import and export utilities",
          "Bulk CSV processing with validation",
        ],
      },
    ],
  },
]

const previousVersions = [
  { version: "0.9.2", date: "2026-08-15", url: "#" },
  { version: "0.9.1", date: "2026-08-01", url: "#" },
  { version: "0.9.0", date: "2026-07-20", url: "#" },
  { version: "0.8.5", date: "2026-06-10", url: "#" },
]

export default function ToolkitPage() {
  return (
    <>
      <Helmet>
        <title>Toolkit — Operion</title>
        <meta name="description" content="Download the Operion Toolkit. Command-line utilities, authentication helpers, local development server, and integration tools for developers." />
      </Helmet>

      <HeroSection
        title="Operion Toolkit"
        description="Command-line utilities and developer tools that make integrating with Operion fast, reliable, and predictable."
        align="center"
        size="large"
      />

      {/* System Requirements */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="System Requirements"
          description="Minimum specs to run the toolkit on your machine."
          className="mb-12"
        />
        <div className="mx-auto max-w-3xl grid gap-4 sm:grid-cols-2">
          {systemRequirements.map((req, i) => (
            <motion.div
              key={req.label}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="h-full">
                <CardContent className="flex gap-3 p-5">
                  <req.icon className="mt-0.5 h-5 w-5 text-muted-foreground shrink-0" />
                  <div>
                    <p className="text-sm font-medium">{req.label}</p>
                    <p className="text-xs text-muted-foreground">{req.value}</p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Download */}
      <SectionWrapper>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl"
        >
          <Card className="border-primary/30 bg-muted/30">
            <CardContent className="p-8">
              <div className="flex flex-col items-center text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-6">
                  <Download className="h-8 w-8 text-primary" />
                </div>
                <Badge variant="success" className="mb-3">Latest Release</Badge>
                <h2 className="text-2xl font-bold">Operion Toolkit {toolkitConfig.latestVersion}</h2>
                <p className="mt-2 text-sm text-muted-foreground">Released {toolkitConfig.releaseDate}</p>
                <Button size="xl" className="mt-6" asChild>
                  <a href={toolkitConfig.downloadUrl} download>
                    <Download className="mr-2 h-4 w-4" />
                    Download Toolkit
                  </a>
                </Button>
                <p className="mt-4 text-xs text-muted-foreground">
                  Windows, macOS, and Linux installers included
                </p>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* Installation */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Installation"
          description="Get up and running in under two minutes."
          className="mb-12"
        />
        <div className="mx-auto max-w-3xl">
          <div className="space-y-6">
            {installationSteps.map((step, i) => (
              <motion.div
                key={step.title}
                initial={{ opacity: 0, x: -10 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.15 }}
                className="flex gap-4"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                  {i + 1}
                </div>
                <div>
                  <h3 className="text-base font-semibold tracking-tight">{step.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{step.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </SectionWrapper>

      {/* What's Included */}
      <SectionWrapper>
        <SectionHeader
          title="What's Included"
          description="A complete set of tools for developers working with Operion."
          className="mb-12"
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {includedFeatures.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
            >
              <Card className="h-full transition-shadow hover:shadow-md">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Release History */}
      <SectionWrapper className="bg-muted/30">
        <SectionHeader
          title="Release History"
          description="Recent updates and improvements to the toolkit."
          className="mb-12"
        />
        <div className="mx-auto max-w-3xl space-y-6">
          {releaseHistory.map((release) => (
            <ReleaseCard key={release.version} release={release} />
          ))}
        </div>
      </SectionWrapper>

      {/* Previous Versions */}
      <SectionWrapper>
        <SectionHeader
          title="Previous Versions"
          description="Access older toolkit releases for compatibility testing or rollback."
          className="mb-12"
        />
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-2xl"
        >
          <Card>
            <CardContent className="p-5">
              <div className="space-y-3">
                {previousVersions.map((version) => (
                  <div
                    key={version.version}
                    className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <History className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium">v{version.version}</p>
                        <p className="text-xs text-muted-foreground">{version.date}</p>
                      </div>
                    </div>
                    <Button variant="ghost" size="sm" asChild>
                      <a href={version.url} download>
                        <Download className="mr-1 h-4 w-4" />
                        Download
                      </a>
                    </Button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </SectionWrapper>

      {/* CTA Banner */}
      <SectionWrapper className="pb-24">
        <CtaBanner
          title="Need help getting started?"
          description="Reach out to our developer support team or browse the documentation."
          buttonText="Contact support"
          buttonHref="/contact"
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
