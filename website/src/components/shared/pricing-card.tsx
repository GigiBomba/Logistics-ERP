import { motion } from "motion/react"
import { Check } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { Link } from "react-router"

interface PricingCardProps {
  name: string
  price: string
  yearlyPrice?: string
  description: string
  features: string[]
  highlighted?: boolean
  ctaLabel?: string
  ctaHref?: string
  index?: number
}

export function PricingCard({
  name,
  price,
  yearlyPrice,
  description,
  features,
  highlighted = false,
  ctaLabel = "Start Free Trial",
  ctaHref = "/register",
  index = 0,
}: PricingCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4, delay: index * 0.1, ease: [0.22, 1, 0.36, 1] }}
    >
      <Card
        className={cn(
          "relative h-full transition-shadow hover:shadow-lg",
          highlighted && "border-primary/50 shadow-md ring-1 ring-primary/20"
        )}
      >
        {highlighted && (
          <div className="absolute -top-3 left-1/2 -translate-x-1/2">
            <Badge>Most Popular</Badge>
          </div>
        )}
        <CardHeader className="pb-4">
          <CardTitle className="text-xl">{name}</CardTitle>
          <CardDescription>{description}</CardDescription>
          <div className="mt-4">
            <span className="text-4xl font-bold">{price}</span>
            <span className="text-muted-foreground">/month</span>
          </div>
          {yearlyPrice && (
            <p className="mt-1 text-sm text-muted-foreground">
              {yearlyPrice}/month billed yearly
            </p>
          )}
        </CardHeader>
        <CardContent>
          <ul className="space-y-2.5">
            {features.map((feature) => (
              <li key={feature} className="flex items-start gap-2 text-sm">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                <span>{feature}</span>
              </li>
            ))}
          </ul>
        </CardContent>
        <CardFooter>
          <Button
            variant={highlighted ? "default" : "outline"}
            className="w-full"
            asChild
          >
            <Link to={ctaHref}>{ctaLabel}</Link>
          </Button>
        </CardFooter>
      </Card>
    </motion.div>
  )
}
