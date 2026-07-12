import * as React from "react"
import { motion } from "motion/react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Check } from "lucide-react"
import { Link } from "react-router-dom"

interface PricingCardProps {
  name: string
  price: string
  period?: string
  description: string
  features: string[]
  highlighted?: boolean
  ctaLabel?: string
  ctaHref?: string
  className?: string
  index?: number
}

export function PricingCard({
  name,
  price,
  period = "/month",
  description,
  features,
  highlighted = false,
  ctaLabel = "Get started",
  ctaHref = "/signup",
  className,
  index = 0,
}: PricingCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{
        duration: 0.5,
        delay: index * 0.12,
        ease: [0.22, 1, 0.36, 1],
      }}
    >
      <Card
        className={cn(
          "relative h-full flex flex-col",
          highlighted
            ? "border-primary/40 bg-primary/5 shadow-lg shadow-primary/5"
            : "border-border/60 bg-card/50 backdrop-blur-sm",
          className
        )}
      >
        {highlighted && (
          <div className="absolute -top-3 left-1/2 -translate-x-1/2">
            <Badge variant="default" className="bg-primary text-primary-foreground px-3">
              Most Popular
            </Badge>
          </div>
        )}

        <CardHeader className="pb-4">
          <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
            {name}
          </h3>
          <div className="mt-2 flex items-baseline gap-1">
            <span className="text-4xl font-bold tracking-tight text-foreground">
              {price}
            </span>
            <span className="text-sm text-muted-foreground">{period}</span>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">{description}</p>
        </CardHeader>

        <CardContent className="flex-1 flex flex-col">
          <ul className="space-y-3">
            {features.map((feature, i) => (
              <li key={i} className="flex items-start gap-3">
                <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10">
                  <Check className="h-3 w-3 text-primary" />
                </div>
                <span className="text-sm text-foreground">{feature}</span>
              </li>
            ))}
          </ul>

          <Button
            asChild
            className={cn(
              "mt-8 w-full",
              highlighted
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
            )}
          >
            <Link to={ctaHref}>{ctaLabel}</Link>
          </Button>
        </CardContent>
      </Card>
    </motion.div>
  )
}
