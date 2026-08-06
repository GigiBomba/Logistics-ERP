import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import {
  Truck,
  Smartphone,
  Wifi,
  WifiOff,
  Building2,
  Eye,
  Loader2,
  AlertTriangle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Callout } from "@/components/ui/callout"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { StatCard } from "@/components/shared/stat-card"
import { EmptyState } from "@/components/shared/empty-state"
import { useAdminCompanyRowCounts } from "@/services/queries"
import { RequireRole } from "@/components/auth/require-role"
import { useLocale } from "@/i18n/locale-context"

// ─── Mock cross-tenant device data ────────────────────────────

interface CrossTenantDevice {
  id: string
  company: string
  name: string
  plate: string
  status: "online" | "offline"
  lastSeen: string
  driver: string
}

const MOCK_COMPANIES = [
  "TransLogistic SRL",
  "EuroFleet Solutions",
  "CargoConnect GmbH",
  "SpeedHaul Logistics",
  "GreenWay Transport",
  "FastTrack Delivery",
] as const

const MOCK_TRUCK_NAMES = [
  "Mercedes Actros 1845",
  "Volvo FH 460",
  "Scania R 450",
  "MAN TGX 18.510",
  "DAF XF 480",
  "Iveco S-Way 460",
  "Renault T 520",
  "Mercedes Arocs 4163",
] as const

const MOCK_PLATES = [
  "B-123-ABC",
  "B-456-DEF",
  "B-789-GHI",
  "CT-12-BOS",
  "CT-45-ABC",
  "CT-78-XYZ",
  "IS-90-LMN",
  "TM-01-PQR",
  "BV-22-STU",
  "AG-56-VWX",
] as const

const MOCK_DRIVERS = [
  "Mihai Popescu",
  "Andrei Ionescu",
  "Ion Georgescu",
  "Cristian Dumitru",
  "Alexandru Stan",
  "Florin Matei",
  "George Vasile",
  "Daniel Radu",
] as const

function generateMockDevices(): CrossTenantDevice[] {
  const devices: CrossTenantDevice[] = []
  let id = 1

  for (const company of MOCK_COMPANIES) {
    const deviceCount = Math.floor(Math.random() * 6) + 2 // 2-7 devices per company
    for (let i = 0; i < deviceCount; i++) {
      const name = MOCK_TRUCK_NAMES[Math.floor(Math.random() * MOCK_TRUCK_NAMES.length)]
      const plate = MOCK_PLATES[Math.floor(Math.random() * MOCK_PLATES.length)]
      const driver = MOCK_DRIVERS[Math.floor(Math.random() * MOCK_DRIVERS.length)]
      const isOnline = Math.random() > 0.35 // ~65% online
      const hoursAgo = isOnline ? Math.floor(Math.random() * 4) : Math.floor(Math.random() * 72) + 1

      const lastSeen = new Date(Date.now() - hoursAgo * 60 * 60 * 1000).toISOString()

      devices.push({
        id: `dev-${id++}`,
        company,
        name,
        plate,
        status: isOnline ? "online" : "offline",
        lastSeen,
        driver,
      })
    }
  }

  return devices
}

function formatRelativeTime(dateString: string) {
  const now = Date.now()
  const then = new Date(dateString).getTime()
  const diffMs = now - then
  const diffMinutes = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMinutes < 1) return "Just now"
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

// ─── Page Component ───────────────────────────────────────────

export default function AdminDevicesPage() {
  const { t } = useLocale()
  const { data: rowCounts, isLoading: countsLoading, error: countsError } = useAdminCompanyRowCounts()

  const [companyFilter, setCompanyFilter] = useState<string>("all")
  const [statusFilter, setStatusFilter] = useState<string>("all")

  // Stable mock data across renders
  const allDevices = useMemo(() => generateMockDevices(), [])

  // Filtered devices
  const filteredDevices = useMemo(() => {
    return allDevices.filter((d) => {
      if (companyFilter !== "all" && d.company !== companyFilter) return false
      if (statusFilter !== "all" && d.status !== statusFilter) return false
      return true
    })
  }, [allDevices, companyFilter, statusFilter])

  // Stats
  const stats = useMemo(() => {
    const total = allDevices.length
    const online = allDevices.filter((d) => d.status === "online").length
    const offline = total - online
    const companies = new Set(allDevices.map((d) => d.company)).size
    return { total, online, offline, companies }
  }, [allDevices])

  // Unique company list for filter
  const companies = useMemo(
    () => [...new Set(allDevices.map((d) => d.company))].sort(),
    [allDevices]
  )

  // Extract total count from row counts if available
  const dbTotalDevices = useMemo(() => {
    if (!rowCounts || typeof rowCounts !== "object") return null
    const counts = rowCounts as Record<string, number>
    return counts.devices ?? counts.trucks ?? null
  }, [rowCounts])

  return (
    <RequireRole roles={["owner", "admin"]}>
      <Helmet>
        <title>{t("admin.devices.pageTitle")}</title>
      </Helmet>

      <PageHeader
        title={t("admin.devices.title")}
        description={t("admin.devices.subtitle")}
      >
        <Badge variant="secondary" className="text-xs font-normal">
          {t("admin.devices.badge")}
        </Badge>
      </PageHeader>

      <SectionWrapper className="pt-0">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          {/* Stats summary */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              value={countsLoading ? "—" : String(dbTotalDevices ?? stats.total)}
              label={t("admin.devices.stats.total")}
              icon={Smartphone}
            />
            <StatCard
              value={countsLoading ? "—" : String(stats.online)}
              label={t("admin.devices.stats.online")}
              icon={Wifi}
            />
            <StatCard
              value={countsLoading ? "—" : String(stats.offline)}
              label={t("admin.devices.stats.offline")}
              icon={WifiOff}
            />
            <StatCard
              value={countsLoading ? "—" : String(stats.companies)}
              label={t("admin.devices.stats.companies")}
              icon={Building2}
            />
          </div>

          {/* Error state */}
          {countsError && (
            <Callout variant="warning" className="mt-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                <span>{t("admin.devices.countsLoadError")}</span>
              </div>
            </Callout>
          )}

          {/* Filters */}
          <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-3">
              {/* Company filter */}
              <select
                value={companyFilter}
                onChange={(e) => setCompanyFilter(e.target.value)}
                className="flex h-9 w-[200px] rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="all">{t("admin.devices.filter.allCompanies")}</option>
                {companies.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>

              {/* Status filter */}
              <div className="flex overflow-hidden rounded-md border">
                {["all", "online", "offline"].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setStatusFilter(val)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors ${
                      statusFilter === val
                        ? "bg-primary text-primary-foreground"
                        : "bg-background text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    {val === "online" && <Wifi className="h-3.5 w-3.5" />}
                    {val === "offline" && <WifiOff className="h-3.5 w-3.5" />}
                    {val === "all" ? t("admin.devices.filter.all") : t(`admin.devices.filter.${val}`)}
                  </button>
                ))}
              </div>
            </div>

            <div className="text-sm text-muted-foreground">
              {t("admin.devices.showing")}:{" "}
              <span className="font-medium text-foreground">{filteredDevices.length}</span> {t("admin.devices.of")}{" "}
              <span className="font-medium text-foreground">{allDevices.length}</span>
            </div>
          </div>

          {/* Loading state */}
          {countsLoading && (
            <div className="mt-8 flex items-center justify-center py-12">
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
              </div>
            </div>
          )}

          {/* Device table */}
          {!countsLoading && (
            <div className="mt-4 overflow-hidden rounded-lg border">
              {filteredDevices.length === 0 ? (
                <EmptyState
                  icon={<Truck className="h-8 w-8" />}
                  title={t("admin.devices.empty.title")}
                  description={t("admin.devices.empty.description")}
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                          {t("admin.devices.table.company")}
                        </th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                          {t("admin.devices.table.name")}
                        </th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                          {t("admin.devices.table.plate")}
                        </th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                          {t("admin.devices.table.status")}
                        </th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                          {t("admin.devices.table.lastSeen")}
                        </th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                          {t("admin.devices.table.driver")}
                        </th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                          {t("admin.devices.table.actions")}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDevices.map((device) => (
                        <tr
                          key={device.id}
                          className="border-b last:border-0 hover:bg-muted/30 transition-colors"
                        >
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
                              <span className="font-medium">{device.company}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <Truck className="h-4 w-4 text-muted-foreground shrink-0" />
                              <span>{device.name}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-xs">
                            {device.plate}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <div className="flex items-center gap-1.5">
                              <span
                                className={`inline-block h-2 w-2 rounded-full ${
                                  device.status === "online"
                                    ? "bg-green-500"
                                    : "bg-red-500"
                                }`}
                              />
                              <span
                                className={
                                  device.status === "online"
                                    ? "text-green-600"
                                    : "text-red-600"
                                }
                              >
                                {device.status === "online" ? t("admin.devices.status.online") : t("admin.devices.status.offline")}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">
                            {formatRelativeTime(device.lastSeen)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">{device.driver}</td>
                          <td className="px-4 py-3 text-right whitespace-nowrap">
                            <Button variant="ghost" size="sm">
                              <Eye className="mr-1.5 h-3.5 w-3.5" />
                              {t("admin.devices.table.viewDetails")}
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Row count from DB (if available) */}
          {dbTotalDevices !== null && !countsLoading && (
            <div className="mt-4 text-xs text-muted-foreground">
              <span className="italic">
                {t("admin.devices.dbInfo")}: {dbTotalDevices} {t("admin.devices.totalDevices")}
                {rowCounts && typeof rowCounts === "object" && (
                  <>
                    {" · "}
                    {Object.entries(rowCounts as Record<string, number>)
                      .filter(([key]) => key !== "devices" && key !== "trucks")
                      .slice(0, 4)
                      .map(([table, count]) => `${table}: ${count}`)
                      .join(" · ")}
                  </>
                )}
              </span>
            </div>
          )}
        </motion.div>
      </SectionWrapper>
    </RequireRole>
  )
}
