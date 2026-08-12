import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { motion } from "motion/react"
import {
  Smartphone,
  Monitor,
  Tablet,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Callout } from "@/components/ui/callout"
import { SectionWrapper } from "@/components/shared/section-wrapper"
import { StatCard } from "@/components/shared/stat-card"
import { EmptyState } from "@/components/shared/empty-state"
import { DeviceList, formatDate, formatRelativeTime, getPlatformIcon, getPlatformLabel } from "@/components/shared/device-list"
import { useDevices, useDeactivateDevice, useSessions, useRevokeSession } from "@/services/queries"
import { useLocale } from "@/i18n/locale-context"
import type { DeviceInfo } from "@/types"
import type { SessionInfo } from "@/api/endpoints"

function SessionCard({ session, onRevoke }: { session: SessionInfo; onRevoke: (id: number) => void }) {
  const [confirming, setConfirming] = useState(false)
  const { t } = useLocale()

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
    >
      <Card className="overflow-hidden">
        <CardContent className="p-5">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
                {getPlatformIcon(session.device_platform)}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">
                  {session.device_name || t("devices.unknownDevice")}
                </p>
                <p className="text-xs text-muted-foreground">{getPlatformLabel(session.device_platform)}</p>
              </div>
            </div>
          </div>

          <div className="mt-4 space-y-2 border-t pt-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t("devices.user")}</span>
              <span className="font-medium truncate ml-2 max-w-[200px]" title={session.user_email}>
                {session.user_email}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t("devices.ipAddress")}</span>
              <span className="font-medium font-mono text-xs">{session.ip_address}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t("devices.lastActive")}</span>
              <span className="font-medium">{formatRelativeTime(session.last_active_at, t)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t("devices.created")}</span>
              <span className="font-medium">{formatDate(session.created_at)}</span>
            </div>
          </div>

          <div className="mt-4 border-t pt-4">
            {confirming ? (
              <div className="flex items-center gap-2">
                <p className="text-xs text-muted-foreground flex-1">
                  {t("devices.areYouSure")}
                </p>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    onRevoke(session.id)
                    setConfirming(false)
                  }}
                >
                  {t("devices.revoke")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConfirming(false)}
                >
                  {t("common.cancel")}
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                className="w-full text-destructive hover:text-destructive border-destructive/30 hover:border-destructive"
                onClick={() => setConfirming(true)}
              >
                <XCircle className="mr-1.5 h-3.5 w-3.5" />
                {t("devices.revoke")}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

function DesktopSessionsSection() {
  const { data: sessions = [], isLoading, isError, error } = useSessions()
  const revokeSession = useRevokeSession()
  const { t } = useLocale()

  function handleRevoke(sessionId: number) {
    revokeSession.mutate(sessionId)
  }

  if (isLoading) {
    return (
      <motion.div
        className="mt-10"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
      >
        <h2 className="text-xl font-bold tracking-tight mb-4">{t("devices.desktopSessions")}</h2>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </motion.div>
    )
  }

  if (isError) {
    return (
      <motion.div
        className="mt-10"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
      >
        <h2 className="text-xl font-bold tracking-tight mb-4">{t("devices.desktopSessions")}</h2>
        <Callout variant="danger" title={t("devices.failedLoadSessions")}>
          {error instanceof Error ? error.message : t("devices.unexpectedError")}
        </Callout>
      </motion.div>
    )
  }

  return (
    <motion.div
      className="mt-10"
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: 0.3 }}
    >
      <h2 className="text-xl font-bold tracking-tight mb-1">{t("devices.desktopSessions")}</h2>
      <p className="text-sm text-muted-foreground mb-6">
        {t("devices.desktopSessionsDesc")}
      </p>

      {sessions.length === 0 ? (
        <Card>
          <CardContent className="p-6">
            <EmptyState
              icon={<Monitor className="h-16 w-16" />}
              title={t("devices.noDesktopSessions")}
              description={t("devices.noDesktopSessionsDesc")}
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sessions.map((session) => (
            <SessionCard
              key={session.id}
              session={session}
              onRevoke={handleRevoke}
            />
          ))}
        </div>
      )}
    </motion.div>
  )
}

/**
 * Two-step deactivate control rendered via the shared DeviceList `renderActions`
 * slot. Preserves the previous inline confirm-before-deactivate behaviour and
 * only appears for active devices.
 */
function DeactivateButton({
  device,
  onDeactivate,
  isLoading,
}: {
  device: DeviceInfo
  onDeactivate: (deviceId: string) => void
  isLoading: boolean
}) {
  const [confirming, setConfirming] = useState(false)
  const { t } = useLocale()

  if (!device.is_active) return null

  if (!confirming) {
    return (
      <Button
        variant="outline"
        size="sm"
        className="w-full text-destructive hover:text-destructive border-destructive/30 hover:border-destructive"
        onClick={() => setConfirming(true)}
      >
        <XCircle className="mr-1.5 h-3.5 w-3.5" />
        {t("devices.deactivate")}
      </Button>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <p className="text-xs text-muted-foreground flex-1">
        {t("devices.areYouSure")}
      </p>
      <Button
        variant="destructive"
        size="sm"
        isLoading={isLoading}
        onClick={() => {
          onDeactivate(device.device_id)
          setConfirming(false)
        }}
      >
        {t("devices.deactivate")}
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setConfirming(false)}
      >
        {t("common.cancel")}
      </Button>
    </div>
  )
}

export default function DevicesPage() {
  const { data: devicesData, isLoading, isError, error } = useDevices()
  const deactivateDevice = useDeactivateDevice()
  const [activeTab, setActiveTab] = useState("all")
  const { t } = useLocale()

  const devices = devicesData ?? []

  const activeDevices = devices.filter((d) => d.is_active)
  const inactiveDevices = devices.filter((d) => !d.is_active)

  // Platform breakdown
  const platformCounts = devices.reduce<Record<string, number>>((acc, d) => {
    const label = getPlatformLabel(d.platform)
    acc[label] = (acc[label] || 0) + 1
    return acc
  }, {})

  const sortedPlatforms = Object.entries(platformCounts).sort(([, a], [, b]) => b - a)

  const displayedDevices =
    activeTab === "all" ? devices : activeTab === "active" ? activeDevices : inactiveDevices

  function handleDeactivate(deviceId: string) {
    deactivateDevice.mutate(deviceId)
  }

  if (isLoading) {
    return (
      <SectionWrapper>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </SectionWrapper>
    )
  }

  if (isError) {
    return (
      <SectionWrapper>
        <div className="flex items-center justify-center py-20">
          <Callout variant="danger" title={t("devices.failedLoadDevices")}>
            {error instanceof Error ? error.message : t("devices.unexpectedError")}
          </Callout>
        </div>
      </SectionWrapper>
    )
  }

  return (
    <>
      <Helmet>
        <title>{t("devices.pageTitle")}</title>
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
              <h1 className="text-3xl font-bold tracking-tight">{t("devices.title")}</h1>
              <p className="mt-2 text-muted-foreground">
                {t("devices.description")}
              </p>
            </div>
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
            <StatCard value={String(devices.length)} label={t("devices.totalDevices")} icon={Smartphone} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <StatCard value={String(activeDevices.length)} label={t("devices.activeDevices")} icon={CheckCircle2} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.15 }}
          >
            <StatCard value={String(inactiveDevices.length)} label={t("devices.inactiveDevices")} icon={XCircle} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
          >
            <StatCard value={String(sortedPlatforms.length)} label={t("devices.platforms")} icon={Monitor} />
          </motion.div>
        </div>

        {/* Platform breakdown */}
        {sortedPlatforms.length > 0 && (
          <motion.div
            className="mt-6"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
          >
            <Card>
              <CardContent className="p-5">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-sm font-medium text-muted-foreground">{t("devices.platforms")}:</span>
                  {sortedPlatforms.map(([platform, count]) => (
                    <Badge key={platform} variant="secondary" className="gap-1.5">
                      {platform}
                      <span className="inline-flex items-center justify-center rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary">
                        {count}
                      </span>
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Devices List */}
        <motion.div
          className="mt-10"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
        >
          <h2 className="text-xl font-bold tracking-tight mb-4">{t("devices.registeredDevices")}</h2>

          {devices.length === 0 ? (
            <Card>
              <CardContent className="p-6">
                <EmptyState
                  icon={<Tablet className="h-16 w-16" />}
                  title={t("devices.noDevicesRegistered")}
                  description={t("devices.noDevicesRegisteredDesc")}
                />
              </CardContent>
            </Card>
          ) : (
            <>
              <Tabs value={activeTab} defaultValue="all" onValueChange={setActiveTab}>
                <TabsList className="mb-4">
                  <TabsTrigger value="all">
                    {t("devices.allDevices")}
                    <span className="ml-1.5 inline-flex items-center justify-center rounded-full bg-muted-foreground/20 px-1.5 py-0.5 text-[10px] font-medium">
                      {devices.length}
                    </span>
                  </TabsTrigger>
                  <TabsTrigger value="active">
                    {t("devices.activeTab")}
                    <span className="ml-1.5 inline-flex items-center justify-center rounded-full bg-green-500/20 px-1.5 py-0.5 text-[10px] font-medium text-green-600 dark:text-green-400">
                      {activeDevices.length}
                    </span>
                  </TabsTrigger>
                  <TabsTrigger value="inactive">
                    {t("devices.inactiveTab")}
                    <span className="ml-1.5 inline-flex items-center justify-center rounded-full bg-muted-foreground/20 px-1.5 py-0.5 text-[10px] font-medium">
                      {inactiveDevices.length}
                    </span>
                  </TabsTrigger>
                </TabsList>

                <TabsContent value={activeTab} className="space-y-4">
                  <DeviceList
                    devices={displayedDevices}
                    variant="card"
                    onDeactivate={handleDeactivate}
                    renderActions={(device) => (
                      <DeactivateButton
                        device={device}
                        onDeactivate={handleDeactivate}
                        isLoading={deactivateDevice.isPending}
                      />
                    )}
                    emptyMessage={
                      activeTab === "active"
                        ? t("devices.noActiveDevices")
                        : activeTab === "inactive"
                          ? t("devices.noInactiveDevices")
                          : t("devices.noDevicesMatchFilter")
                    }
                  />
                </TabsContent>
              </Tabs>
            </>
          )}
        </motion.div>

        {/* Info callout */}
        <motion.div
          className="mt-10"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 }}
        >
          <Callout variant="info" title={t("devices.aboutDeviceManagement")} icon={<Smartphone className="h-5 w-5 shrink-0 mt-0.5" />}>
            {t("devices.aboutDeviceManagementDesc")}
          </Callout>
        </motion.div>

        {/* Desktop App Sessions */}
        <DesktopSessionsSection />
      </SectionWrapper>
    </>
  )
}
