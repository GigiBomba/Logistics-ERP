import { Helmet } from "react-helmet-async"
import { Link } from "react-router"
import { motion } from "motion/react"
import {
  Key,
  Monitor,
  Smartphone,
  Server,
  Clock,
  ArrowUpRight,
  Plus,
  WifiOff,
  Users,
  CheckCircle2,
  History,
  Loader2,
} from "lucide-react"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { Callout } from "@/components/ui/callout"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { StatCard } from "@/components/shared/stat-card"
import { EmptyState } from "@/components/shared/empty-state"
import { useLicenses } from "@/services/queries"
import type { License, Device } from "@/types"

const mockLicenses: License[] = [
  {
    id: "lic-pro-001",
    org_id: "org-1",
    plan_tier: "professional",
    seats_total: 25,
    seats_used: 12,
    status: "active",
    issued_at: "2026-01-15",
    expires_at: "2027-01-15",
    renewal_date: "2027-01-15",
    features: ["Route Optimization", "Real-time Dispatch", "API Access"],
  },
  {
    id: "lic-starter-002",
    org_id: "org-1",
    plan_tier: "starter",
    seats_total: 5,
    seats_used: 3,
    status: "active",
    issued_at: "2026-03-10",
    expires_at: "2027-03-10",
    renewal_date: "2027-03-10",
    features: ["Route Optimization"],
  },
  {
    id: "lic-trial-003",
    org_id: "org-1",
    plan_tier: "enterprise",
    seats_total: 10,
    seats_used: 10,
    status: "trial",
    issued_at: "2026-07-01",
    expires_at: "2026-08-01",
    renewal_date: "2026-08-01",
    features: ["Route Optimization", "Real-time Dispatch", "API Access", "Priority Support", "Custom Integrations"],
  },
]

const mockDevices: Device[] = [
  {
    id: "dev-1",
    license_id: "lic-pro-001",
    name: "Workstation-BUCH-01",
    platform: "Windows 11",
    last_active: "2026-07-10T09:30:00Z",
    is_active: true,
  },
  {
    id: "dev-2",
    license_id: "lic-pro-001",
    name: "MacBook-Pro-M3",
    platform: "macOS Sonoma",
    last_active: "2026-07-09T16:45:00Z",
    is_active: true,
  },
  {
    id: "dev-3",
    license_id: "lic-pro-001",
    name: "iPhone-15-Dispatch",
    platform: "iOS 17",
    last_active: "2026-07-10T08:15:00Z",
    is_active: true,
  },
  {
    id: "dev-4",
    license_id: "lic-starter-002",
    name: "Warehouse-Terminal-1",
    platform: "Linux Ubuntu 22.04",
    last_active: "2026-07-08T11:20:00Z",
    is_active: true,
  },
  {
    id: "dev-5",
    license_id: "lic-trial-003",
    name: "Sales-Laptop-DELL",
    platform: "Windows 11",
    last_active: "2026-07-10T10:00:00Z",
    is_active: true,
  },
]

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function maskLicenseKey(id: string) {
  return id.slice(0, 4) + "-****-****-****-****"
}

function getPlanBadgeColor(tier: string) {
  switch (tier) {
    case "starter":
      return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100"
    case "professional":
      return "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-100"
    case "enterprise":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100"
    default:
      return "bg-muted text-muted-foreground"
  }
}

function getStatusBadgeVariant(status: string) {
  switch (status) {
    case "active":
      return "success"
    case "trial":
      return "default"
    case "expired":
      return "destructive"
    case "suspended":
      return "secondary"
    default:
      return "outline"
  }
}

function PlatformIcon({ platform }: { platform: string }) {
  if (platform.includes("iOS") || platform.includes("iPhone")) return <Smartphone className="h-4 w-4" />
  if (platform.includes("Linux") || platform.includes("Server")) return <Server className="h-4 w-4" />
  return <Monitor className="h-4 w-4" />
}

export default function LicensesPage() {
  const { data: licensesData, isLoading } = useLicenses()
  const licenses = (licensesData || mockLicenses) as unknown as typeof mockLicenses
  const devices = mockDevices

  const totalSeats = licenses.reduce((sum, l) => sum + l.seats_total, 0)
  const activeSeats = licenses.reduce((sum, l) => sum + l.seats_used, 0)
  const availableSeats = totalSeats - activeSeats
  const nextRenewal = licenses
    .filter((l) => l.renewal_date)
    .sort((a, b) => new Date(a.renewal_date!).getTime() - new Date(b.renewal_date!).getTime())[0]

  const activeDevices = devices.filter((d) => d.is_active)

  if (isLoading) {
    return (
      <SectionWrapper>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </SectionWrapper>
    )
  }

  return (
    <>
      <Helmet>
        <title>Licenses — Operion ERP</title>
      </Helmet>

      <SectionWrapper>
        {/* Page Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Licenses</h1>
              <p className="mt-2 text-muted-foreground">
                Manage your Operion licenses and devices
              </p>
            </div>
            <Button disabled>
              <Plus className="mr-2 h-4 w-4" />
              Add License
            </Button>
          </div>
        </motion.div>

        {/* Stats Row */}
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.05 }}
          >
            <StatCard value={String(totalSeats)} label="Total Seats" icon={Users} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <StatCard value={String(activeSeats)} label="Active Seats" icon={CheckCircle2} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 }}
          >
            <StatCard value={String(availableSeats)} label="Available Seats" icon={Key} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
          >
            <StatCard
              value={nextRenewal ? formatDate(nextRenewal.renewal_date!) : "—"}
              label="Next Renewal"
              icon={Clock}
            />
          </motion.div>
        </div>

        {/* License Cards */}
        <div className="mt-10 space-y-6">
          <h2 className="text-xl font-bold tracking-tight">Your Licenses</h2>
          <div className="grid gap-6 lg:grid-cols-2">
            {mockLicenses.map((license, index) => (
              <motion.div
                key={license.id}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 + index * 0.05 }}
              >
                <Card className="overflow-hidden">
                  <CardHeader className="border-b bg-muted/30">
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold ${getPlanBadgeColor(license.plan_tier)}`}
                          >
                            {license.plan_tier.charAt(0).toUpperCase() + license.plan_tier.slice(1)}
                          </span>
                          <Badge variant={getStatusBadgeVariant(license.status)}>
                            {license.status}
                          </Badge>
                        </div>
                        <p className="font-mono text-xs text-muted-foreground">
                          {maskLicenseKey(license.id)}
                        </p>
                      </div>
                      <Key className="h-5 w-5 text-muted-foreground" />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-5 p-5">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Seats used</span>
                        <span className="font-medium">
                          {license.seats_used} / {license.seats_total}
                        </span>
                      </div>
                      <Progress
                        value={(license.seats_used / license.seats_total) * 100}
                        variant={license.seats_used / license.seats_total > 0.9 ? "warning" : "default"}
                      />
                    </div>

                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Expiry / Renewal</span>
                      <span className="font-medium">
                        {license.expires_at ? formatDate(license.expires_at) : "—"}
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Button variant="link" size="sm" className="h-auto p-0" asChild>
                        <Link to={`/dashboard/licenses?license=${license.id}`}>
                          Manage Devices <ArrowUpRight className="ml-1 h-3 w-3" />
                        </Link>
                      </Button>
                      <Button variant="outline" size="sm" disabled>
                        Transfer License
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Devices Section */}
        <motion.div
          className="mt-10"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
        >
          <h2 className="text-xl font-bold tracking-tight mb-4">Devices</h2>
          <Tabs defaultValue="active">
            <TabsList className="mb-4">
              <TabsTrigger value="active">Active Devices</TabsTrigger>
              <TabsTrigger value="history">Device History</TabsTrigger>
            </TabsList>

            <TabsContent value="active" className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {activeDevices.map((device, index) => (
                  <motion.div
                    key={device.id}
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.05 * index }}
                  >
                    <Card>
                      <CardContent className="p-5">
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
                              <PlatformIcon platform={device.platform} />
                            </div>
                            <div>
                              <p className="text-sm font-medium">{device.name}</p>
                              <p className="text-xs text-muted-foreground">{device.platform}</p>
                            </div>
                          </div>
                          <Badge variant="success" className="text-[10px]">
                            Active
                          </Badge>
                        </div>
                        <div className="mt-4 flex items-center justify-between">
                          <p className="text-xs text-muted-foreground">
                            Last active: {formatDate(device.last_active)}
                          </p>
                          <Button variant="ghost" size="sm" disabled>
                            Deactivate
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="history">
              <Card>
                <CardContent className="p-6">
                  <EmptyState
                    icon={<History className="h-16 w-16" />}
                    title="Device history coming soon"
                    description="A full audit log of device activations and deactivations will be available here."
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </motion.div>

        {/* Callouts */}
        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <Callout variant="info" title="Offline Activation" icon={<WifiOff className="h-5 w-5 shrink-0 mt-0.5" />}>
              Offline license activation will be available for air-gapped environments. Contact support to request early access.
            </Callout>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 }}
          >
            <Callout variant="warning" title="Floating Licenses" icon={<Users className="h-5 w-5 shrink-0 mt-0.5" />}>
              Floating license pools for shared workstation environments are planned for Q4 2026. Stay tuned for updates.
            </Callout>
          </motion.div>
        </div>
      </SectionWrapper>
    </>
  )
}
