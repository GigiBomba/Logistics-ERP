import { useState } from "react"
import { SeoHead } from "@/components/seo/seo-head"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { CheckCircle, AlertTriangle, XCircle, Wrench, Mail, BarChart3, HelpCircle } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { StatusBadge } from "@/components/shared/status-badge"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { cn } from "@/lib/utils"
import { formatDate } from "@/lib/utils"
import { useServiceStatus } from "@/services/queries"

type ServiceStatus = "operational" | "degraded" | "outage" | "maintenance" | "unknown"

interface Service {
  name: string
  description?: string
  status: ServiceStatus
  updatedAt?: string
}

interface ServiceGroup {
  name: string
  description?: string
  services: Service[]
}

const KNOWN_STATUSES: ServiceStatus[] = ["operational", "degraded", "outage", "maintenance"]

// Map whatever the backend reports to a known status; anything unexpected
// becomes "unknown" rather than rendering a broken badge.
function normalizeStatus(value: string | undefined): ServiceStatus {
  return value && KNOWN_STATUSES.includes(value as ServiceStatus) ? (value as ServiceStatus) : "unknown"
}

function getOverallStatus(groups: ServiceGroup[]): {
  status: ServiceStatus
  labelKey: string
  descKey: string
  icon: React.ReactNode
  bannerClass: string
} {
  const allServices = groups.flatMap((g) => g.services)

  // No live data at all → honest "unknown" state, never a green pulse.
  if (allServices.length === 0 || allServices.every((s) => s.status === "unknown")) {
    return {
      status: "unknown",
      labelKey: "status.unavailable",
      descKey: "status.unavailableDesc",
      icon: <HelpCircle className="h-6 w-6" />,
      bannerClass: "border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-950/40",
    }
  }

  // All services in active development (maintenance) → in-development banner.
  if (allServices.every((s) => s.status === "maintenance")) {
    return {
      status: "maintenance",
      labelKey: "status.inDevelopment",
      descKey: "status.inDevelopmentDesc",
      icon: <Wrench className="h-6 w-6" />,
      bannerClass: "border-blue-200 bg-blue-50 dark:border-blue-900/50 dark:bg-blue-950/30",
    }
  }

  if (allServices.some((s) => s.status === "outage")) {
    return {
      status: "outage",
      labelKey: "status.disruption",
      descKey: "status.disruptionDesc",
      icon: <XCircle className="h-6 w-6" />,
      bannerClass: "border-red-200 bg-red-50 dark:border-red-900/50 dark:bg-red-950/30",
    }
  }

  if (allServices.some((s) => s.status === "degraded")) {
    return {
      status: "degraded",
      labelKey: "status.degraded",
      descKey: "status.degradedDesc",
      icon: <AlertTriangle className="h-6 w-6" />,
      bannerClass: "border-yellow-200 bg-yellow-50 dark:border-yellow-900/50 dark:bg-yellow-950/30",
    }
  }

  if (allServices.some((s) => s.status === "maintenance")) {
    return {
      status: "maintenance",
      labelKey: "status.scheduledMaintenance",
      descKey: "status.scheduledDesc",
      icon: <Wrench className="h-6 w-6" />,
      bannerClass: "border-blue-200 bg-blue-50 dark:border-blue-900/50 dark:bg-blue-950/30",
    }
  }

  // Only reachable when every service is explicitly "operational".
  return {
    status: "operational",
    labelKey: "status.operational",
    descKey: "status.operationalDesc",
    icon: <CheckCircle className="h-6 w-6" />,
    bannerClass: "border-green-200 bg-green-50 dark:border-green-900/50 dark:bg-green-950/30",
  }
}

const statusColorMap: Record<ServiceStatus, string> = {
  operational: "text-green-600 dark:text-green-400",
  degraded: "text-yellow-600 dark:text-yellow-400",
  outage: "text-red-600 dark:text-red-400",
  maintenance: "text-blue-600 dark:text-blue-400",
  unknown: "text-gray-500 dark:text-gray-400",
}

const lastPageUpdated = new Date().toISOString()

export default function StatusPage() {
  const { t } = useLocale()
  const [subEmail, setSubEmail] = useState("")

  const { data, isLoading, isError, refetch } = useServiceStatus()

  const serviceGroups: ServiceGroup[] =
    data && data.length > 0
      ? data.map((group) => ({
          name: group.name,
          services: group.services.map((service) => ({
            name: service.name,
            description: service.description,
            status: normalizeStatus(service.status),
            updatedAt: service.updated_at,
          })),
        }))
      : [
          {
            name: t("status.components"),
            services: [
              {
                name: t("status.desktopApp"),
                description: t("status.desktopAppDesc"),
                status: "unknown",
              },
              {
                name: t("status.webPortal"),
                description: t("status.webPortalDesc"),
                status: "unknown",
              },
              {
                name: t("status.apiBackend"),
                description: t("status.apiBackendDesc"),
                status: "unknown",
              },
            ],
          },
        ]

  const overall = getOverallStatus(isError || !data ? [] : serviceGroups)

  const badgeLabel = (status: ServiceStatus) => {
    if (status === "unknown") return t("status.unknownShort")
    if (status === "maintenance") return t("status.inDevelopmentShort")
    return undefined
  }

  return (
    <>
      <SeoHead title={t("status.pageTitle")} description={t("status.metaDesc")} canonical="https://operionerp.xyz/status" />

      <PageHeader
        title={t("status.title")}
        description={t("status.pageDesc")}
      />

      {/* Overall Status Banner */}
      <SectionWrapper className="py-0 md:py-0">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl"
        >
          {isLoading ? (
            <div className="flex items-center justify-center rounded-xl border p-10">
              <LoadingSpinner />
            </div>
          ) : (
            <div
              className={cn(
                "flex items-start gap-4 rounded-xl border p-5",
                overall.bannerClass
              )}
            >
              <div className={cn("mt-0.5", statusColorMap[overall.status])}>
                {overall.icon}
              </div>
              <div className="flex-1">
                <h2 className="text-base font-semibold">{t(overall.labelKey)}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{t(overall.descKey)}</p>
                {isError && (
                  <Button variant="outline" size="sm" className="mt-3" onClick={() => refetch()}>
                    {t("common.tryAgain")}
                  </Button>
                )}
              </div>
            </div>
          )}
        </motion.div>
      </SectionWrapper>

      {/* Service Groups */}
      <SectionWrapper>
        <div className="mx-auto max-w-3xl space-y-12">
          {serviceGroups.map((group, groupIndex) => (
            <motion.div
              key={`${group.name}-${groupIndex}`}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: groupIndex * 0.1, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="mb-4">
                <h3 className="text-lg font-bold">{group.name}</h3>
                {group.description && (
                  <p className="text-sm text-muted-foreground">{group.description}</p>
                )}
              </div>
              <div className="space-y-3">
                {group.services.map((service) => (
                  <Card key={`${group.name}-${service.name}`}>
                    <CardContent className="flex items-center justify-between p-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{service.name}</span>
                          <StatusBadge status={service.status} label={badgeLabel(service.status)} />
                        </div>
                        {service.description && (
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            {service.description}
                          </p>
                        )}
                      </div>
                      {service.updatedAt && (
                        <span className="shrink-0 text-[11px] text-muted-foreground">
                          {t("status.updated")} {formatDate(service.updatedAt)}
                        </span>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </SectionWrapper>

      {/* Past Incidents */}
      <SectionWrapper className="bg-muted/30">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-xl font-bold tracking-tight mb-6">{t("status.pastIncidents")}</h2>
            <Card className="border-dashed">
              <CardContent className="p-8 text-center">
                <p className="text-muted-foreground">
                  {t("status.noIncidents")}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>

      {/* Scheduled Maintenance */}
      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-xl font-bold tracking-tight mb-6">{t("status.scheduledMaintenance")}</h2>
            <Card className="border-dashed">
              <CardContent className="p-8 text-center">
                <p className="text-muted-foreground">
                  {t("status.noMaintenance")}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>

      {/* Uptime History */}
      <SectionWrapper className="bg-muted/30">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-xl font-bold tracking-tight mb-6">{t("status.uptimeHistory")}</h2>
            <Card className="border-dashed">
              <CardContent className="p-8 text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 mx-auto mb-4">
                  <BarChart3 className="h-7 w-7 text-primary" />
                </div>
                <p className="text-sm text-muted-foreground">{t("status.uptimeComing")}</p>
                <p className="mt-1 text-xs text-muted-foreground">{t("status.uptimeDesc")}</p>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>

      {/* Subscribe to Updates */}
      <SectionWrapper>
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <Card className="border-primary/20 bg-primary/5">
              <CardContent className="p-6">
                <div className="flex items-center gap-2 mb-2">
                  <Mail className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold">{t("status.subscribe")}</h3>
                </div>
                <p className="text-sm text-muted-foreground mb-4">
                  {t("status.subscribeDesc")}
                </p>
                <div className="flex flex-col sm:flex-row gap-2">
                  <Input
                    type="email"
                    placeholder={t("common.search")}
                    value={subEmail}
                    onChange={(e) => setSubEmail(e.target.value)}
                    className="flex-1"
                  />
                  <Button
                    onClick={() => {
                      alert(t("status.subscribeAlert"))
                      setSubEmail("")
                    }}
                  >
                    {t("common.submit")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </SectionWrapper>

      {/* Last Updated Footer */}
      <SectionWrapper className="py-8 md:py-8">
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center"
        >
          <p className="text-xs text-muted-foreground">
            {t("status.lastUpdated")}: {formatDate(lastPageUpdated)} at{" "}
            {new Date(lastPageUpdated).toLocaleTimeString("en-US", {
              hour: "2-digit",
              minute: "2-digit",
              timeZoneName: "short",
            })}
          </p>
        </motion.div>
      </SectionWrapper>
    </>
  )
}
