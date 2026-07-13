import * as React from "react"
import { cn } from "@/lib/utils"

export interface TooltipProps {
  content: React.ReactNode
  children: React.ReactNode
  delay?: number
  side?: "top" | "bottom" | "left" | "right"
  className?: string
}

export function Tooltip({ content, children, delay = 300, side = "top", className }: TooltipProps) {
  const [visible, setVisible] = React.useState(false)
  const timeoutRef = React.useRef<number>(undefined)

  const show = React.useCallback(() => {
    window.clearTimeout(timeoutRef.current)
    timeoutRef.current = window.setTimeout(() => setVisible(true), delay)
  }, [delay])

  const hide = React.useCallback(() => {
    window.clearTimeout(timeoutRef.current)
    setVisible(false)
  }, [])

  React.useEffect(() => {
    return () => window.clearTimeout(timeoutRef.current)
  }, [])

  const sideClasses: Record<string, string> = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  }

  return (
    <div
      className={cn("relative inline-flex", className)}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {visible && (
        <div
          role="tooltip"
          className={cn(
            "absolute z-50 max-w-xs rounded-md bg-foreground px-2.5 py-1.5 text-xs text-background shadow-sm pointer-events-none",
            "animate-in fade-in zoom-in-95",
            sideClasses[side]
          )}
        >
          {content}
        </div>
      )}
    </div>
  )
}
