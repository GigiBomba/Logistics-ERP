import { Download, Package } from "lucide-react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn, formatDate } from "@/lib/utils"

interface ReleaseSection {
  title: string
  items: string[]
}

export interface Release {
  version: string
  release_date: string
  sections: ReleaseSection[]
  type: "app" | "toolkit"
  size_mb?: number
  downloads_url?: string
}

interface ReleaseCardProps {
  release: Release
  className?: string
}

export function ReleaseCard({ release, className }: ReleaseCardProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="flex flex-row items-start justify-between gap-4 border-b bg-muted/30 p-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold tracking-tight">v{release.version}</h3>
            <Badge variant={release.type === "app" ? "default" : "secondary"}>
              {release.type === "app" ? "Application" : "Toolkit"}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">{formatDate(release.release_date)}</p>
        </div>
        {release.size_mb !== undefined && (
          <span className="flex items-center gap-1 whitespace-nowrap text-xs text-muted-foreground">
            <Package className="h-3.5 w-3.5" />
            {release.size_mb} MB
          </span>
        )}
      </CardHeader>

      <CardContent className="space-y-4 p-5">
        {release.sections.map((section, i) => (
          <div key={i}>
            <h4 className="mb-2 text-sm font-semibold">{section.title}</h4>
            <ul className="space-y-1">
              {section.items.map((item, j) => (
                <li key={j} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-muted-foreground/40" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}

        {release.downloads_url && (
          <div className="pt-2">
            <Button asChild size="sm">
              <a href={release.downloads_url} download>
                <Download className="h-4 w-4" />
                Download v{release.version}
              </a>
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
