import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const progressVariants = cva("h-full w-full rounded-full transition-all", {
  variants: {
    variant: {
      default: "bg-primary",
      success: "bg-emerald-500",
      warning: "bg-amber-500",
    },
  },
  defaultVariants: {
    variant: "default",
  },
})

export interface ProgressProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof progressVariants> {
  value: number
}

export function Progress({ className, value, variant, ...props }: ProgressProps) {
  const clampedValue = Math.min(100, Math.max(0, value))

  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={clampedValue}
      aria-label={`${clampedValue}%`}
      className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}
      {...props}
    >
      <div
        className={cn(progressVariants({ variant }))}
        style={{ width: `${clampedValue}%` }}
      />
    </div>
  )
}
