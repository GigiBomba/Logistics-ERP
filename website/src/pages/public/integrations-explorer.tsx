import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion, AnimatePresence } from "motion/react"
import {
  Search,
  Plug,
  ChevronDown,
  BookOpen,
  Wrench,
  ListChecks,
  ArrowRight,
} from "lucide-react"
import { HeroSection } from "@/components/shared/hero-section"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CtaBanner } from "@/components/shared/cta-banner"
import { StatusBadge } from "@/components/shared/status-badge"

type Category = "All" | "Telematics" | "Accounting" | "Communication" | "Analytics" | "ERP" | "Other"

interface Integration {
  id: string
  name: string
  category: Category
  status: "available" | "planned" | "beta"
  overview: string
  capabilities: string[]
  setup: string
  requirements: string[]
  docsHref: string
}

const integrations: Integration[] = [
  {
    id: "geotab",
    name: "Geotab",
    category: "Telematics",
    status: "available",
    overview: "Real-time vehicle tracking, driver behavior monitoring, and engine diagnostics directly synced into Operion's fleet dashboard.",
    capabilities: ["Real-time GPS tracking", "Engine fault codes", "Driver scorecards", "Fuel consumption analytics", "Geofence alerts"],
    setup: "Connect via API key from your Geotab MyAdmin portal. Data syncs every 60 seconds with historical backfill available.",
    requirements: ["Active Geotab account", "MyAdmin API access enabled", "Operion Professional plan or higher"],
    docsHref: "#",
  },
  {
    id: "samsara",
    name: "Samsara",
    category: "Telematics",
    status: "beta",
    overview: "Fleet IoT platform integration for vehicle telematics, compliance, and safety workflows within Operion.",
    capabilities: ["ELD compliance data", "Vehicle diagnostics", "Safety event video", "Temperature monitoring", "Route replay"],
    setup: "Generate a Samsara API token with read scope. Map vehicle IDs in Operion settings. Sync begins within 5 minutes.",
    requirements: ["Samsara account with API access", "Vehicle ID mapping in Operion", "Beta program enrollment"],
    docsHref: "#",
  },
  {
    id: "quickbooks",
    name: "QuickBooks Online",
    category: "Accounting",
    status: "available",
    overview: "Sync trip invoices, driver payroll, and fleet expenses directly to your QuickBooks company file.",
    capabilities: ["Automatic invoice creation", "Expense categorization", "Tax tracking", "Multi-currency support", "Reconciliation reports"],
    setup: "Authorize Operion via OAuth 2.0 through QuickBooks App Store. Select company file and mapping preferences.",
    requirements: ["QuickBooks Online Plus or Advanced", "Admin access to company file", "Operion Professional plan"],
    docsHref: "#",
  },
  {
    id: "xero",
    name: "Xero",
    category: "Accounting",
    status: "planned",
    overview: "Connect fleet financials to Xero for streamlined bookkeeping and automated reconciliation.",
    capabilities: ["Invoice sync", "Bank reconciliation", "Contact sync", "Tracking categories", "Multi-entity support"],
    setup: "Planned: OAuth connection with organization selection and chart of accounts mapping.",
    requirements: ["Xero organization with Standard or higher plan", "Operion Professional plan"],
    docsHref: "#",
  },
  {
    id: "slack",
    name: "Slack",
    category: "Communication",
    status: "available",
    overview: "Send automated dispatch alerts, delivery notifications, and exception reports to your team's Slack channels.",
    capabilities: ["Dispatch alerts", "Delivery confirmations", "Exception notifications", "Daily fleet summary", "Driver check-in reminders"],
    setup: "Install the Operion app from Slack App Directory. Authorize workspace and select default channels per alert type.",
    requirements: ["Slack workspace with app installation permissions", "Operion Starter plan or higher"],
    docsHref: "#",
  },
  {
    id: "teams",
    name: "Microsoft Teams",
    category: "Communication",
    status: "planned",
    overview: "Native Teams integration for fleet alerts, collaboration, and document sharing within your organization.",
    capabilities: ["Channel notifications", "Adaptive card alerts", "Document sharing", "Approval workflows", "Meeting scheduling"],
    setup: "Planned: Azure AD app registration with Teams channel webhooks and adaptive card templates.",
    requirements: ["Microsoft 365 Business or Enterprise", "Teams admin consent", "Operion Professional plan"],
    docsHref: "#",
  },
  {
    id: "powerbi",
    name: "Power BI",
    category: "Analytics",
    status: "available",
    overview: "Export Operion fleet data to Power BI for custom dashboards, executive reporting, and advanced analytics.",
    capabilities: ["Fleet performance dashboards", "Cost per mile analysis", "Driver utilization reports", "Custom DAX measures", "Scheduled refresh"],
    setup: "Connect via Operion's Power BI connector. Authenticate with API key and select data entities to import.",
    requirements: ["Power BI Pro or Premium", "Operion API access", "Operion Enterprise plan"],
    docsHref: "#",
  },
  {
    id: "tableau",
    name: "Tableau",
    category: "Analytics",
    status: "beta",
    overview: "Direct connector for Tableau to build visual analytics on top of Operion's logistics data warehouse.",
    capabilities: ["Live query support", "Extract refresh scheduling", "Custom geospatial maps", "Blended data sources", "Published workbook sync"],
    setup: "Download the Operion Tableau connector. Configure server URL and API credentials. Build workbooks against published data sources.",
    requirements: ["Tableau Desktop 2024.1+ or Tableau Cloud", "Operion Enterprise plan", "Beta program enrollment"],
    docsHref: "#",
  },
  {
    id: "sap",
    name: "SAP S/4HANA",
    category: "ERP",
    status: "planned",
    overview: "Bi-directional sync between Operion and SAP for logistics, procurement, and financial operations.",
    capabilities: ["Purchase order sync", "Inventory allocation", "Financial posting", "Master data exchange", "Transportation planning"],
    setup: "Planned: RFC connector with BAPI mapping and IDoc message types for real-time exchange.",
    requirements: ["SAP S/4HANA 2022 or later", "RFC destination configuration", "Operion Enterprise plan"],
    docsHref: "#",
  },
  {
    id: "hubspot",
    name: "HubSpot",
    category: "Other",
    status: "available",
    overview: "Sync customer delivery data to HubSpot CRM for automated follow-ups, satisfaction surveys, and sales pipeline updates.",
    capabilities: ["Delivery event logging", "Contact enrichment", "Deal stage automation", "Ticket creation", "Email sequences"],
    setup: "Authorize via OAuth 2.0. Map delivery statuses to HubSpot lifecycle stages and configure workflow triggers.",
    requirements: ["HubSpot Professional or Enterprise", "Super admin access", "Operion Professional plan"],
    docsHref: "#",
  },
]

const categories: Category[] = ["All", "Telematics", "Accounting", "Communication", "Analytics", "ERP", "Other"]

function statusToBadge(status: Integration["status"]) {
  switch (status) {
    case "available":
      return <StatusBadge status="success" label="Available" />
    case "beta":
      return <StatusBadge status="warning" label="Beta" />
    case "planned":
      return <StatusBadge status="pending" label="Planned" />
  }
}

export default function IntegrationsExplorerPage() {
  const [search, setSearch] = useState("")
  const [activeCategory, setActiveCategory] = useState<Category>("All")
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const filtered = integrations.filter((i) => {
    const matchesSearch =
      i.name.toLowerCase().includes(search.toLowerCase()) ||
      i.overview.toLowerCase().includes(search.toLowerCase())
    const matchesCategory = activeCategory === "All" || i.category === activeCategory
    return matchesSearch && matchesCategory
  })

  return (
    <>
      <Helmet>
        <title>Integration Explorer — Operion</title>
        <meta name="description" content="Connect Operion with your entire technology stack. Browse available, beta, and planned integrations." />
      </Helmet>

      <HeroSection
        title="Integration Explorer"
        description="Connect Operion with your entire stack. Browse our growing catalog of native integrations, from telematics and accounting to analytics and ERP."
        align="center"
        size="large"
      />

      <SectionWrapper className="pt-0">
        <div className="mx-auto max-w-5xl">
          {/* Search & Filter */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-8"
          >
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search integrations by name or capability..."
                className="w-full rounded-lg border bg-background py-3 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setActiveCategory(cat)}
                  className={cn(
                    "rounded-full border px-4 py-1.5 text-sm font-medium transition-colors",
                    activeCategory === cat
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background text-muted-foreground hover:bg-muted"
                  )}
                >
                  {cat}
                </button>
              ))}
            </div>
          </motion.div>

          {/* Integration Cards */}
          <div className="space-y-4">
            <AnimatePresence mode="popLayout">
              {filtered.map((integration, i) => {
                const isExpanded = expandedId === integration.id
                return (
                  <motion.div
                    key={integration.id}
                    layout
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    transition={{ duration: 0.25, delay: i * 0.05 }}
                  >
                    <Card className="overflow-hidden">
                      <button
                        type="button"
                        onClick={() => setExpandedId(isExpanded ? null : integration.id)}
                        className="flex w-full items-center justify-between p-5 text-left transition-colors hover:bg-muted/30"
                      >
                        <div className="flex items-center gap-4">
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary">
                            <Plug className="h-5 w-5" />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="font-semibold">{integration.name}</h3>
                              {statusToBadge(integration.status)}
                            </div>
                            <p className="mt-0.5 text-sm text-muted-foreground">{integration.overview}</p>
                          </div>
                        </div>
                        <motion.div
                          animate={{ rotate: isExpanded ? 180 : 0 }}
                          transition={{ duration: 0.2 }}
                        >
                          <ChevronDown className="h-5 w-5 text-muted-foreground" />
                        </motion.div>
                      </button>

                      <AnimatePresence>
                        {isExpanded && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                            className="overflow-hidden"
                          >
                            <CardContent className="border-t bg-muted/20 px-5 py-5">
                              <div className="grid gap-6 md:grid-cols-2">
                                <div>
                                  <h4 className="flex items-center gap-2 text-sm font-semibold">
                                    <ListChecks className="h-4 w-4 text-primary" />
                                    Capabilities
                                  </h4>
                                  <ul className="mt-3 space-y-2">
                                    {integration.capabilities.map((cap) => (
                                      <li key={cap} className="flex items-start gap-2 text-sm text-muted-foreground">
                                        <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                                        {cap}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                                <div className="space-y-5">
                                  <div>
                                    <h4 className="flex items-center gap-2 text-sm font-semibold">
                                      <Wrench className="h-4 w-4 text-primary" />
                                      Setup
                                    </h4>
                                    <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                                      {integration.setup}
                                    </p>
                                  </div>
                                  <div>
                                    <h4 className="flex items-center gap-2 text-sm font-semibold">
                                      <BookOpen className="h-4 w-4 text-primary" />
                                      Requirements
                                    </h4>
                                    <ul className="mt-2 space-y-1">
                                      {integration.requirements.map((req) => (
                                        <li key={req} className="text-sm text-muted-foreground">
                                          {req}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                </div>
                              </div>
                              <div className="mt-5 flex items-center gap-3">
                                <Button variant="outline" size="sm" asChild>
                                  <a href={integration.docsHref}>
                                    Documentation
                                    <ArrowRight className="ml-1 h-3.5 w-3.5" />
                                  </a>
                                </Button>
                                {integration.status === "available" && (
                                  <Button size="sm">Connect</Button>
                                )}
                                {integration.status === "beta" && (
                                  <Badge variant="secondary">Join Beta</Badge>
                                )}
                                {integration.status === "planned" && (
                                  <Badge variant="outline">Coming Soon</Badge>
                                )}
                              </div>
                            </CardContent>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </Card>
                  </motion.div>
                )
              })}
            </AnimatePresence>
          </div>

          {filtered.length === 0 && (
            <div className="py-16 text-center">
              <Search className="mx-auto h-10 w-10 text-muted-foreground/50" />
              <p className="mt-4 text-muted-foreground">No integrations match your search.</p>
              <Button
                variant="link"
                className="mt-2"
                onClick={() => {
                  setSearch("")
                  setActiveCategory("All")
                }}
              >
                Clear filters
              </Button>
            </div>
          )}
        </div>
      </SectionWrapper>

      {/* Request Integration CTA */}
      <SectionWrapper className="pb-24">
        <CtaBanner
          title="Can't find what you need?"
          description="We're always expanding our integration catalog. Tell us what you need and we'll prioritize it."
          buttonText="Request an integration"
          buttonHref="mailto:integrations@operion.com"
          variant="outline"
        />
      </SectionWrapper>
    </>
  )
}

function cn(...inputs: (string | undefined | false | null)[]) {
  return inputs.filter(Boolean).join(" ")
}
