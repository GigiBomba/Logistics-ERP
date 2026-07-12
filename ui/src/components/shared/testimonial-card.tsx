import * as React from "react"
import { motion } from "motion/react"
import { cn } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"
import { Quote } from "lucide-react"

interface TestimonialCardProps {
  quote: string
  author: string
  role: string
  company: string
  avatarUrl?: string
  className?: string
  index?: number
}

export function TestimonialCard({
  quote,
  author,
  role,
  company,
  avatarUrl,
  className,
  index = 0,
}: TestimonialCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{
        duration: 0.5,
        delay: index * 0.1,
        ease: [0.22, 1, 0.36, 1],
      }}
    >
      <Card
        className={cn(
          "h-full border-border/60 bg-card/50 backdrop-blur-sm",
          "hover:border-primary/20",
          className
        )}
      >
        <CardContent className="p-6">
          <Quote className="h-5 w-5 text-primary/40" />
          <p className="mt-3 text-sm leading-relaxed text-foreground">
            {quote}
          </p>
          <div className="mt-5 flex items-center gap-3">
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={author}
                className="h-10 w-10 rounded-full object-cover ring-2 ring-border"
              />
            ) : (
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold text-sm ring-2 ring-border">
                {author
                  .split(" ")
                  .map((n) => n[0])
                  .join("")}
              </div>
            )}
            <div>
              <p className="text-sm font-medium text-foreground">{author}</p>
              <p className="text-xs text-muted-foreground">
                {role}, {company}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}
