import { Link } from "react-router"
import { ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface CtaBannerProps {
  title: string
  description?: string
  buttonText: string
  buttonHref: string
  variant?: "primary" | "outline"
  className?: string
}

export function CtaBanner({
  title,
  description,
  buttonText,
  buttonHref,
  variant = "primary",
  className,
}: CtaBannerProps) {
  return (
    <Card
      className={cn(
        "relative overflow-hidden p-8 md:p-12",
        variant === "primary"
          ? "border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-background"
          : "border-accent bg-gradient-to-br from-accent/30 via-accent/10 to-background",
        className
      )}
    >
      <div className="relative z-10 flex flex-col items-start gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="max-w-xl">
          <h3 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h3>
          {description && (
            <p className="mt-2 text-muted-foreground">{description}</p>
          )}
        </div>
        <Button
          variant={variant === "primary" ? "default" : "outline"}
          size="lg"
          asChild
          className="shrink-0"
        >
          <Link to={buttonHref}>
            {buttonText}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </div>
    </Card>
  )
}
