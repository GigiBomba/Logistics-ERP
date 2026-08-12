import { Clock } from "lucide-react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { trackEvent } from "@/services/analytics"

export interface RoadmapFeatureProps {
  /** Title of the feature */
  title: string
  /** What it will do, 1–2 lines */
  description: string
  /** Optional icon (defaults to Clock) */
  icon?: React.ReactNode
  /** Target quarter e.g. "Q4 2026" or "Under evaluation" */
  targetQuarter?: string
  /** Optional "Notify me" callback */
  notifyAction?: () => void
  /** Additional content below the description */
  children?: React.ReactNode
  className?: string
}

export function RoadmapFeature({
  title,
  description,
  icon,
  targetQuarter,
  notifyAction,
  children,
  className,
}: RoadmapFeatureProps) {
  return (
    <Card
      className={cn("h-full", className)}
      role="article"
      aria-label={title}
    >
      <CardHeader className="flex flex-row items-start gap-4">
        <span
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
          aria-hidden="true"
        >
          {icon ?? <Clock className="h-5 w-5" />}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold leading-tight tracking-tight">
              {title}
            </h3>
            {targetQuarter && (
              <Badge variant="secondary" className="shrink-0 text-xs">
                {targetQuarter}
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </CardHeader>

      {(children || notifyAction) && (
        <CardContent className="space-y-3">
          {children}
          {notifyAction && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                trackEvent("feature_interest_clicked", "roadmap", title)
                notifyAction()
              }}
              aria-label={`Notify me about ${title}`}
            >
              Notify me
            </Button>
          )}
        </CardContent>
      )}
    </Card>
  )
}
