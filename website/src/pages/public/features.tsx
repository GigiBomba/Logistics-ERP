import { useEffect } from "react"
import { useLocation } from "react-router"
import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import {
  MapPin,
  Radio,
  Send,
  Scan,
  BarChart3,
  Users,
  FileText,
  Settings,
  TrendingUp,
  UserCheck,
  Calendar,
  Wrench,
  ImageIcon,
  Plug,
  Bot,
  Workflow,
  LineChart,
  Route,
  Navigation,
  Check,
} from "lucide-react"
import { PageHeader, SectionHeader } from "@/components/shared/page-header"
import { FeatureCard } from "@/components/shared/feature-card"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { FaqAccordion } from "@/components/shared/faq-accordion"
import { CtaBanner } from "@/components/shared/cta-banner"
import { Badge } from "@/components/ui/badge"

function ScreenshotPlaceholder({ name }: { name: string }) {
  const mockupContent = getMockupContent(name)
  const label = name.toLowerCase().replace(/\s+/g, "-")

  return (
    <div className="mt-8 rounded-lg border bg-card shadow-xl overflow-hidden">
      {/* Browser chrome bar */}
      <div className="flex items-center gap-1.5 px-4 py-2.5 bg-muted/50 border-b">
        <div className="h-2.5 w-2.5 rounded-full bg-red-400" />
        <div className="h-2.5 w-2.5 rounded-full bg-yellow-400" />
        <div className="h-2.5 w-2.5 rounded-full bg-green-400" />
        <div className="ml-3 flex-1 max-w-[200px] rounded-md bg-background px-3 py-1 text-[10px] text-foreground/80 border">
          app.operionerp.xyz/{label}
        </div>
      </div>
      {/* Mock content */}
      <div className="p-4">
        {mockupContent}
      </div>
    </div>
  )
}

function getMockupContent(name: string): React.ReactNode {
  switch (name) {
    case "Route Planning Dashboard":
      return <RoutePlanningMockup />
    case "Fleet Live Map":
      return <FleetLiveMapMockup />
    case "Dispatch Console":
      return <DispatchConsoleMockup />
    case "AI Copilot Dashboard":
      return <AiCopilotMockup />
    case "OCR Document Scanner":
      return <OcrScannerMockup />
    case "Analytics Dashboard":
      return <AnalyticsMockup />
    case "Driver Schedule View":
      return <DriverScheduleMockup />
    default:
      return <DefaultMockup />
  }
}

function RoutePlanningMockup() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Route className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold text-foreground/80">Route Planning</span>
      </div>
      {/* Mini map */}
      <div className="relative h-28 rounded-md border bg-gradient-to-br from-primary/5 to-accent/10 overflow-hidden">
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 300 120" preserveAspectRatio="xMidYMid meet">
          <line x1="0" y1="30" x2="300" y2="30" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
          <line x1="0" y1="60" x2="300" y2="60" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
          <line x1="0" y1="90" x2="300" y2="90" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
          <line x1="75" y1="0" x2="75" y2="120" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
          <line x1="150" y1="0" x2="150" y2="120" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
          <line x1="225" y1="0" x2="225" y2="120" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="0.5" />
          {/* Multiple route paths */}
          <path d="M 20 90 Q 70 30, 140 60 T 280 30" fill="none" stroke="currentColor" className="text-primary" strokeWidth="1.5" strokeDasharray="5 3">
            <animate attributeName="stroke-dashoffset" from="0" to="-16" dur="4s" repeatCount="indefinite" />
          </path>
          <path d="M 40 45 Q 120 80, 200 40 T 270 85" fill="none" stroke="currentColor" className="text-accent/60" strokeWidth="1" strokeDasharray="3 3">
            <animate attributeName="stroke-dashoffset" from="0" to="-12" dur="3s" repeatCount="indefinite" />
          </path>
          {/* Waypoints */}
          <circle cx="20" cy="90" r="3" fill="currentColor" className="text-muted-foreground/50" />
          <circle cx="140" cy="60" r="2.5" fill="currentColor" className="text-accent" />
          <circle cx="280" cy="30" r="3" fill="currentColor" className="text-primary" />
          <circle cx="40" cy="45" r="2" fill="currentColor" className="text-muted-foreground/40" />
          <circle cx="200" cy="40" r="2" fill="currentColor" className="text-muted-foreground/40" />
          <text x="12" y="101" className="fill-foreground/80" fontSize="5">Bucharest</text>
          <text x="260" y="24" className="fill-foreground/80" fontSize="5">Cluj</text>
        </svg>
      </div>
      {/* Route info table */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded border bg-muted/20 p-2">
          <p className="text-[9px] text-foreground/80">Distance</p>
          <p className="text-sm font-bold">486 km</p>
        </div>
        <div className="rounded border bg-muted/20 p-2">
          <p className="text-[9px] text-foreground/80">ETA</p>
          <p className="text-sm font-bold">5h 20m</p>
        </div>
        <div className="rounded border bg-muted/20 p-2">
          <p className="text-[9px] text-foreground/80">Stops</p>
          <p className="text-sm font-bold">3</p>
        </div>
      </div>
      {/* Route entries */}
      <div className="space-y-1 text-[10px]">
        <div className="flex items-center justify-between rounded border bg-muted/10 p-1.5">
          <div className="flex items-center gap-1.5">
            <Navigation className="h-3 w-3 text-foreground/80" />
            <span className="font-medium">R-102</span>
            <span className="text-foreground/80">Bucharest → Ploiesti → Brasov → Cluj</span>
          </div>
          <Badge variant="outline" className="text-[8px] px-1.5 py-0 h-4">Optimized</Badge>
        </div>
        <div className="flex items-center justify-between rounded border bg-muted/10 p-1.5">
          <div className="flex items-center gap-1.5">
            <Navigation className="h-3 w-3 text-foreground/80" />
            <span className="font-medium">R-098</span>
            <span className="text-foreground/80">Constanta → Bucharest → Pitesti</span>
          </div>
          <Badge variant="outline" className="text-[8px] px-1.5 py-0 h-4 text-amber-700 dark:text-amber-300 border-amber-700/30 dark:border-amber-500/30">Scheduled</Badge>
        </div>
      </div>
    </div>
  )
}

function FleetLiveMapMockup() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <MapPin className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold text-foreground/80">Fleet Live Map</span>
      </div>
      {/* Mini map with truck markers */}
      <div className="relative h-28 rounded-md border bg-gradient-to-br from-primary/5 to-accent/10 overflow-hidden">
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 300 120" preserveAspectRatio="xMidYMid meet">
          <line x1="0" y1="30" x2="300" y2="30" stroke="currentColor" className="text-muted-foreground/15" strokeWidth="0.5" />
          <line x1="0" y1="60" x2="300" y2="60" stroke="currentColor" className="text-muted-foreground/15" strokeWidth="0.5" />
          <line x1="0" y1="90" x2="300" y2="90" stroke="currentColor" className="text-muted-foreground/15" strokeWidth="0.5" />
          <line x1="75" y1="0" x2="75" y2="120" stroke="currentColor" className="text-muted-foreground/15" strokeWidth="0.5" />
          <line x1="150" y1="0" x2="150" y2="120" stroke="currentColor" className="text-muted-foreground/15" strokeWidth="0.5" />
          <line x1="225" y1="0" x2="225" y2="120" stroke="currentColor" className="text-muted-foreground/15" strokeWidth="0.5" />
          {/* Roads */}
          <path d="M 0 60 Q 75 20, 150 60 T 300 60" fill="none" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="1" />
          <path d="M 75 120 L 75 0" fill="none" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="1" />
          <path d="M 225 120 L 225 0" fill="none" stroke="currentColor" className="text-muted-foreground/20" strokeWidth="1" />
          {/* Truck markers */}
          <g>
            <rect x="68" y="68" width="14" height="8" rx="2" fill="currentColor" className="text-primary" />
            <circle cx="71" cy="78" r="3" fill="currentColor" className="text-primary" />
            <circle cx="79" cy="78" r="3" fill="currentColor" className="text-primary" />
          </g>
          <g>
            <rect x="143" y="28" width="14" height="8" rx="2" fill="currentColor" className="text-accent" />
            <circle cx="146" cy="38" r="3" fill="currentColor" className="text-accent" />
            <circle cx="154" cy="38" r="3" fill="currentColor" className="text-accent" />
          </g>
          <g>
            <rect x="218" y="53" width="14" height="8" rx="2" fill="currentColor" className="text-emerald-400" />
            <circle cx="221" cy="63" r="3" fill="currentColor" className="text-emerald-400" />
            <circle cx="229" cy="63" r="3" fill="currentColor" className="text-emerald-400" />
          </g>
          {/* Labels */}
          <text x="55" y="95" className="fill-primary text-[6px] font-medium">TR-102</text>
          <text x="130" y="20" className="fill-foreground/80 dark:fill-accent text-[6px] font-medium">TR-098</text>
          <text x="205" y="80" className="fill-emerald-700 dark:fill-emerald-400 text-[6px] font-medium">TR-105</text>
        </svg>
      </div>
      {/* Vehicle status cards */}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded border bg-muted/20 p-2">
          <div className="flex items-center gap-1.5 text-[10px]">
            <div className="h-2 w-2 rounded-full bg-primary" />
            <span className="font-medium">TR-102</span>
          </div>
          <p className="text-[9px] text-foreground/80 mt-0.5">Bucharest → Cluj</p>
          <span className="text-[8px] text-primary">In Transit</span>
        </div>
        <div className="rounded border bg-muted/20 p-2">
          <div className="flex items-center gap-1.5 text-[10px]">
            <div className="h-2 w-2 rounded-full bg-accent" />
            <span className="font-medium">TR-098</span>
          </div>
          <p className="text-[9px] text-foreground/80 mt-0.5">Constanta Port</p>
          <span className="text-[8px] text-foreground/80 dark:text-accent">Loading</span>
        </div>
        <div className="rounded border bg-muted/20 p-2">
          <div className="flex items-center gap-1.5 text-[10px]">
            <div className="h-2 w-2 rounded-full bg-emerald-400" />
            <span className="font-medium">TR-105</span>
          </div>
          <p className="text-[9px] text-foreground/80 mt-0.5">Deva Yard</p>
          <span className="text-[8px] text-emerald-700 dark:text-emerald-400">Delivered</span>
        </div>
        <div className="rounded border bg-muted/20 p-2">
          <div className="flex items-center gap-1.5 text-[10px]">
            <div className="h-2 w-2 rounded-full bg-amber-400" />
            <span className="font-medium">TR-111</span>
          </div>
          <p className="text-[9px] text-foreground/80 mt-0.5">Brasov Depot</p>
          <span className="text-[8px] text-amber-700 dark:text-amber-400">Idle</span>
        </div>
      </div>
    </div>
  )
}

function DispatchConsoleMockup() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Send className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold text-foreground/80">Dispatch Console</span>
      </div>
      {/* Command input */}
      <div className="flex items-center gap-2 rounded-md border bg-muted/20 px-3 py-2 text-xs text-foreground/80">
        <Send className="h-3.5 w-3.5 shrink-0 text-foreground/60" />
        <span className="italic">Dispatch Truck 14 from Bucharest to Cluj...</span>
      </div>
      {/* Active dispatch cards */}
      <div className="space-y-1.5">
        {[
          { route: "DSP-2024-0821", driver: "Ionescu M.", from: "Bucharest", to: "Cluj-Napoca", status: "In Transit" as const },
          { route: "DSP-2024-0822", driver: "Popescu A.", from: "Constanta", to: "Brasov", status: "Loading" as const },
          { route: "DSP-2024-0823", driver: "Dumitru V.", from: "Timisoara", to: "Iasi", status: "Pending" as const },
        ].map((d) => (
          <div key={d.route} className="rounded border bg-muted/10 p-2 text-[10px] space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-medium">{d.route}</span>
              <span className={`text-[8px] px-1.5 py-0.5 rounded-full font-medium ${
                d.status === "In Transit" ? "bg-primary/20 text-primary" :
                d.status === "Loading" ? "bg-amber-700/20 dark:bg-amber-500/20 text-amber-800 dark:text-amber-300" :
                "bg-muted/50 text-foreground/80"
              }`}>{d.status}</span>
            </div>
            <div className="flex items-center gap-1.5 text-foreground/80">
              <Users className="h-3 w-3" />
              <span>{d.driver}</span>
              <span className="mx-1">·</span>
              <MapPin className="h-3 w-3" />
              <span>{d.from} → {d.to}</span>
            </div>
          </div>
        ))}
      </div>
      {/* Quick actions */}
      <div className="flex gap-1.5 pt-1">
        <Badge variant="secondary" className="text-[9px] px-2 py-0.5 cursor-default">+ New Dispatch</Badge>
        <Badge variant="outline" className="text-[9px] px-2 py-0.5 cursor-default">Batch Assign</Badge>
        <Badge variant="outline" className="text-[9px] px-2 py-0.5 cursor-default">Reports</Badge>
      </div>
    </div>
  )
}

function AiCopilotMockup() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Bot className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold text-foreground/80">AI Copilot</span>
      </div>
      {/* Chat messages */}
      <div className="space-y-2">
        <div className="flex items-start gap-2">
          <div className="h-5 w-5 rounded-full bg-primary/20 flex items-center justify-center shrink-0 mt-0.5">
            <Bot className="h-3 w-3 text-primary" />
          </div>
          <div className="rounded-lg rounded-tl-sm bg-primary/10 border border-primary/20 px-2.5 py-1.5 text-[10px]">
            <p className="text-foreground/90">I found a profitable return load for Truck X after it unloads in Poznań.</p>
            <p className="text-foreground/80 mt-1">Distance to reload: 18 km · Est. profit: +€487</p>
          </div>
        </div>
        <div className="flex items-start gap-2 justify-end">
          <div className="rounded-lg rounded-tr-sm bg-muted/30 border px-2.5 py-1.5 text-[10px] max-w-[80%]">
            <p className="text-foreground/90">Show me the route and documents.</p>
          </div>
          <div className="h-5 w-5 rounded-full bg-muted flex items-center justify-center shrink-0 mt-0.5">
            <Users className="h-3 w-3 text-muted-foreground" />
          </div>
        </div>
        <div className="flex items-start gap-2">
          <div className="h-5 w-5 rounded-full bg-primary/20 flex items-center justify-center shrink-0 mt-0.5">
            <Bot className="h-3 w-3 text-primary" />
          </div>
          <div className="rounded-lg rounded-tl-sm bg-primary/10 border border-primary/20 px-2.5 py-1.5 text-[10px]">
            <p className="text-foreground/90">All prepared. Dispatch, CMR, proforma invoice, and final invoice are ready.</p>
            <div className="flex gap-1 mt-1.5">
              <Badge variant="outline" className="text-[8px] px-1.5 py-0 h-3.5">Dispatch</Badge>
              <Badge variant="outline" className="text-[8px] px-1.5 py-0 h-3.5">CMR</Badge>
              <Badge variant="outline" className="text-[8px] px-1.5 py-0 h-3.5">Invoice</Badge>
            </div>
          </div>
        </div>
      </div>
      {/* Analytics cards */}
      <div className="grid grid-cols-2 gap-2 pt-1 border-t border-border/50">
        <div className="rounded border bg-muted/15 p-2">
          <p className="text-[9px] text-foreground/80">Today's Profit</p>
          <p className="text-sm font-bold text-emerald-700 dark:text-emerald-400">+€2,847</p>
        </div>
        <div className="rounded border bg-muted/15 p-2">
          <p className="text-[9px] text-foreground/80">Active Dispatches</p>
          <p className="text-sm font-bold">12</p>
        </div>
      </div>
    </div>
  )
}

function OcrScannerMockup() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Scan className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold text-foreground/80">Document Scanner</span>
      </div>
      {/* Document preview */}
      <div className="rounded-md border bg-gradient-to-br from-muted/30 to-muted/10 p-3 relative overflow-hidden">
        {/* Scan lines animation */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="h-0.5 w-full bg-primary/20 absolute animate-pulse" style={{ top: "40%" }} />
        </div>
        {/* Document content */}
        <div className="space-y-1.5 relative">
          <div className="flex justify-between text-[8px] text-foreground/80 border-b border-border/30 pb-1">
            <span>CMR Document</span>
            <span>#CMR-2024-0842</span>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[9px]">
            <span className="text-foreground/80">Sender:</span>
            <span className="text-foreground/80">Transilvania Logistics</span>
            <span className="text-foreground/80">Consignee:</span>
            <span className="text-foreground/80">Cluj Distribution SRL</span>
            <span className="text-foreground/80">Origin:</span>
            <span className="text-foreground/80">Bucharest, RO</span>
            <span className="text-foreground/80">Destination:</span>
            <span className="text-foreground/80">Cluj-Napoca, RO</span>
            <span className="text-foreground/80">Goods:</span>
            <span className="text-foreground/80">Electronics, 24 pallets</span>
            <span className="text-foreground/80">Weight:</span>
            <span className="text-foreground/80">12,400 kg</span>
          </div>
        </div>
      </div>
      {/* Extracted data status */}
      <div className="space-y-1">
        <div className="flex items-center gap-1.5 text-[10px]">
          <Check className="h-3 w-3 text-emerald-700 dark:text-emerald-400" />
          <span className="text-foreground/80">Text extracted successfully</span>
        </div>
        <div className="flex items-center gap-1.5 text-[10px]">
          <Check className="h-3 w-3 text-emerald-700 dark:text-emerald-400" />
          <span className="text-foreground/80">Fields mapped to shipment record</span>
        </div>
        <div className="flex items-center gap-1.5 text-[10px]">
          <div className="h-3 w-3 rounded-full border-2 border-amber-700 dark:border-amber-400" />
          <span className="text-foreground/80">Invoice pending review</span>
        </div>
      </div>
    </div>
  )
}

function AnalyticsMockup() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold text-foreground/80">Analytics</span>
      </div>
      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded border bg-muted/20 p-2">
          <p className="text-[9px] text-foreground/80">Total Revenue</p>
          <p className="text-sm font-bold text-emerald-700 dark:text-emerald-400">€124.5k</p>
          <p className="text-[8px] text-emerald-700 dark:text-emerald-400">↑ 12.3% vs last month</p>
        </div>
        <div className="rounded border bg-muted/20 p-2">
          <p className="text-[9px] text-foreground/80">Empty Km Rate</p>
          <p className="text-sm font-bold text-amber-700 dark:text-amber-400">18.2%</p>
          <p className="text-[8px] text-emerald-700 dark:text-emerald-400">↓ 4.1% vs last month</p>
        </div>
        <div className="rounded border bg-muted/20 p-2">
          <p className="text-[9px] text-foreground/80">Fleet Utilization</p>
          <p className="text-sm font-bold">76%</p>
          <p className="text-[8px] text-emerald-700 dark:text-emerald-400">↑ 5% vs last month</p>
        </div>
        <div className="rounded border bg-muted/20 p-2">
          <p className="text-[9px] text-foreground/80">On-Time Delivery</p>
          <p className="text-sm font-bold text-emerald-700 dark:text-emerald-400">94%</p>
          <p className="text-[8px] text-emerald-700 dark:text-emerald-400">↑ 2.1% vs last month</p>
        </div>
      </div>
      {/* Mini bar chart */}
      <div className="rounded border bg-muted/10 p-2.5">
        <p className="text-[9px] text-foreground/80 mb-2">Weekly Profit Trend</p>
        <div className="flex items-end gap-1.5 h-12">
          {[45, 62, 38, 71, 55, 80, 68].map((h, i) => (
            <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
              <div
                className="w-full rounded-t-sm bg-primary/60 transition-all"
                style={{ height: `${h}%` }}
              />
              <span className="text-[6px] text-foreground/80">M</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function DriverScheduleMockup() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Calendar className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold text-foreground/80">Driver Schedule</span>
      </div>
      {/* Weekday header */}
      <div className="grid grid-cols-7 gap-1 text-center">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <div key={d} className="text-[8px] text-foreground/80 font-medium py-1">{d}</div>
        ))}
      </div>
      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31].map((d) => (
          <div key={d} className={`aspect-square rounded border p-0.5 text-[8px] ${
            d === 15 ? "border-primary/40 bg-primary/10" :
            d === 22 ? "border-accent/40 bg-accent/10" :
            "border-border/50 bg-muted/10"
          }`}>
            <span className="text-foreground/80">{d}</span>
            {d === 15 && <div className="mt-0.5 h-1 rounded-full bg-primary/60" />}
            {d === 22 && <div className="mt-0.5 h-1 rounded-full bg-accent/60" />}
          </div>
        ))}
      </div>
      {/* Driver assignments */}
      <div className="space-y-1 text-[10px]">
        <div className="flex items-center justify-between rounded border bg-muted/10 p-1.5">
          <div className="flex items-center gap-1.5">
            <UserCheck className="h-3 w-3 text-emerald-700 dark:text-emerald-400" />
            <span className="font-medium">Ionescu M.</span>
            <span className="text-foreground/80">Route R-102</span>
          </div>
          <span className="text-emerald-700 dark:text-emerald-400 text-[8px]">Assigned</span>
        </div>
        <div className="flex items-center justify-between rounded border bg-muted/10 p-1.5">
          <div className="flex items-center gap-1.5">
            <UserCheck className="h-3 w-3 text-foreground/80 dark:text-accent" />
            <span className="font-medium">Popescu A.</span>
            <span className="text-foreground/80">Route R-098</span>
          </div>
          <span className="text-foreground/80 dark:text-accent text-[8px]">Loading</span>
        </div>
        <div className="flex items-center justify-between rounded border bg-muted/10 p-1.5">
          <div className="flex items-center gap-1.5">
            <UserCheck className="h-3 w-3 text-foreground/80" />
            <span className="font-medium">Dumitru V.</span>
            <span className="text-foreground/80">Available</span>
          </div>
          <span className="text-foreground/80 text-[8px]">Unassigned</span>
        </div>
      </div>
    </div>
  )
}

function DefaultMockup() {
  return (
    <div className="flex items-center justify-center h-32">
      <div className="text-center">
        <ImageIcon className="h-8 w-8 text-foreground/60 mx-auto mb-2" />
        <p className="text-xs text-foreground/80">Interface preview</p>
      </div>
    </div>
  )
}



export default function FeaturesPage() {
  const { t } = useLocale()
  const location = useLocation()

  useEffect(() => {
    if (location.hash) {
      const id = location.hash.slice(1)
      const el = document.getElementById(id)
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" })
      }
    }
  }, [location.hash])

  const categories = [
    {
      title: t("features.route.heading"),
      problem: t("features.route.problem"),
      screenshot: "Route Planning Dashboard",
      integrations: t("features.route.integrations"),
      items: [
        { icon: MapPin, title: t("features.route.planning.title"), description: t("features.route.planning.desc") },
        { icon: TrendingUp, title: t("features.route.optimization.title"), description: t("features.route.optimization.desc") },
        { icon: Radio, title: t("features.route.traffic.title"), description: t("features.route.traffic.desc") },
      ],
    },
    {
      title: t("features.fleet.heading"),
      problem: t("features.fleet.problem"),
      screenshot: "Fleet Live Map",
      integrations: t("features.fleet.integrations"),
      items: [
        { icon: Radio, title: t("features.fleet.gps.title"), description: t("features.fleet.gps.desc") },
        { icon: Wrench, title: t("features.fleet.maintenance.title"), description: t("features.fleet.maintenance.desc") },
        { icon: MapPin, title: t("features.fleet.geofencing.title"), description: t("features.fleet.geofencing.desc") },
      ],
    },
    {
      title: t("features.dispatch.heading"),
      problem: t("features.dispatch.problem"),
      screenshot: "Dispatch Console",
      integrations: t("features.dispatch.integrations"),
      items: [
        { icon: Send, title: t("features.dispatch.jobs.title"), description: t("features.dispatch.jobs.desc") },
        { icon: FileText, title: t("features.dispatch.pod.title"), description: t("features.dispatch.pod.desc") },
        { icon: TrendingUp, title: t("features.dispatch.status.title"), description: t("features.dispatch.status.desc") },
      ],
    },
    {
      title: t("features.ai.heading"),
      problem: t("features.ai.problem"),
      screenshot: "AI Copilot Dashboard",
      integrations: t("features.ai.integrations"),
      items: [
        { icon: Bot, title: t("features.ai.copilot.title"), description: t("features.ai.copilot.desc") },
        { icon: Workflow, title: t("features.ai.workflow.title"), description: t("features.ai.workflow.desc") },
        { icon: LineChart, title: t("features.ai.predictive.title"), description: t("features.ai.predictive.desc") },
      ],
    },
    {
      title: t("features.documents.heading"),
      problem: t("features.documents.problem"),
      screenshot: "OCR Document Scanner",
      integrations: t("features.documents.integrations"),
      items: [
        { icon: Scan, title: t("features.documents.ocr.title"), description: t("features.documents.ocr.desc") },
        { icon: FileText, title: t("features.documents.archive.title"), description: t("features.documents.archive.desc") },
        { icon: Settings, title: t("features.documents.invoicing.title"), description: t("features.documents.invoicing.desc") },
      ],
    },
    {
      title: t("features.analytics.heading"),
      problem: t("features.analytics.problem"),
      screenshot: "Analytics Dashboard",
      integrations: t("features.analytics.integrations"),
      items: [
        { icon: BarChart3, title: t("features.analytics.dashboards.title"), description: t("features.analytics.dashboards.desc") },
        { icon: TrendingUp, title: t("features.analytics.kpi.title"), description: t("features.analytics.kpi.desc") },
        { icon: Send, title: t("features.analytics.export.title"), description: t("features.analytics.export.desc") },
      ],
    },
    {
      title: t("features.driver.heading"),
      problem: t("features.driver.problem"),
      screenshot: "Driver Schedule View",
      integrations: t("features.driver.integrations"),
      items: [
        { icon: Users, title: t("features.driver.profiles.title"), description: t("features.driver.profiles.desc") },
        { icon: UserCheck, title: t("features.driver.performance.title"), description: t("features.driver.performance.desc") },
        { icon: Calendar, title: t("features.driver.schedule.title"), description: t("features.driver.schedule.desc") },
      ],
    },
  ]

  const featureFaqs = [
    { question: t("features.faq1.q"), answer: t("features.faq1.a") },
    { question: t("features.faq2.q"), answer: t("features.faq2.a") },
    { question: t("features.faq3.q"), answer: t("features.faq3.a") },
    { question: t("features.faq4.q"), answer: t("features.faq4.a") },
    { question: t("features.faq5.q"), answer: t("features.faq5.a") },
  ]

  return (
    <>
      <SeoHead
        title={t("features.meta.title")}
        description={t("features.meta.description")}
        canonical="https://operionerp.xyz/features"
      />
      <PageHeader
        title={t("features.title")}
        description={t("features.subtitle")}
      />
      {categories.map((category, ci) => (
        <SectionWrapper
          key={category.title}
          id={ci === 3 ? "ai" : undefined}
          className={ci % 2 === 1 ? "bg-muted/30" : ""}
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-10"
          >
            <Badge
              variant="outline"
              className="mb-3 text-xs uppercase tracking-wider"
            >
              {t("features.section.problem")}
            </Badge>
            <h2 className="text-2xl font-bold tracking-tight">
              {category.title}
            </h2>
            <p className="mt-3 max-w-2xl text-base leading-relaxed text-foreground/80">
              {category.problem}
            </p>
          </motion.div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {category.items.map((item, i) => (
              <FeatureCard key={item.title} {...item} index={i} />
            ))}
          </div>
          {category.integrations && (
            <div className="mt-6 flex items-center gap-2 text-sm text-foreground/80">
              <Plug className="h-4 w-4 shrink-0" />
              <span>{t("features.integrations")}: {category.integrations}</span>
            </div>
          )}
          <ScreenshotPlaceholder name={category.screenshot} />
        </SectionWrapper>
      ))}

      {/* FAQ */}
      <SectionWrapper>
        <SectionHeader
          title={t("features.faq")}
          description={t("features.faqSubtitle")}
          className="mb-12"
        />
        <div className="mx-auto max-w-3xl">
          <FaqAccordion items={featureFaqs} />
        </div>
      </SectionWrapper>

      {/* CTA Banner */}
      <SectionWrapper className="pb-8 md:pb-12">
        <CtaBanner
          title={t("features.cta.title")}
          description={t("features.cta.text")}
          buttonText={t("features.cta.button")}
          buttonHref="/register"
        />
      </SectionWrapper>
    </>
  )
}
