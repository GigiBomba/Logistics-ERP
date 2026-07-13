"use client"

import { cn } from "@/lib/utils"

interface HeroSectionProps {
  title: string
  description?: string
  children?: React.ReactNode
  className?: string
  align?: "left" | "center"
  size?: "default" | "large" | "compact"
  background?: React.ReactNode
}

const sizeStyles = {
  default: "py-20 md:py-28",
  large: "py-24 md:py-36",
  compact: "py-12 md:py-16",
}

const titleSizes = {
  default: "text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl",
  large: "text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl",
  compact: "text-2xl font-bold tracking-tight sm:text-3xl",
}

export function HeroSection({
  title,
  description,
  children,
  className,
  align = "left",
  size = "default",
  background,
}: HeroSectionProps) {
  return (
    <div className={cn("relative overflow-hidden", sizeStyles[size], className)}>
      {background && <div className="absolute inset-0 -z-10">{background}</div>}
      <div
        className={cn(
          "container-wide",
          align === "center" && "flex flex-col items-center text-center"
        )}
      >
        <div className={cn(align === "center" && "max-w-3xl")}>
          <h1 className={cn(titleSizes[size])}>{title}</h1>
          {description && (
            <p className="mt-4 text-lg text-muted-foreground sm:text-xl">{description}</p>
          )}
          {children && <div className="mt-8">{children}</div>}
        </div>
      </div>
    </div>
  )
}
