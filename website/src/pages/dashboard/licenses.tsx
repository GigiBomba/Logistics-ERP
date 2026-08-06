import { Helmet } from "react-helmet-async"
import { Link, useSearchParams } from "react-router"
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
  AlertTriangle,
} from "lucide-react"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { CopyButton } from "@/components/ui/copy-button"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { Callout } from "@/components/ui/callout"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { StatCard } from "@/components/shared/stat-card"
import { EmptyState } from "@/components/shared/empty-state"
import { Tooltip } from "@/components/ui/tooltip"
import { useLicenses, useLicenseDevices, useRemoveLicenseDevice } from "@/services/queries"
import { useLocale } from "@/i18n/locale-context"
import { useReducedMotion } from "@/services/accessibility"

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

function PlatformIcon({ os }: { os?: string }) {
  if (os?.includes("iOS") || os?.includes("iPhone")) return <Smartphone className="h-4 w-4" />
  if (os?.includes("Linux") || os?.includes("Server")) return <Server className="h-4 w-4" />
  return <Monitor className="h-4 w-4" />
}

export default function LicensesPage() {
  const prefersReducedMotion = useReducedMotion()
  const [searchParams] = useSearchParams()
  const { t } = useLocale()

  const { data: licensesData, isLoading: licensesLoading, error: licensesError } = useLicenses()

  const selectedLicenseId = searchParams.get("license")
  const {
    data: devices,
    isLoading: devicesLoading,
    error: devicesError,
  } = useLicenseDevices(selectedLicenseId || "")

  const removeDeviceMutation = useRemoveLicenseDevice()

  const licenseList = licensesData || []

  const totalSeats = licenseList.reduce((sum, l) => sum + l.seats, 0)
  const activeSeats = licenseList.reduce((sum, l) => sum + l.seats_used, 0)
  const availableSeats = totalSeats - activeSeats
  const nextRenewal = licenseList
    .filter((l) => l.expires_at)
    .sort((a, b) => new Date(a.expires_at!).getTime() - new Date(b.expires_at!).getTime())[0]

  const selectedLicense = licenseList.find((l) => String(l.id) === selectedLicenseId)

  function handleDeactivate(deviceId: string | number) {
    if (selectedLicenseId) {
      removeDeviceMutation.mutate({ licenseId: selectedLicenseId, deviceId })
    }
  }

  if (licensesLoading) {
    return (
      <SectionWrapper>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </SectionWrapper>
    )
  }

  if (licensesError) {
    return (
      <SectionWrapper>
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <AlertTriangle className="h-12 w-12 text-destructive" />
          <h2 className="mt-4 text-xl font-semibold">{t("licenses.failedToLoad")}</h2>
          <p className="mt-2 text-muted-foreground">{t("licenses.tryAgainLater")}</p>
        </div>
      </SectionWrapper>
    )
  }

  return (
    <>
      <Helmet>
        <title>{t("licenses.pageTitle")}</title>
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
              <h1 className="text-3xl font-bold tracking-tight">{t("licenses.title")}</h1>
              <p className="mt-2 text-muted-foreground">
                {t("licenses.description")}
              </p>
            </div>
            <Tooltip content={t("licenses.addLicenseComingSoon")}>
              <Button disabled>
                <Plus className="mr-2 h-4 w-4" />
                {t("licenses.addLicense")}
              </Button>
            </Tooltip>
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
            <StatCard value={String(totalSeats)} label={t("dashboard.licenses.totalSeats")} icon={Users} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <StatCard value={String(activeSeats)} label={t("dashboard.licenses.activeSeats")} icon={CheckCircle2} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 }}
          >
            <StatCard value={String(availableSeats)} label={t("dashboard.licenses.availableSeats")} icon={Key} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
          >
            <StatCard
              value={nextRenewal ? formatDate(nextRenewal.expires_at!) : "—"}
              label={t("dashboard.licenses.nextRenewal")}
              icon={Clock}
            />
          </motion.div>
        </div>

        {/* License Cards */}
        <div className="mt-10 space-y-6">
          <h2 className="text-xl font-bold tracking-tight">{t("licenses.yourLicenses")}</h2>
          {licenseList.length === 0 ? (
            <EmptyState
              icon={<Key className="h-16 w-16" />}
              title={t("licenses.noLicensesFound")}
              description={t("licenses.noLicensesFoundDesc")}
            />
          ) : (
            <div className="grid gap-6 lg:grid-cols-2">
              {licenseList.map((license, index) => (
                <motion.div
                  key={license.id}
                  initial={prefersReducedMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: prefersReducedMotion ? 0 : Math.min(0.1 + index * 0.05, 0.3) }}
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
                          <div className="flex items-center gap-2">
                            <p className="font-mono text-xs text-muted-foreground">
                              {maskLicenseKey(license.license_key)}
                            </p>
                            <CopyButton
                              text={license.license_key}
                              aria-label={t("licenses.copyLicenseKey").replace("{key}", license.license_key)}
                              className="h-6 px-2 py-0"
                            />
                          </div>
                        </div>
                        <Key className="h-5 w-5 text-muted-foreground" />
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-5 p-5">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground">{t("dashboard.licenses.seatsUsed")}</span>
                          <span className="font-medium">
                            {license.seats_used} / {license.seats}
                          </span>
                        </div>
                        <Progress
                          value={(license.seats_used / license.seats) * 100}
                          variant={license.seats_used / license.seats > 0.9 ? "warning" : "default"}
                        />
                      </div>

                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">{t("licenses.expiryRenewal")}</span>
                        <span className="font-medium">
                          {license.expires_at ? formatDate(license.expires_at) : "—"}
                        </span>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <Button variant="link" size="sm" className="h-auto p-0" asChild>
                          <Link to={`/dashboard/licenses?license=${license.id}`}>
                            {t("licenses.manageDevices")} <ArrowUpRight className="ml-1 h-3 w-3" />
                          </Link>
                        </Button>
                        <Tooltip content={t("licenses.addLicenseComingSoon")}>
                          <Button variant="outline" size="sm" disabled>
                            {t("licenses.transferLicense")}
                          </Button>
                        </Tooltip>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {/* Devices Section */}
        <motion.div
          className="mt-10"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
        >
          <h2 className="text-xl font-bold tracking-tight mb-4">{t("licenses.devices")}</h2>
          {!selectedLicenseId ? (
            <EmptyState
              icon={<Monitor className="h-16 w-16" />}
              title={t("licenses.selectLicense")}
              description={t("licenses.selectLicenseDesc")}
            />
          ) : devicesLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : devicesError ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <AlertTriangle className="h-10 w-10 text-destructive" />
              <h3 className="mt-3 text-lg font-semibold">{t("licenses.failedLoadDevices")}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{t("licenses.tryAgainLater")}</p>
            </div>
          ) : (
            <Tabs defaultValue="active">
              <TabsList className="mb-4">
                <TabsTrigger value="active">{t("licenses.activeDevices")}</TabsTrigger>
                <TabsTrigger value="history">{t("licenses.deviceHistory")}</TabsTrigger>
              </TabsList>

              <TabsContent value="active" className="space-y-4">
                {devices && devices.length > 0 ? (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {devices.map((device, index) => (
                      <motion.div
                        key={device.id}
                        initial={prefersReducedMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: prefersReducedMotion ? 0 : Math.min(0.05 * index, 0.3) }}
                      >
                        <Card>
                          <CardContent className="p-5">
                            <div className="flex items-start justify-between">
                              <div className="flex items-center gap-3">
                                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
                                  <PlatformIcon os={device.os} />
                                </div>
                                <div>
                                  <p className="text-sm font-medium">{device.name}</p>
                                  <p className="text-xs text-muted-foreground">{device.os}</p>
                                </div>
                              </div>
                              <Badge variant="success" className="text-[10px]">
                                {t("licenses.deviceActive")}
                              </Badge>
                            </div>
                            <div className="mt-4 flex items-center justify-between">
                              <p className="text-xs text-muted-foreground">
                                {t("licenses.lastActive").replace("{date}", device.last_seen ? formatDate(device.last_seen) : "—")}
                              </p>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeactivate(device.id)}
                                isLoading={removeDeviceMutation.isPending}
                              >
                                {t("licenses.deactivate")}
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    icon={<Monitor className="h-16 w-16" />}
                    title={t("licenses.noDevicesFound")}
                    description={t("licenses.noDevicesFoundDesc").replace("{license}", selectedLicense?.license_key ?? selectedLicenseId)}
                  />
                )}
              </TabsContent>

              <TabsContent value="history">
                <Card>
                  <CardContent className="p-6">
                    <EmptyState
                      icon={<History className="h-16 w-16" />}
                      title={t("licenses.deviceHistoryComingSoon")}
                      description={t("licenses.deviceHistoryComingSoonDesc")}
                    />
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          )}
        </motion.div>

        {/* Callouts */}
        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <Callout variant="info" title={t("licenses.offlineActivation")} icon={<WifiOff className="h-5 w-5 shrink-0 mt-0.5" />}>
              {t("licenses.offlineActivationDesc")}
            </Callout>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 }}
          >
            <Callout variant="warning" title={t("licenses.floatingLicenses")} icon={<Users className="h-5 w-5 shrink-0 mt-0.5" />}>
              {t("licenses.floatingLicensesDesc")}
            </Callout>
          </motion.div>
        </div>
      </SectionWrapper>
    </>
  )
}
