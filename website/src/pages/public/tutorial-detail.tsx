import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useParams, Link } from "react-router"
import { ArrowLeft, Calendar, Clock, Signal, BarChart3, BookOpen } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { TableOfContents } from "@/components/shared/table-of-contents"
import { SocialShare } from "@/components/shared/social-share"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
import { useTutorial } from "@/services/queries"
import { formatDate } from "@/lib/utils"
import { cn } from "@/lib/utils"

interface MockTutorialDetail {
  title: string
  slug: string
  excerpt: string
  category: string
  difficulty: "Beginner" | "Intermediate" | "Advanced"
  reading_time_minutes: number
  published_at: string
  updated_at: string
  content: React.ReactNode
}

const RELATED_TUTORIALS = [
  {
    title: "Setting Up Your Fleet in 15 Minutes",
    slug: "setting-up-your-fleet",
    excerpt: "Add vehicles, define capacity profiles, upload inspection documents, and invite drivers.",
    category: "Fleet Manager",
    difficulty: "Beginner" as const,
    reading_time_minutes: 15,
    published_at: "2026-07-02T08:00:00Z",
  },
  {
    title: "OCR Document Scanning for Invoices",
    slug: "ocr-document-scanning-invoices",
    excerpt: "Configure Operion's OCR engine to scan invoices, CMRs, and delivery receipts.",
    category: "OCR",
    difficulty: "Intermediate" as const,
    reading_time_minutes: 14,
    published_at: "2026-06-20T09:00:00Z",
  },
  {
    title: "AI Route Optimization Deep Dive",
    slug: "ai-route-optimization-deep-dive",
    excerpt: "Learn how Operion's AI engine balances fuel cost, delivery windows, and traffic.",
    category: "AI Assistant",
    difficulty: "Intermediate" as const,
    reading_time_minutes: 18,
    published_at: "2026-06-18T08:00:00Z",
  },
]

function getCategoryColor(category: string): string {
  switch (category) {
    case "Beginner":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100"
    case "Intermediate":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100"
    case "Advanced":
      return "bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-100"
    case "Administrator":
      return "bg-violet-100 text-violet-800 dark:bg-violet-900 dark:text-violet-100"
    case "Dispatcher":
      return "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-100"
    case "Fleet Manager":
      return "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-100"
    case "Driver":
      return "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-100"
    case "Installation":
      return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100"
    case "AI Assistant":
      return "bg-fuchsia-100 text-fuchsia-800 dark:bg-fuchsia-900 dark:text-fuchsia-100"
    case "OCR":
      return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100"
    case "Analytics":
      return "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-100"
    default:
      return "bg-secondary text-secondary-foreground"
  }
}

function getDifficultyVariant(difficulty: string) {
  switch (difficulty) {
    case "Beginner":
      return "success"
    case "Intermediate":
      return "secondary"
    case "Advanced":
      return "destructive"
    default:
      return "outline"
  }
}

function getDifficultyIcon(difficulty: string) {
  switch (difficulty) {
    case "Beginner":
      return <Signal className="h-3 w-3" />
    case "Intermediate":
      return <BarChart3 className="h-3 w-3" />
    case "Advanced":
      return <BarChart3 className="h-3 w-3" />
    default:
      return null
  }
}

const MOCK_TUTORIALS: Record<string, MockTutorialDetail> = {
  "your-first-route-plan": {
    title: "Your First Route Plan: A Beginner's Guide",
    slug: "your-first-route-plan",
    excerpt:
      "Learn how to create your first optimized route in Operion. Import stops, set constraints, and dispatch to a driver in under 10 minutes.",
    category: "Beginner",
    difficulty: "Beginner",
    reading_time_minutes: 8,
    published_at: "2026-07-05T09:00:00Z",
    updated_at: "2026-07-05T09:00:00Z",
    content: (
      <>
        <p>
          Route planning is the core of Operion ERP. This tutorial walks you through creating your first optimized route from scratch. By the end, you will have a live route assigned to a driver with turn-by-turn navigation.
        </p>

        <h2 id="step-1-prepare-your-data">Step 1: Prepare Your Data</h2>
        <p>
          Before you open the route planner, gather your delivery stops. You need addresses or GPS coordinates for each stop, plus any time windows or priority notes. Operion accepts CSV, Excel, and manual entry.
        </p>
        <p>
          The minimum required fields are: stop name, address, and expected service time. Optional fields include time windows, contact phone, and delivery notes.
        </p>

        <h2 id="step-2-create-a-new-route">Step 2: Create a New Route</h2>
        <p>
          Navigate to <strong>Route Planning &gt; New Route</strong>. Select your depot as the starting point. The depot is where your vehicles load and where routes begin and end.
        </p>
        <p>
          Click <strong>Import Stops</strong> and upload your file. Operion will geocode each address and place it on the map. Review any addresses that fail geocoding and correct them manually.
        </p>

        <h2 id="step-3-set-constraints">Step 3: Set Constraints</h2>
        <p>
          Constraints tell the optimizer what matters most to your operation. Common constraints include:
        </p>
        <ul>
          <li><strong>Vehicle capacity:</strong> Maximum weight or volume per route.</li>
          <li><strong>Driver shift length:</strong> Hard limit on total driving and service hours.</li>
          <li><strong>Time windows:</strong> Customer-specified delivery windows.</li>
          <li><strong>Priority stops:</strong> Stops that must be visited first or at a specific time.</li>
        </ul>
        <p>
          For your first route, start with just vehicle capacity and driver shift length. You can add complexity later.
        </p>

        <h2 id="step-4-run-optimization">Step 4: Run Optimization</h2>
        <p>
          Click <strong>Optimize</strong>. The engine will sequence your stops to minimize total driving time while respecting all constraints. Results typically appear in under five seconds for routes with fewer than 50 stops.
        </p>
        <p>
          Review the suggested route on the map. Drag stops to reorder if needed. The optimizer will recalculate the route in real time as you make changes.
        </p>

        <h2 id="step-5-assign-and-dispatch">Step 5: Assign and Dispatch</h2>
        <p>
          Select a driver and vehicle from the dropdown. Click <strong>Dispatch</strong>. The driver receives the route instantly on their mobile app, including turn-by-turn navigation and delivery instructions.
        </p>
        <p>
          From the dispatch dashboard, you can track the driver's progress in real time, receive proof of delivery at each stop, and re-optimize if traffic conditions change.
        </p>
      </>
    ),
  },
  "ocr-document-scanning-invoices": {
    title: "OCR Document Scanning for Invoices",
    slug: "ocr-document-scanning-invoices",
    excerpt:
      "Configure Operion's OCR engine to scan invoices, CMRs, and delivery receipts. Validate extracted data and sync with your billing system.",
    category: "OCR",
    difficulty: "Intermediate",
    reading_time_minutes: 14,
    published_at: "2026-06-20T09:00:00Z",
    updated_at: "2026-06-20T09:00:00Z",
    content: (
      <>
        <p>
          Paper documents are a bottleneck in modern logistics. Operion's OCR pipeline turns scanned invoices, CMRs, and delivery receipts into structured data you can search, validate, and sync with your ERP. This tutorial covers setup, configuration, and validation workflows.
        </p>

        <h2 id="step-1-enable-the-ocr-module">Step 1: Enable the OCR Module</h2>
        <p>
          Go to <strong>Settings &gt; Modules &gt; Document Intelligence</strong> and toggle <strong>OCR Engine</strong> to on. The module requires an active subscription tier that includes document processing credits.
        </p>
        <p>
          Once enabled, the engine supports 18 languages out of the box. Verify that your primary document languages are listed. If not, contact support to request a language pack.
        </p>

        <h2 id="step-2-configure-document-types">Step 2: Configure Document Types</h2>
        <p>
          Operion recognizes documents by layout, not just text. Navigate to <strong>Document Management &gt; OCR Templates</strong> and select the document types you process:
        </p>
        <ul>
          <li><strong>Invoice:</strong> Extracts vendor, date, line items, totals, and tax.</li>
          <li><strong>CMR / Bill of Lading:</strong> Extracts sender, receiver, goods description, and weight.</li>
          <li><strong>Delivery Receipt:</strong> Extracts recipient signature, timestamp, and condition notes.</li>
          <li><strong>Fuel Receipt:</strong> Extracts station, volume, price per liter, and total cost.</li>
        </ul>
        <p>
          Each template defines the fields the OCR should look for and their expected locations on the page. You can customize templates if your documents deviate from standard layouts.
        </p>

        <h2 id="step-3-upload-and-process">Step 3: Upload and Process</h2>
        <p>
          Upload documents via the web interface, mobile app camera, or email forwarding. Bulk uploads are supported via ZIP files or folder sync. The engine processes most documents in under three seconds.
        </p>
        <p>
          During processing, each document passes through three stages: image cleanup, text recognition, and field extraction. Low-confidence fields are flagged for manual review.
        </p>

        <h2 id="step-4-validate-extracted-data">Step 4: Validate Extracted Data</h2>
        <p>
          Open the <strong>Validation Queue</strong> to review flagged documents. The interface shows the original scan side-by-side with the extracted fields. Click any field to correct it. Corrections train the model for future documents of the same type.
        </p>
        <p>
          Set validation rules to auto-approve high-confidence extractions. For example, you can auto-approve invoices from known vendors when the total amount matches the expected range.
        </p>

        <h2 id="step-5-sync-with-your-billing-system">Step 5: Sync with Your Billing System</h2>
        <p>
          Once validated, documents can flow into your billing or ERP system automatically. Go to <strong>Integrations &gt; Document Sync</strong> and configure the target system. Supported targets include SAP, Microsoft Dynamics, QuickBooks, and generic REST endpoints.
        </p>
        <p>
          Map Operion fields to your ERP fields using the visual field mapper. Schedule sync jobs hourly, daily, or in real time via webhook.
        </p>
      </>
    ),
  },
  "ai-route-optimization-deep-dive": {
    title: "AI Route Optimization Deep Dive",
    slug: "ai-route-optimization-deep-dive",
    excerpt:
      "Learn how Operion's AI engine balances fuel cost, delivery windows, driver hours, and traffic to generate near-optimal routes.",
    category: "AI Assistant",
    difficulty: "Intermediate",
    reading_time_minutes: 18,
    published_at: "2026-06-18T08:00:00Z",
    updated_at: "2026-06-18T08:00:00Z",
    content: (
      <>
        <p>
          Operion's AI route optimizer is not a simple shortest-path calculator. It is a multi-objective solver that balances competing priorities—fuel cost, customer satisfaction, driver welfare, and operational constraints—to produce routes that are genuinely better, not just shorter.
        </p>

        <h2 id="step-1-understand-the-objectives">Step 1: Understand the Objectives</h2>
        <p>
          Before you configure optimization settings, understand what the engine is trying to achieve. The default objective is a weighted blend of:
        </p>
        <ul>
          <li><strong>Total driving time:</strong> Shorter routes save fuel and labor.</li>
          <li><strong>On-time performance:</strong> Hitting customer time windows matters more than raw distance.</li>
          <li><strong>Driver compliance:</strong> Breaks, shift limits, and route familiarity reduce turnover and accidents.</li>
          <li><strong>Vehicle wear:</strong> Avoiding rough roads and excessive idling extends maintenance intervals.</li>
        </ul>
        <p>
          You can adjust the weights in <strong>Route Planning &gt; Optimization Settings</strong>. A delivery-focused operation should increase the on-time weight. A long-haul operation should prioritize driving time and vehicle wear.
        </p>

        <h2 id="step-2-configure-traffic-integration">Step 2: Configure Traffic Integration</h2>
        <p>
          Live traffic data is the single biggest improvement you can make to route quality. Enable <strong>Real-Time Traffic</strong> in the optimization settings. The system ingests flow speeds and incident reports every 60 seconds.
        </p>
        <p>
          Traffic integration works best when your routes are planned close to execution time. If you plan routes the night before, enable <strong>Predictive Traffic</strong> which uses historical patterns for the planned departure time.
        </p>

        <h2 id="step-3-set-soft-and-hard-constraints">Step 3: Set Soft and Hard Constraints</h2>
        <p>
          Hard constraints cannot be violated. Soft constraints can be violated at a penalty cost. This distinction is critical for realistic optimization:
        </p>
        <ul>
          <li><strong>Hard:</strong> Vehicle capacity, driver shift length, legal break requirements.</li>
          <li><strong>Soft:</strong> Preferred driver assignments, customer time windows, depot visit timing.</li>
        </ul>
        <p>
          If you make too many constraints hard, the solver may fail to find any feasible route. Start with a minimal hard-constraint set and tighten gradually.
        </p>

        <h2 id="step-4-review-ai-suggestions">Step 4: Review AI Suggestions</h2>
        <p>
          After optimization, the AI may suggest route adjustments that are not obvious from the map alone. Open the <strong>AI Insights</strong> panel to see:
        </p>
        <ul>
          <li>Stops that were reordered to avoid predicted traffic.</li>
          <li>Consolidation suggestions where two nearby stops could share a delivery window.</li>
          <li>Driver swap recommendations when a shift limit is at risk.</li>
        </ul>
        <p>
          Each suggestion includes an estimated impact on cost, time, or customer satisfaction. Accept or reject suggestions individually.
        </p>

        <h2 id="step-5-measure-and-iterate">Step 5: Measure and Iterate</h2>
        <p>
          Optimization is not a one-time setup. Use the <strong>Route Performance</strong> report to compare planned versus actual metrics. Look for systematic deviations that indicate your constraints or weights need adjustment.
        </p>
        <p>
          Common patterns to watch for: routes consistently running late suggest time windows are too tight; routes finishing early suggest capacity is underutilized; high fuel variance suggests traffic prediction needs tuning.
        </p>
      </>
    ),
  },
  "installing-operion-windows-server": {
    title: "Installing Operion ERP on Windows Server",
    slug: "installing-operion-windows-server",
    excerpt:
      "A complete walkthrough of installing Operion ERP on Windows Server 2019 or later, including database setup, IIS configuration, and firewall rules.",
    category: "Installation",
    difficulty: "Beginner",
    reading_time_minutes: 12,
    published_at: "2026-07-08T10:00:00Z",
    updated_at: "2026-07-08T10:00:00Z",
    content: (
      <>
        <p>
          This guide covers a standard on-premises installation of Operion ERP on Windows Server 2019 or Windows Server 2022. By the end, you will have a fully operational instance connected to SQL Server, served through IIS, and secured behind your corporate firewall.
        </p>

        <h2 id="step-1-system-requirements">Step 1: Verify System Requirements</h2>
        <p>
          Before beginning installation, ensure your server meets the minimum requirements:
        </p>
        <ul>
          <li>Windows Server 2019 or later (64-bit)</li>
          <li>8 GB RAM minimum (16 GB recommended for fleets over 100 vehicles)</li>
          <li>2 GB available disk space for the application (additional space for document storage)</li>
          <li>SQL Server 2019 or later, or SQL Server Express</li>
          <li>.NET Framework 4.8 or later</li>
          <li>IIS 10 with ASP.NET hosting bundle</li>
        </ul>
        <p>
          For cloud deployments on Azure or AWS, use the provided ARM and CloudFormation templates instead of this guide.
        </p>

        <h2 id="step-2-install-sql-server">Step 2: Install SQL Server</h2>
        <p>
          If you do not have an existing SQL Server instance, download SQL Server Express from Microsoft. During installation, select <strong>Mixed Mode Authentication</strong> so Operion can connect with a SQL login.
        </p>
        <p>
          Create a dedicated database named <code>OperionERP</code> and a SQL login with <code>db_owner</code> permissions. Note the server name, database name, username, and password—you will need them in Step 4.
        </p>

        <h2 id="step-3-configure-iis">Step 3: Configure IIS</h2>
        <p>
          Open IIS Manager and create a new application pool named <code>OperionAppPool</code>. Set the .NET CLR version to <strong>No Managed Code</strong> if you are using the self-contained deployment, or to <strong>v4.0</strong> for framework-dependent deployment.
        </p>
        <p>
          Create a new website bound to port 443 with a valid SSL certificate. Operion requires HTTPS for all authentication flows. Map the site to the <code>wwwroot</code> folder inside your Operion installation directory.
        </p>

        <h2 id="step-4-run-the-installer">Step 4: Run the Installer</h2>
        <p>
          Download the Operion installer from your account portal. Run it as Administrator. The wizard will prompt for:
        </p>
        <ul>
          <li>Installation directory (default: <code>C:\Operion</code>)</li>
          <li>Database connection string</li>
          <li>Application URL (the HTTPS URL you configured in IIS)</li>
          <li>Administrator email and password for the first Operion admin account</li>
        </ul>
        <p>
          The installer runs database migrations automatically. This step typically takes two to five minutes depending on server performance.
        </p>

        <h2 id="step-5-configure-firewall-and-dns">Step 5: Configure Firewall and DNS</h2>
        <p>
          Open Windows Firewall and allow inbound traffic on ports 80 and 443. If Operion is behind a corporate firewall or proxy, whitelist the following external endpoints:
        </p>
        <ul>
          <li>Map and geocoding services</li>
          <li>Traffic data feeds</li>
          <li>License validation server</li>
          <li>Email delivery service (for notifications)</li>
        </ul>
        <p>
          Create a DNS A record pointing your chosen domain to the server's IP address. Verify that <code>https://your-domain/health</code> returns a 200 OK response before proceeding.
        </p>

        <h2 id="step-6-verify-and-activate">Step 6: Verify and Activate</h2>
        <p>
          Log in with the administrator credentials you created during installation. Navigate to <strong>Settings &gt; License</strong> and enter your license key. The system will validate the key against our licensing server.
        </p>
        <p>
          Run the built-in system health check from <strong>Settings &gt; Diagnostics</strong>. It verifies database connectivity, file storage permissions, email delivery, and external API reachability. Address any warnings before inviting users.
        </p>
      </>
    ),
  },
}

const proseClasses =
  "[&_h2]:mt-10 [&_h2]:mb-4 [&_h2]:text-2xl [&_h2]:font-bold [&_h2]:tracking-tight [&_p]:mb-4 [&_p]:leading-7 [&_p]:text-muted-foreground [&_ul]:my-6 [&_ul]:ml-6 [&_ul]:list-disc [&_li]:mb-2 [&_li]:text-muted-foreground [&_strong]:font-semibold [&_strong]:text-foreground [&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-muted [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-sm [&_code]:font-mono"

function ArticleSkeleton() {
  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <Skeleton className="h-10 w-3/4" />
        <div className="flex items-center gap-4">
          <Skeleton className="h-6 w-20 rounded-full" />
          <Skeleton className="h-6 w-20 rounded-full" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>
      <div className="space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
      </div>
    </div>
  )
}

function RelatedTutorialCard({ tutorial, index }: { tutorial: (typeof RELATED_TUTORIALS)[number]; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.05 }}
    >
      <Card className="group flex h-full flex-col transition-shadow hover:shadow-md">
        <CardContent className="flex h-full flex-col p-6">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center rounded-md border border-transparent px-2.5 py-0.5 text-xs font-semibold shadow",
                getCategoryColor(tutorial.category)
              )}
            >
              {tutorial.category}
            </span>
            <Badge variant={getDifficultyVariant(tutorial.difficulty) as never} className="gap-1 text-xs">
              {getDifficultyIcon(tutorial.difficulty)}
              {tutorial.difficulty}
            </Badge>
          </div>
          <Link
            to={`/tutorials/${tutorial.slug}`}
            className="mb-2 block font-semibold leading-snug transition-colors group-hover:text-primary"
          >
            {tutorial.title}
          </Link>
          <p className="mb-4 flex-1 text-sm text-muted-foreground line-clamp-3">{tutorial.excerpt}</p>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              {tutorial.reading_time_minutes} min
            </span>
            <span>{formatDate(tutorial.published_at)}</span>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

export default function TutorialDetailPage() {
  const { slug } = useParams<{ slug: string }>()
  const { isLoading } = useTutorial(slug || "")

  const tutorial = slug ? MOCK_TUTORIALS[slug] : undefined

  const related = useMemo(() => {
    return RELATED_TUTORIALS.filter((t) => t.slug !== slug).slice(0, 3)
  }, [slug])

  const shareUrl =
    typeof window !== "undefined"
      ? window.location.href
      : `https://operion.com/tutorials/${slug}`

  if (!isLoading && !tutorial) {
    return (
      <>
        <Helmet>
          <title>Not Found — Operion</title>
        </Helmet>
        <PageHeader title="Tutorial Not Found" />
        <SectionWrapper>
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <BookOpen className="mb-4 h-12 w-12 text-muted-foreground/50" />
            <h2 className="text-xl font-semibold">This tutorial does not exist.</h2>
            <p className="mt-2 text-muted-foreground">
              The link may be outdated or the tutorial may have been moved.
            </p>
            <Link
              to="/tutorials"
              className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Tutorials
            </Link>
          </div>
        </SectionWrapper>
      </>
    )
  }

  return (
    <>
      <Helmet>
        <title>
          {tutorial ? `${tutorial.title} — Operion` : "Loading... — Operion"}
        </title>
        {tutorial && <meta name="description" content={tutorial.excerpt} />}
      </Helmet>

      <div className="py-8">
        <div className="container-wide">
          <Link
            to="/tutorials"
            className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Tutorials
          </Link>
        </div>
      </div>

      {isLoading || !tutorial ? (
        <SectionWrapper className="pt-0">
          <div className="container-wide">
            <div className="mx-auto max-w-3xl">
              <ArticleSkeleton />
            </div>
          </div>
        </SectionWrapper>
      ) : (
        <>
          {/* Header */}
          <section className="pb-8">
            <div className="container-wide">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="mx-auto max-w-3xl"
              >
                <div className="mb-6 flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-md border border-transparent px-2.5 py-0.5 text-xs font-semibold shadow",
                      getCategoryColor(tutorial.category)
                    )}
                  >
                    {tutorial.category}
                  </span>
                  <Badge variant={getDifficultyVariant(tutorial.difficulty) as never} className="gap-1 text-xs">
                    {getDifficultyIcon(tutorial.difficulty)}
                    {tutorial.difficulty}
                  </Badge>
                </div>
                <h1 className="text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
                  {tutorial.title}
                </h1>
                <p className="mt-4 text-lg text-muted-foreground">{tutorial.excerpt}</p>

                <div className="mt-6 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-4 w-4" />
                    {formatDate(tutorial.published_at)}
                  </span>
                  <span className="hidden text-border sm:inline">|</span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {tutorial.reading_time_minutes} min read
                  </span>
                  <span className="hidden text-border sm:inline">|</span>
                  <span className="text-xs text-muted-foreground">
                    Updated {formatDate(tutorial.updated_at)}
                  </span>
                </div>
              </motion.div>
            </div>
          </section>

          {/* Content */}
          <SectionWrapper className="pt-0">
            <div className="container-wide">
              <div className="grid gap-8 lg:grid-cols-[1fr_280px]">
                <div className="mx-auto w-full max-w-3xl">
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.1 }}
                  >
                    <article className={proseClasses}>{tutorial.content}</article>
                  </motion.div>

                  {/* Tags */}
                  <div className="mt-10 flex flex-wrap gap-2">
                    <Tag variant="outline">{tutorial.category}</Tag>
                    <Tag variant="outline">{tutorial.difficulty}</Tag>
                  </div>

                  {/* Social Share */}
                  <div className="mt-10 flex items-center justify-between border-t pt-6">
                    <span className="text-sm font-medium text-muted-foreground">
                      Share this tutorial
                    </span>
                    <SocialShare url={shareUrl} title={tutorial.title} />
                  </div>
                </div>

                {/* TOC Sidebar */}
                <aside className="hidden lg:block">
                  <TableOfContents />
                </aside>
              </div>
            </div>
          </SectionWrapper>

          {/* Next Steps / Related */}
          <SectionWrapper className="bg-muted/30">
            <div className="container-wide">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
              >
                <h2 className="mb-2 text-2xl font-bold tracking-tight">Next Steps</h2>
                <p className="mb-8 text-muted-foreground">
                  Continue learning with these related tutorials.
                </p>
                <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  {related.length > 0 ? (
                    related.map((t, i) => (
                      <RelatedTutorialCard key={t.slug} tutorial={t} index={i} />
                    ))
                  ) : (
                    <p className="col-span-full text-muted-foreground">
                      Related tutorials coming soon.
                    </p>
                  )}
                </div>
              </motion.div>
            </div>
          </SectionWrapper>
        </>
      )}
    </>
  )
}
