import { Link } from "react-router"
import { Button } from "@/components/ui/button"
import { ArrowRight } from "lucide-react"
import { useLocale } from "@/i18n/locale-context"

interface CtaSectionProps {
  title: string
  description?: string
  primaryLabel?: string
  primaryHref?: string
  secondaryLabel?: string
  secondaryHref?: string
}

export function CtaSection({
  title,
  description,
  primaryLabel,
  primaryHref = "/register",
  secondaryLabel,
  secondaryHref,
}: CtaSectionProps) {
  const { t } = useLocale()
  const resolvedPrimaryLabel = primaryLabel ?? t("common.getStarted")
  return (
    <section className="py-16 md:py-24">
      <div className="container-wide">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{title}</h2>
          {description && (
            <p className="mt-4 text-lg text-muted-foreground">{description}</p>
          )}
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button size="xl" asChild>
              <Link to={primaryHref}>
                {resolvedPrimaryLabel}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            {secondaryLabel && secondaryHref && (
              <Button variant="outline" size="xl" asChild>
                <Link to={secondaryHref}>{secondaryLabel}</Link>
              </Button>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
