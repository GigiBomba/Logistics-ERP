import type { LucideIcon } from "lucide-react"
import { motion } from "motion/react"
import { Card, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { useReducedMotion } from "@/services/accessibility"

interface FeatureCardProps {
  icon: LucideIcon
  title: string
  description: string
  className?: string
  index?: number
}

export function FeatureCard({ icon: Icon, title, description, className, index = 0 }: FeatureCardProps) {
  const prefersReducedMotion = useReducedMotion()
  return (
    <motion.div
      initial={prefersReducedMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4, delay: prefersReducedMotion ? 0 : Math.min(index * 0.05, 0.3), ease: [0.22, 1, 0.36, 1] }}
    >
      <Card className={cn("group h-full transition-shadow hover:shadow-md", className)}>
        <CardHeader>
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
            <Icon className="h-5 w-5" />
          </div>
          <CardTitle className="text-lg">{title}</CardTitle>
          <p className="text-sm leading-relaxed text-foreground/80">{description}</p>
        </CardHeader>
      </Card>
    </motion.div>
  )
}
