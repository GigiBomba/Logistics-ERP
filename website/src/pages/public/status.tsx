import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import { useLocale } from "@/i18n/locale-context"
import { CheckCircle, AlertTriangle, XCircle, Wrench, Mail, BarChart3 } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { StatusBadge } from "@/components/shared/status-badge"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { formatDate } from "@/lib/utils"

type ServiceStatus = "operational" | "degraded" | "outage" | "maintenance"

interface Service {
  nameKey: string
  descKey: string
  status: ServiceStatus
  updatedAt: string
}

interface ServiceGroup {
  titleKey: string
  descKey: string
  services: Service[]
}

const serviceGroups: ServiceGroup[] = [
  {
    titleKey: "status.components",
    descKey: "status.componentsDesc",
    services: [
      {
        nameKey: "status.desktopApp",
        descKey: "status.desktopAppDesc",
        status: "maintenance",
        updatedAt: new Date().toISOString(),
      },
      {
        nameKey: "status.webPortal",
        descKey: "status.webPortalDesc",
        status: "maintenance",
        updatedAt: new Date().toISOString(),
      },
      {
        nameKey: "status.apiBackend",
        descKey: "status.apiBackendDesc",
        status: "maintenance",
        updatedAt: new Date().toISOString(),
      },
    ],
  },
]

function getOverallStatus(groups: ServiceGroup[]): {
  status: ServiceStatus
  labelKey: string
  descKey: string
  icon: React.ReactNode
  bannerClass: string
} {
  const allServices = groups.flatMap((g) => g.services)

  const allInDevelopment = allServices.length > 0 && allServices.every((s) => s.status === "maintenance")

  if (allInDevelopment) {
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
}

const lastPageUpdated = new Date().toISOString()

export default function StatusPage() {
  const { t } = useLocale()
  const overall = getOverallStatus(serviceGroups)
  const [subEmail, setSubEmail] = useState("")

  return (
    <>
      <Helmet>
        <title>{t("status.pageTitle")}</title>
        <meta name="description" content={t("status.metaDesc")} />
      </Helmet>

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
          <div
            className={cn(
              "flex items-start gap-4 rounded-xl border p-5",
              overall.bannerClass
            )}
          >
            <div className={cn("mt-0.5", statusColorMap[overall.status])}>
              {overall.icon}
            </div>
            <div>
              <h2 className="text-base font-semibold">{t(overall.labelKey)}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{t(overall.descKey)}</p>
            </div>
          </div>
        </motion.div>
      </SectionWrapper>

      {/* Service Groups */}
      <SectionWrapper>
        <div className="mx-auto max-w-3xl space-y-12">
          {serviceGroups.map((group, groupIndex) => (
            <motion.div
              key={group.titleKey}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: groupIndex * 0.1, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="mb-4">
                <h3 className="text-lg font-bold">{t(group.titleKey)}</h3>
                <p className="text-sm text-muted-foreground">{t(group.descKey)}</p>
              </div>
              <div className="space-y-3">
                {group.services.map((service) => (
                  <Card key={service.nameKey}>
                    <CardContent className="flex items-center justify-between p-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{t(service.nameKey)}</span>
                          <StatusBadge status={service.status} label={service.status === "maintenance" ? t("status.inDevelopmentShort") : undefined} />
                        </div>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {t(service.descKey)}
                        </p>
                      </div>
                      <span className="shrink-0 text-[11px] text-muted-foreground">
                        {t("status.updated")} {formatDate(service.updatedAt)}
                      </span>
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
