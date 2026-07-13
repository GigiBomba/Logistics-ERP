import { motion } from "motion/react"
import { Quote } from "lucide-react"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface TestimonialCardProps {
  quote: string
  name: string
  role: string
  company: string
  index?: number
  className?: string
}

export function TestimonialCard({
  quote,
  name,
  role,
  company,
  index = 0,
  className,
}: TestimonialCardProps) {
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4, delay: index * 0.1, ease: [0.22, 1, 0.36, 1] }}
    >
      <Card className={cn("h-full p-6", className)}>
        <Quote className="mb-4 h-8 w-8 text-muted-foreground/30" />
        <blockquote className="text-sm leading-relaxed text-muted-foreground">
          &ldquo;{quote}&rdquo;
        </blockquote>
        <div className="mt-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
            {initials}
          </div>
          <div>
            <p className="text-sm font-medium">{name}</p>
            <p className="text-xs text-muted-foreground">
              {role}, {company}
            </p>
          </div>
        </div>
      </Card>
    </motion.div>
  )
}
