import { Link, useLocation } from "react-router"
import { cn } from "@/lib/utils"
import { useLocale } from "@/i18n/locale-context"
import { trackCTAClick } from "@/services/analytics"

interface WaitlistCtaProps {
  /** Source label tracked in analytics and forwarded to the waitlist form (e.g. "route_calculator", "blog:<slug>"). */
  source: string
  className?: string
}

/**
 * Contextual waitlist CTA (Waitlist blueprint §5.3).
 *
 * Renders the site's standard waitlist button style linking to
 * `/waitlist?source=<source>` and fires the shared CTA-click tracking helper
 * so analytics stay consistent with the rest of the site.
 */
export function WaitlistCta({ source, className }: WaitlistCtaProps) {
  const { t } = useLocale()
  const location = useLocation()

  return (
    <Link
      to={`/waitlist?source=${source}`}
      onClick={() => trackCTAClick(source, location.pathname)}
      className={cn(
        "inline-flex items-center rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors",
        className
      )}
    >
      {t("waitlist.joinButton")}
    </Link>
  )
}