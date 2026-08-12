import * as React from "react"
import { createPortal } from "react-dom"
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
  const [position, setPosition] = React.useState({ top: 0, left: 0 })
  const timeoutRef = React.useRef<number>(undefined)
  const triggerRef = React.useRef<HTMLDivElement>(null)

  const calculatePosition = React.useCallback(() => {
    const triggerRect = triggerRef.current?.getBoundingClientRect()
    if (!triggerRect) return { top: 0, left: 0 }

    const gap = 4
    const positions: Record<string, { top: number; left: number }> = {
      top: { top: triggerRect.top - gap, left: triggerRect.left + triggerRect.width / 2 },
      bottom: { top: triggerRect.bottom + gap, left: triggerRect.left + triggerRect.width / 2 },
      left: { top: triggerRect.top + triggerRect.height / 2, left: triggerRect.left - gap },
      right: { top: triggerRect.top + triggerRect.height / 2, left: triggerRect.right + gap },
    }
    return positions[side] ?? positions.top
  }, [side])

  const show = React.useCallback(() => {
    window.clearTimeout(timeoutRef.current)
    timeoutRef.current = window.setTimeout(() => {
      setPosition(calculatePosition())
      setVisible(true)
    }, delay)
  }, [delay, calculatePosition])

  const hide = React.useCallback(() => {
    window.clearTimeout(timeoutRef.current)
    setVisible(false)
  }, [])

  React.useEffect(() => {
    return () => window.clearTimeout(timeoutRef.current)
  }, [])

  const sideTransform: Record<string, string> = {
    top: "translateX(-50%) translateY(-100%)",
    bottom: "translateX(-50%)",
    left: "translateX(-100%) translateY(-50%)",
    right: "translateY(-50%)",
  }

  return (
    <div
      ref={triggerRef}
      className={cn("relative inline-flex", className)}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {visible &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            role="tooltip"
            style={{
              position: "fixed",
              top: position.top,
              left: position.left,
              transform: sideTransform[side],
            }}
            className={cn(
              "z-50 max-w-xs rounded-md bg-foreground px-2.5 py-1.5 text-xs text-background shadow-sm pointer-events-none",
              "animate-in fade-in zoom-in-95"
            )}
          >
            {content}
          </div>,
          document.body
        )}
    </div>
  )
}
