import { useLocale } from "@/i18n/locale-context"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"
import { MapPin, Battery, Wifi, Gauge, Clock } from "lucide-react"
export interface DeviceHealthCardProps {
  deviceName: string
  isOnline?: boolean
  batteryLevel?: number
  signalStrength?: number
  lastSeen?: string
  latitude?: number
  longitude?: number
  speed?: number
}

function formatRelativeTime(dateString: string, t: (key: string) => string): string {
  const now = Date.now()
  const then = new Date(dateString).getTime()
  const diffMs = now - then
  const diffMinutes = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMinutes < 1) return t("deviceHealth.justNow")
  if (diffMinutes < 60) return t("deviceHealth.minutesAgo").replace("{minutes}", String(diffMinutes))
  if (diffHours < 24) return t("deviceHealth.hoursAgo").replace("{hours}", String(diffHours))
  if (diffDays < 7) return t("deviceHealth.daysAgo").replace("{days}", String(diffDays))
  return new Date(dateString).toLocaleDateString()
}

function getBatteryVariant(level: number): "success" | "warning" | "default" {
  if (level >= 50) return "success"
  if (level >= 20) return "warning"
  return "default"
}

function getSignalLabel(strength: number, t: (key: string) => string): string {
  if (strength >= 80) return t("deviceHealth.signalExcellent")
  if (strength >= 60) return t("deviceHealth.signalGood")
  if (strength >= 40) return t("deviceHealth.signalFair")
  if (strength >= 20) return t("deviceHealth.signalWeak")
  return t("deviceHealth.signalVeryWeak")
}

export function DeviceHealthCard({
  deviceName,
  isOnline,
  batteryLevel,
  signalStrength,
  lastSeen,
  latitude,
  longitude,
  speed,
}: DeviceHealthCardProps) {
  const { t } = useLocale()

  const hasLocation = latitude != null && longitude != null
  const mapsUrl = hasLocation
    ? `https://www.google.com/maps?q=${latitude},${longitude}`
    : undefined

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between gap-4 pb-3">
        <CardTitle className="text-base font-semibold truncate">{deviceName}</CardTitle>
        <Badge variant={isOnline ? "success" : "secondary"}>
          {isOnline ? t("deviceHealth.online") : t("deviceHealth.offline")}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* GPS Coordinates */}
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <MapPin className="h-4 w-4" />
            {t("deviceHealth.coordinates")}
          </span>
          <span className="font-mono text-xs">
            {hasLocation
              ? `${latitude!.toFixed(4)}, ${longitude!.toFixed(4)}`
              : t("deviceHealth.noData")}
          </span>
        </div>

        {/* Battery Level */}
        {batteryLevel != null && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <Battery className="h-4 w-4" />
                {t("deviceHealth.battery")}
              </span>
              <span className="font-medium">{batteryLevel}%</span>
            </div>
            <Progress value={batteryLevel} variant={getBatteryVariant(batteryLevel)} />
          </div>
        )}

        {/* Signal Strength */}
        {signalStrength != null && (
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Wifi className="h-4 w-4" />
              {t("deviceHealth.signal")}
            </span>
            <span className="font-medium">{getSignalLabel(signalStrength, t)}</span>
          </div>
        )}

        {/* Speed */}
        {speed != null && (
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Gauge className="h-4 w-4" />
              {t("deviceHealth.speed")}
            </span>
            <span className="font-medium">{speed.toFixed(1)} km/h</span>
          </div>
        )}

        {/* Last Seen */}
        {lastSeen && (
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Clock className="h-4 w-4" />
              {t("deviceHealth.lastSeen")}
            </span>
            <span className="font-medium">{formatRelativeTime(lastSeen, t)}</span>
          </div>
        )}

        {/* Locate on Map Button */}
        <Button
          variant="outline"
          size="sm"
          className="w-full gap-2"
          disabled={!mapsUrl}
          onClick={() => {
            if (mapsUrl) window.open(mapsUrl, "_blank", "noopener,noreferrer")
          }}
        >
          <MapPin className="h-4 w-4" />
          {t("deviceHealth.locateOnMap")}
        </Button>
      </CardContent>
    </Card>
  )
}
