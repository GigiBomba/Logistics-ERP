import { type ReactNode } from "react"
import { motion } from "motion/react"
import { Smartphone, Monitor, Server, Tablet } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useLocale } from "@/i18n/locale-context"
import type { DeviceInfo } from "@/types"

// ─── Helpers ────────────────────────────────────────────────

export function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function formatRelativeTime(dateString: string, t?: (key: string) => string) {
  const now = Date.now()
  const then = new Date(dateString).getTime()
  const diffMs = now - then
  const diffMinutes = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  const tr = (key: string, fallback: string) => (t ? t(key) : fallback)

  if (diffMinutes < 1) return tr("devices.justNow", "Just now")
  if (diffMinutes < 60) return tr("devices.minutesAgo", `${diffMinutes}m ago`).replace("{minutes}", String(diffMinutes))
  if (diffHours < 24) return tr("devices.hoursAgo", `${diffHours}h ago`).replace("{hours}", String(diffHours))
  if (diffDays < 7) return tr("devices.daysAgo", `${diffDays}d ago`).replace("{days}", String(diffDays))
  return formatDate(dateString)
}

export function getPlatformIcon(platform: string) {
  const p = platform.toLowerCase()
  if (p.includes("android")) return <Smartphone className="h-4 w-4" />
  if (p.includes("ios") || p.includes("iphone") || p.includes("ipad")) return <Tablet className="h-4 w-4" />
  if (p.includes("linux") || p.includes("server")) return <Server className="h-4 w-4" />
  if (p.includes("windows") || p.includes("macos") || p.includes("mac")) return <Monitor className="h-4 w-4" />
  return <Smartphone className="h-4 w-4" />
}

export function getPlatformLabel(platform: string) {
  const p = platform.toLowerCase()
  if (p.includes("android")) return "Android"
  if (p.includes("ios")) return "iOS"
  if (p.includes("iphone")) return "iOS"
  if (p.includes("ipad")) return "iPadOS"
  if (p.includes("windows")) return "Windows"
  if (p.includes("macos") || p.includes("mac")) return "macOS"
  if (p.includes("linux")) return "Linux"
  return platform
}

// ─── Props ───────────────────────────────────────────────────

export interface DeviceListProps {
  devices: DeviceInfo[]
  onDeactivate?: (deviceId: string) => void
  renderActions?: (device: DeviceInfo) => ReactNode
  variant?: "card" | "table"
  isLoading?: boolean
  emptyMessage?: string
}

// ─── Card Variant ────────────────────────────────────────────

function DeviceCard({
  device,
  onDeactivate,
  renderActions,
}: {
  device: DeviceInfo
  onDeactivate?: (deviceId: string) => void
  renderActions?: (device: DeviceInfo) => ReactNode
}) {
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
                {getPlatformIcon(device.platform)}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{device.device_name}</p>
                <p className="text-xs text-muted-foreground">{getPlatformLabel(device.platform)}</p>
              </div>
            </div>
            <Badge variant={device.is_active ? "success" : "secondary"}>
              {device.is_active ? t("devices.activeTab") : t("devices.inactiveTab")}
            </Badge>
          </div>

          <div className="mt-4 space-y-2 border-t pt-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t("devices.user")}</span>
              <span className="font-medium truncate ml-2 max-w-[200px]" title={`${device.user_name} (${device.user_email})`}>
                {device.user_name}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t("devices.lastSeen")}</span>
              <span className="font-medium">{formatRelativeTime(device.last_seen, t)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t("devices.registered")}</span>
              <span className="font-medium">{formatDate(device.created_at)}</span>
            </div>
          </div>

          {/* Actions slot */}
          {renderActions ? (
            <div className="mt-4 border-t pt-4">
              {renderActions(device)}
            </div>
          ) : onDeactivate && device.is_active ? (
            <div className="mt-4 border-t pt-4">
              <button
                type="button"
                onClick={() => onDeactivate(device.device_id)}
                className="text-sm text-destructive hover:text-destructive/80 transition-colors"
              >
                {t("devices.deactivate")}
              </button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </motion.div>
  )
}

// ─── Table Variant ───────────────────────────────────────────

function DeviceTableRow({
  device,
  onDeactivate,
  renderActions,
}: {
  device: DeviceInfo
  onDeactivate?: (deviceId: string) => void
  renderActions?: (device: DeviceInfo) => ReactNode
}) {
  const { t } = useLocale()
  return (
    <tr className="border-b border-border transition-colors hover:bg-muted/50">
      <td className="py-3 pl-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
            {getPlatformIcon(device.platform)}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium truncate max-w-[200px]">{device.device_name}</p>
            <p className="text-xs text-muted-foreground">{getPlatformLabel(device.platform)}</p>
          </div>
        </div>
      </td>
      <td className="py-3 text-sm text-muted-foreground">
        {device.user_name}
      </td>
      <td className="py-3 text-sm text-muted-foreground">
        <span title={formatDate(device.last_seen)}>{formatRelativeTime(device.last_seen, t)}</span>
      </td>
      <td className="py-3">
        <Badge variant={device.is_active ? "success" : "secondary"}>
          {device.is_active ? t("devices.activeTab") : t("devices.inactiveTab")}
        </Badge>
      </td>
      <td className="py-3 pr-4 text-right">
        {renderActions ? (
          renderActions(device)
        ) : onDeactivate && device.is_active ? (
          <button
            type="button"
            onClick={() => onDeactivate(device.device_id)}
            className="text-sm text-destructive hover:text-destructive/80 transition-colors"
          >
            {t("devices.deactivate")}
          </button>
        ) : null}
      </td>
    </tr>
  )
}

// ─── Main Component ─────────────────────────────────────────

export function DeviceList({
  devices,
  onDeactivate,
  renderActions,
  variant = "card",
  isLoading,
  emptyMessage,
}: DeviceListProps) {
  const { t } = useLocale()
  const resolvedEmptyMessage = emptyMessage ?? t("devices.noDevicesFound")
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (devices.length === 0) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <p className="text-sm text-muted-foreground">{resolvedEmptyMessage}</p>
        </CardContent>
      </Card>
    )
  }

  if (variant === "table") {
    return (
      <div className="overflow-x-auto rounded-xl border">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-muted/50 text-left text-xs font-medium uppercase text-muted-foreground">
              <th className="py-3 pl-4">{t("devices.device")}</th>
              <th className="py-3">{t("devices.user")}</th>
              <th className="py-3">{t("devices.lastSeenTitle")}</th>
              <th className="py-3">{t("devices.status")}</th>
              <th className="py-3 pr-4 text-right">{t("devices.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((device) => (
              <DeviceTableRow
                key={device.id}
                device={device}
                onDeactivate={onDeactivate}
                renderActions={renderActions}
              />
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {devices.map((device) => (
        <DeviceCard
          key={device.id}
          device={device}
          onDeactivate={onDeactivate}
          renderActions={renderActions}
        />
      ))}
    </div>
  )
}
