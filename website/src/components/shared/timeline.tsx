import { motion } from "motion/react"
import { cn } from "@/lib/utils"
import { Check, Dot } from "lucide-react"
import { useReducedMotion } from "@/services/accessibility"

type TimelineStatus = "completed" | "current" | "upcoming"

interface TimelineItem {
  date: string
  title: string
  description?: string
  icon?: React.ReactNode
  status?: TimelineStatus
}

interface TimelineProps {
  items: TimelineItem[]
  className?: string
}

const statusColors: Record<TimelineStatus, { dot: string; line: string; bg: string }> = {
  completed: {
    dot: "border-primary bg-primary text-primary-foreground",
    line: "bg-primary",
    bg: "bg-primary/10",
  },
  current: {
    dot: "border-amber-500 bg-amber-500 text-amber-50",
    line: "bg-amber-500",
    bg: "bg-amber-500/10",
  },
  upcoming: {
    dot: "border-muted-foreground/30 bg-background text-muted-foreground",
    line: "bg-border",
    bg: "bg-muted/30",
  },
}

export function Timeline({ items, className }: TimelineProps) {
  const prefersReducedMotion = useReducedMotion()
  return (
    <div className={cn("relative", className)}>
      {items.map((item, index) => {
        const status = item.status ?? "upcoming"
        const colors = statusColors[status]
        const isLast = index === items.length - 1

        return (
          <motion.div
            key={index}
            initial={prefersReducedMotion ? { opacity: 1, x: 0 } : { opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: prefersReducedMotion ? 0 : Math.min(index * 0.05, 0.3), ease: [0.22, 1, 0.36, 1] }}
            className="relative flex gap-6 pb-8 last:pb-0"
          >
            {/* Vertical line */}
            {!isLast && (
              <div
                className={cn(
                  "absolute left-[11px] top-6 w-0.5",
                  colors.line,
                  status === "upcoming" ? "h-full" : "h-[calc(100%-12px)]"
                )}
              />
            )}

            {/* Dot */}
            <div
              className={cn(
                "relative z-10 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2",
                colors.dot,
                colors.bg
              )}
            >
              {status === "completed" ? (
                <Check className="h-3 w-3" />
              ) : item.icon ? (
                <span className="h-3 w-3">{item.icon}</span>
              ) : (
                <Dot className="h-4 w-4" />
              )}
            </div>

            {/* Content */}
            <div className="flex-1 space-y-1 pt-0.5">
              <span className="text-xs font-medium text-muted-foreground">{item.date}</span>
              <h3 className="text-sm font-semibold">{item.title}</h3>
              {item.description && (
                <p className="text-sm text-muted-foreground">{item.description}</p>
              )}
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}
