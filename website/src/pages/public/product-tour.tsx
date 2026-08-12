import { useState } from "react"
import { SeoHead } from "@/components/seo/seo-head"
import { useLocale } from "@/i18n/locale-context"
import { motion, AnimatePresence } from "motion/react"
import {
  LayoutDashboard,
  MapPin,
  Truck,
  Send,
  FileText,
  BarChart3,
  Settings,
  Search,
  Bell,
  ChevronRight,
  CheckCircle2,
  Clock,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Users,
  Euro,
  Package,
  Route,
  Info,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { StatCard } from "@/components/shared/stat-card"
import { CtaBanner } from "@/components/shared/cta-banner"
import { SectionWrapper } from "@/components/shared/section-wrapper"

type DemoPage =
  | "dashboard"
  | "routes"
  | "fleet"
  | "dispatch"
  | "invoices"
  | "analytics"
  | "settings"

const navItems: { id: DemoPage; label: string; icon: React.ElementType }[] = [
  { id: "dashboard", label: "productTour.navDashboard", icon: LayoutDashboard },
  { id: "routes", label: "productTour.navRoutes", icon: Route },
  { id: "fleet", label: "productTour.navFleet", icon: Truck },
  { id: "dispatch", label: "productTour.navDispatch", icon: Send },
  { id: "invoices", label: "productTour.navInvoices", icon: FileText },
  { id: "analytics", label: "productTour.navAnalytics", icon: BarChart3 },
  { id: "settings", label: "productTour.navSettings", icon: Settings },
]

/* ─── Page contents ─── */
function DashboardPage() {
  const { t } = useLocale()
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">{t("productTour.dashboard.welcome")}</h2>
          <p className="text-sm text-muted-foreground">{t("productTour.dashboard.todaySummary")}</p>
        </div>
        <Badge variant="outline" className="text-xs">{t("productTour.liveDemoData")}</Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard value="12" label={t("productTour.dashboard.activeTrips")} icon={Route} trend={{ direction: "up", value: "+2" }} />
        <StatCard value="18/20" label={t("productTour.dashboard.pendingLoads")} icon={Truck} trend={{ direction: "up", value: "+1" }} />
        <StatCard value="47" label={t("productTour.dashboard.driversAvailable")} icon={Package} trend={{ direction: "up", value: "+8" }} />
        <StatCard value="€3,240" label={t("productTour.dashboard.fleetStatus")} icon={Euro} trend={{ direction: "down", value: "-4%" }} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">{t("productTour.dashboard.recentActivity")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[
                { icon: CheckCircle2, color: "text-green-600", text: t("productTour.dashboard.activity1"), time: "10 min ago" },
                { icon: Truck, color: "text-blue-600", text: t("productTour.dashboard.activity2"), time: "25 min ago" },
                { icon: AlertCircle, color: "text-amber-600", text: t("productTour.dashboard.activity3"), time: "1 hr ago" },
                { icon: FileText, color: "text-purple-600", text: "Invoice INV-2026-089 marked as paid", time: "2 hr ago" },
                { icon: Users, color: "text-indigo-600", text: "Driver M. Ionescu assigned to Route #1029", time: "3 hr ago" },
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-3">
                  <item.icon className={`h-4 w-4 shrink-0 ${item.color}`} />
                  <span className="flex-1 text-sm">{item.text}</span>
                  <span className="text-xs text-muted-foreground">{item.time}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("productTour.dashboard.quickActions")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button variant="outline" size="sm" className="w-full justify-start">
              <Send className="mr-2 h-4 w-4" /> {t("productTour.dispatch.newDispatch")}
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start">
              <MapPin className="mr-2 h-4 w-4" /> {t("productTour.routes.newRoute")}
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start">
              <FileText className="mr-2 h-4 w-4" /> {t("productTour.invoices.createInvoice")}
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start">
              <Truck className="mr-2 h-4 w-4" /> {t("productTour.fleet.addVehicle")}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function RoutesPage() {
  const { t } = useLocale()
  const routes = [
    { id: "#1023", origin: "Bucharest", destination: "Cluj-Napoca", status: "In Progress", statusColor: "default" as const, driver: "M. Ionescu", eta: "4h 20m" },
    { id: "#1024", origin: "Timisoara", destination: "Arad", status: "Completed", statusColor: "success" as const, driver: "A. Popescu", eta: "—" },
    { id: "#1025", origin: "Brasov", destination: "Sibiu", status: "Scheduled", statusColor: "secondary" as const, driver: "Unassigned", eta: "Tomorrow 08:00" },
    { id: "#1026", origin: "Iasi", destination: "Bacau", status: "In Progress", statusColor: "default" as const, driver: "R. Dumitru", eta: "2h 15m" },
    { id: "#1027", origin: "Constanta", destination: "Bucharest", status: "Delayed", statusColor: "destructive" as const, driver: "V. Stan", eta: "+1h 30m" },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold tracking-tight">{t("productTour.routes.title")}</h2>
        <Button size="sm"><MapPin className="mr-1.5 h-4 w-4" /> {t("productTour.routes.newRoute")}</Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">{t("productTour.routes.activeRoutes")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {routes.map((r) => (
                <div key={r.id} className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted/40">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent">
                      <Route className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">{r.id} — {r.origin} to {r.destination}</p>
                      <p className="text-xs text-muted-foreground">Driver: {r.driver} • ETA: {r.eta}</p>
                    </div>
                  </div>
                  <Badge variant={r.statusColor === "success" ? "success" : r.statusColor} className="text-[10px]">
                    {r.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("productTour.mapView")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex aspect-square items-center justify-center rounded-lg border border-dashed bg-muted/30">
              <div className="text-center">
                <MapPin className="mx-auto h-8 w-8 text-muted-foreground/50" />
                <p className="mt-2 text-xs text-muted-foreground">{t("productTour.interactiveMap")}</p>
                <p className="text-[10px] text-muted-foreground/70">{t("productTour.poweredByMaps")}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function FleetPage() {
  const { t } = useLocale()
  const vehicles = [
    { id: "TR-01", type: "Mercedes Actros", status: "Online", statusColor: "success" as const, fuel: 78, location: "A1, km 120" },
    { id: "TR-02", type: "Volvo FH", status: "Online", statusColor: "success" as const, fuel: 45, location: "DN7, km 45" },
    { id: "TR-03", type: "Scania R500", status: "Maintenance", statusColor: "secondary" as const, fuel: 12, location: "Bucharest Depot" },
    { id: "TR-04", type: "MAN TGX", status: "Online", statusColor: "success" as const, fuel: 92, location: "A2, km 210" },
    { id: "TR-05", type: "DAF XF", status: "Offline", statusColor: "outline" as const, fuel: 0, location: "Unknown" },
    { id: "TR-06", type: "Iveco S-Way", status: "Online", statusColor: "success" as const, fuel: 63, location: "DN1, km 88" },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold tracking-tight">{t("productTour.fleet.title")}</h2>
        <div className="flex gap-2">
          <Badge variant="success" className="text-[10px]">4 Online</Badge>
          <Badge variant="secondary" className="text-[10px]">1 Maintenance</Badge>
          <Badge variant="outline" className="text-[10px]">1 Offline</Badge>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {vehicles.map((v) => (
          <Card key={v.id} className="transition-shadow hover:shadow-md">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent">
                    <Truck className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-sm">{v.id}</CardTitle>
                    <CardDescription className="text-xs">{v.type}</CardDescription>
                  </div>
                </div>
                <Badge variant={v.statusColor} className="text-[10px]">{v.status}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <MapPin className="h-3.5 w-3.5" />
                {v.location}
              </div>
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t("productTour.fuel")}</span>
                  <span className="font-medium">{v.fuel}%</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-muted">
                  <div
                    className={`h-1.5 rounded-full ${v.fuel > 50 ? "bg-green-600" : v.fuel > 20 ? "bg-amber-500" : "bg-red-500"}`}
                    style={{ width: `${v.fuel}%` }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function DispatchPage() {
  const { t } = useLocale()
  const jobs = [
    { id: "#4521", client: "Metro Logistics", priority: "High", priorityColor: "destructive" as const, driver: "M. Ionescu", status: "Assigned", deadline: "Today 14:00" },
    { id: "#4522", client: "FreshFood SRL", priority: "Medium", priorityColor: "secondary" as const, driver: "A. Popescu", status: "In Transit", deadline: "Today 16:30" },
    { id: "#4523", client: "BuildMax", priority: "Low", priorityColor: "outline" as const, driver: "Unassigned", status: "Pending", deadline: "Tomorrow 09:00" },
    { id: "#4524", client: "EuroTransport", priority: "High", priorityColor: "destructive" as const, driver: "R. Dumitru", status: "Assigned", deadline: "Today 18:00" },
    { id: "#4525", client: "AgroPack", priority: "Medium", priorityColor: "secondary" as const, driver: "V. Stan", status: "In Transit", deadline: "Today 20:00" },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold tracking-tight">{t("productTour.dispatch.title")}</h2>
        <Button size="sm"><Send className="mr-1.5 h-4 w-4" /> {t("productTour.dispatch.newDispatch")}</Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="divide-y">
            {jobs.map((j) => (
              <div key={j.id} className="flex items-center justify-between p-4 transition-colors hover:bg-muted/30">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent">
                    <Package className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{j.id} — {j.client}</p>
                    <p className="text-xs text-muted-foreground">Driver: {j.driver} • Deadline: {j.deadline}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={j.priorityColor} className="text-[10px]">{j.priority}</Badge>
                  <Badge variant="outline" className="text-[10px]">{j.status}</Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function InvoicesPage() {
  const { t } = useLocale()
  const invoices = [
    { id: "INV-2026-001", client: "Metro Logistics", amount: 1240, status: "Paid", date: "2026-07-01" },
    { id: "INV-2026-002", client: "FreshFood SRL", amount: 890, status: "Pending", date: "2026-07-03" },
    { id: "INV-2026-003", client: "BuildMax", amount: 2340, status: "Paid", date: "2026-07-05" },
    { id: "INV-2026-004", client: "EuroTransport", amount: 1560, status: "Overdue", date: "2026-06-28" },
    { id: "INV-2026-005", client: "AgroPack", amount: 670, status: "Pending", date: "2026-07-08" },
  ]

  const total = invoices.reduce((s, i) => s + i.amount, 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold tracking-tight">{t("productTour.invoices.title")}</h2>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">{t("productTour.totalOutstanding")} <span className="font-semibold text-foreground">€{total.toLocaleString()}</span></span>
          <Button size="sm"><FileText className="mr-1.5 h-4 w-4" /> {t("productTour.invoices.createInvoice")}</Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="grid grid-cols-12 gap-4 border-b bg-muted/40 px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
            <div className="col-span-3">{t("productTour.invoiceHeader")}</div>
            <div className="col-span-3">{t("productTour.clientHeader")}</div>
            <div className="col-span-2">{t("productTour.dateHeader")}</div>
            <div className="col-span-2 text-right">{t("productTour.amountHeader")}</div>
            <div className="col-span-2 text-right">{t("productTour.statusHeader")}</div>
          </div>
          <div className="divide-y">
            {invoices.map((inv) => (
              <div key={inv.id} className="grid grid-cols-12 items-center gap-4 px-4 py-3 transition-colors hover:bg-muted/30">
                <div className="col-span-3 text-sm font-medium">{inv.id}</div>
                <div className="col-span-3 text-sm">{inv.client}</div>
                <div className="col-span-2 text-sm text-muted-foreground">{inv.date}</div>
                <div className="col-span-2 text-right text-sm font-medium">€{inv.amount.toLocaleString()}</div>
                <div className="col-span-2 text-right">
                  <Badge
                    variant={inv.status === "Paid" ? "success" : inv.status === "Overdue" ? "destructive" : "secondary"}
                    className="text-[10px]"
                  >
                    {inv.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function AnalyticsPage() {
  const { t } = useLocale()
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold tracking-tight">{t("productTour.analytics.title")}</h2>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard value="€42,300" label={t("productTour.analytics.revenue")} icon={TrendingUp} trend={{ direction: "up", value: "+12%" }} />
        <StatCard value="1,240" label={t("productTour.analytics.profit")} icon={Route} trend={{ direction: "up", value: "+8%" }} />
        <StatCard value="98.2%" label={t("productTour.analytics.costKm")} icon={Clock} trend={{ direction: "up", value: "+1.2%" }} />
        <StatCard value="€0.42" label={t("productTour.analytics.fuelEfficiency")} icon={TrendingDown} trend={{ direction: "down", value: "-3%" }} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("productTour.analytics.revenue")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex h-48 items-end justify-between gap-2">
              {[35, 42, 38, 55, 48, 62, 58, 70, 65, 78, 72, 85].map((h, i) => (
                <div key={i} className="group relative flex flex-1 flex-col items-center gap-1">
                  <div
                    className="w-full rounded-sm bg-primary/80 transition-all group-hover:bg-primary"
                    style={{ height: `${h * 1.8}px` }}
                  />
                  <span className="text-[10px] text-muted-foreground">{i + 1}</span>
                </div>
              ))}
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground">Revenue by week (thousands EUR)</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("productTour.analytics.fuelEfficiency")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex h-48 items-end justify-between gap-2">
              {[28, 32, 30, 35, 33, 38, 36, 40, 39, 42, 41, 44].map((h, i) => (
                <div key={i} className="group relative flex flex-1 flex-col items-center gap-1">
                  <div
                    className="w-full rounded-sm bg-emerald-500/80 transition-all group-hover:bg-emerald-500"
                    style={{ height: `${h * 2.8}px` }}
                  />
                  <span className="text-[10px] text-muted-foreground">{i + 1}</span>
                </div>
              ))}
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground">{t("productTour.analytics.fuelEfficiencyValue")}</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function SettingsPage() {
  const { t } = useLocale()
  const [toggles, setToggles] = useState({
    notifications: true,
    autoDispatch: false,
    darkMode: false,
    autoInvoice: true,
    geofenceAlerts: true,
    maintenanceReminders: true,
  })

  const toggle = (key: keyof typeof toggles) =>
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }))

  const items = [
    { key: "notifications" as const, label: t("productTour.settings.pushNotif"), desc: "Receive alerts for route changes and delivery updates." },
    { key: "autoDispatch" as const, label: "Auto-Dispatch", desc: "Automatically assign jobs to the nearest available driver." },
    { key: "darkMode" as const, label: "Dark Mode", desc: "Switch the interface to a darker color scheme." },
    { key: "autoInvoice" as const, label: "Auto-Generate Invoices", desc: "Create invoices automatically when deliveries are completed." },
    { key: "geofenceAlerts" as const, label: "Geofence Alerts", desc: "Get notified when vehicles enter or exit defined zones." },
    { key: "maintenanceReminders" as const, label: "Maintenance Reminders", desc: "Receive reminders based on mileage and engine diagnostics." },
  ]

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold tracking-tight">{t("productTour.settings.title")}</h2>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("productTour.settings.general")}</CardTitle>
          <CardDescription>{t("productTour.settingsDesc")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {items.map((item) => (
            <div key={item.key} className="flex items-center justify-between rounded-lg border p-4">
              <div>
                <p className="text-sm font-medium">{item.label}</p>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
              <button
                onClick={() => toggle(item.key)}
                className={`relative h-6 w-11 rounded-full transition-colors ${toggles[item.key] ? "bg-primary" : "bg-muted"}`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-background shadow-sm transition-transform ${toggles[item.key] ? "translate-x-5" : ""}`}
                />
              </button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

const pageComponents: Record<DemoPage, React.FC> = {
  dashboard: DashboardPage,
  routes: RoutesPage,
  fleet: FleetPage,
  dispatch: DispatchPage,
  invoices: InvoicesPage,
  analytics: AnalyticsPage,
  settings: SettingsPage,
}

export default function ProductTourPage() {
  const { t } = useLocale()
  const [activePage, setActivePage] = useState<DemoPage>("dashboard")
  const [searchQuery, setSearchQuery] = useState("")

  const ActiveComponent = pageComponents[activePage]

  return (
    <>
      <SeoHead title={t("productTour.pageTitle")} description={t("productTour.metaDesc")} canonical="https://operionerp.xyz/product-tour" />

      {/* Demo Banner */}
      <div className="border-b bg-amber-50 text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
        <div className="container-wide flex items-center justify-center gap-2 py-2 text-sm">
          <Info className="h-4 w-4 shrink-0" />
          <span>{t("productTour.demoBanner")}</span>
        </div>
      </div>

      {/* Demo Container */}
      <div className="container-wide py-8">
        <Card className="overflow-hidden border shadow-lg">
          {/* Top Bar */}
          <div className="flex items-center justify-between border-b bg-card px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <Truck className="h-4 w-4" />
              </div>
              <span className="font-semibold tracking-tight">Operion ERP</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative hidden sm:block">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder={t("productTour.searchPlaceholder")}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-8 w-48 rounded-md border bg-background pl-8 pr-3 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus:ring-1 focus:ring-ring"
                />
              </div>
              <button aria-label={t("common.notifications")} className="relative rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground">
                <Bell className="h-4 w-4" />
                <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500" />
              </button>
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-xs font-bold">
                AL
              </div>
            </div>
          </div>

          <div className="flex min-h-[600px]">
            {/* Sidebar */}
            <aside className="w-56 shrink-0 border-r bg-muted/30">
              <nav className="space-y-1 p-3">
                {navItems.map((item) => {
                  const isActive = activePage === item.id
                  return (
                    <button
                      key={item.id}
                      onClick={() => setActivePage(item.id)}
                      className={`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:bg-accent hover:text-foreground"
                      }`}
                    >
                      <item.icon className="h-4 w-4" />
                      {t(item.label)}
                      {isActive && <ChevronRight className="ml-auto h-3.5 w-3.5" />}
                    </button>
                  )
                })}
              </nav>

              <div className="mt-auto border-t p-3">
                <div className="rounded-md bg-accent p-3">
                  <p className="text-xs font-medium">{t("productTour.proTip")}</p>
                  <p className="mt-1 text-[11px] text-muted-foreground leading-relaxed">
                    {t("productTour.proTipText")}
                  </p>
                </div>
              </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto bg-background p-6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activePage}
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                >
                  <ActiveComponent />
                </motion.div>
              </AnimatePresence>
            </main>
          </div>
        </Card>
      </div>

      <SectionWrapper className="pb-24 pt-8">
        <CtaBanner
          title={t("productTour.cta")}
          description="Download the desktop app and start managing your fleet with the tools you just explored."
          buttonText={t("productTour.ctaButton")}
          buttonHref="/download"
          variant="primary"
        />
      </SectionWrapper>
    </>
  )
}
