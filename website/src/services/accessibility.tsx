"use client"

import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"

// ─── SkipToContent ──────────────────────────────────────────

/**
 * SkipToContent renders a "Skip to content" link that is visually hidden
 * until focused. This lets keyboard users bypass the navigation and jump
 * directly to the main content region.
 *
 * @example
 * // Place as the very first child inside <body> or your layout wrapper
 * <SkipToContent contentId="main-content" />
 */
export function SkipToContent({ contentId = "main-content" }: { contentId?: string }) {
  return (
    <a
      href={`#${contentId}`}
      className={cn(
        "sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[9999]",
        "focus:flex focus:items-center focus:gap-2",
        "focus:rounded-lg focus:bg-background focus:px-4 focus:py-2.5",
        "focus:text-sm focus:font-medium focus:text-foreground",
        "focus:border focus:border-border",
        "focus:shadow-lg focus:ring-2 focus:ring-ring focus:ring-offset-2",
        "focus:outline-none"
      )}
    >
      <span aria-hidden="true">&darr;</span>
      Skip to content
    </a>
  )
}

// ─── useReducedMotion ───────────────────────────────────────

/**
 * useReducedMotion returns `true` when the user has requested reduced motion
 * via their OS/accessibility settings. Use this to disable or simplify
 * animations for users who experience motion sensitivity.
 *
 * @example
 * const prefersReducedMotion = useReducedMotion()
 * const animationProps = prefersReducedMotion
 *   ? {}
 *   : { initial: { opacity: 0 }, animate: { opacity: 1 } }
 */
export function useReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(() => {
    if (typeof window === "undefined") return false
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches
  })

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)")
    const handler = (event: MediaQueryListEvent) => setPrefersReducedMotion(event.matches)
    mq.addEventListener("change", handler)
    return () => mq.removeEventListener("change", handler)
  }, [])

  return prefersReducedMotion
}
