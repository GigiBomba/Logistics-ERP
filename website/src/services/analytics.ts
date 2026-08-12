import { analyticsConfig } from "@/config/site"
import { getConsent } from "@/lib/consent"

// ---------------------------------------------------------------------------
// Analytics service — lightweight wrapper around Google Analytics (gtag).
// In development it logs to the console; in production it dispatches to gtag
// if a valid measurement ID is configured.  All functions are safe to call
// even when GA is not loaded.
//
// All tracking is gated on analytics consent (see @/lib/consent).  If the
// visitor has not granted analytics consent, every call is a no-op — nothing
// is logged to the console and nothing is dispatched to gtag.
// ---------------------------------------------------------------------------

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void
    dataLayer?: Record<string, unknown>[]
  }
}

const MEASUREMENT_ID = analyticsConfig.measurementId

function hasGtag(): boolean {
  return !!MEASUREMENT_ID && typeof window.gtag === "function"
}

/** Whether the visitor granted analytics consent (defaults to denied). */
function hasAnalyticsConsent(): boolean {
  return getConsent().analytics === true
}

/**
 * Track a page view.
 * Call this once per route change with the new pathname.
 */
export function trackPageView(path: string) {
  if (!hasAnalyticsConsent()) return

  if (import.meta.env.DEV) {
    console.log(`[Analytics] Page view: ${path}`)
  }

  if (hasGtag()) {
    window.gtag!("config", MEASUREMENT_ID, { page_path: path })
  }
}

/**
 * Track a custom event.
 *
 * @param name  - Event action name (e.g. "click_signup")
 * @param category - Event category (e.g. "engagement")
 * @param label - Optional event label
 * @param value - Optional numeric value
 */
export function trackEvent(
  name: string,
  category: string,
  label?: string,
  value?: number,
) {
  if (!hasAnalyticsConsent()) return

  if (import.meta.env.DEV) {
    console.log(`[Analytics] Event: ${name} (${category})`, { label, value })
  }

  if (hasGtag()) {
    window.gtag!("event", name, {
      event_category: category,
      event_label: label,
      value: value,
    })
  }
}

/**
 * Track scroll depth percentage (rounded to nearest 25%).
 */
export function trackScrollDepth(depth: number) {
  if (!hasAnalyticsConsent()) return

  if (import.meta.env.DEV) {
    console.log(`[Analytics] Scroll depth: ${depth}%`)
  }

  if (hasGtag()) {
    window.gtag!("event", "scroll_depth", {
      depth: Math.round(depth / 25) * 25,
    })
  }
}

/**
 * Track CTA button clicks.
 *
 * @param ctaName - Identifies the CTA (e.g. "hero_trial", "pricing_contact")
 * @param page    - The page path where the click occurred
 */
export function trackCTAClick(ctaName: string, page: string) {
  if (!hasAnalyticsConsent()) return

  if (import.meta.env.DEV) {
    console.log(`[Analytics] CTA click: ${ctaName} on ${page}`)
  }

  if (hasGtag()) {
    window.gtag!("event", "cta_click", { cta_name: ctaName, page })
  }
}

/**
 * Track a download event.
 *
 * @param version  - Software version (e.g. "4.2.0")
 * @param platform - Target platform (e.g. "windows", "linux")
 */
export function trackDownload(version: string, platform: string) {
  if (!hasAnalyticsConsent()) return

  if (import.meta.env.DEV) {
    console.log(`[Analytics] Download: ${version} for ${platform}`)
  }

  if (hasGtag()) {
    window.gtag!("event", "download", { version, platform })
  }
}

/**
 * Track pricing-page interactions (tab switches, toggle clicks, etc.).
 */
export function trackPricingInteraction(action: string) {
  if (!hasAnalyticsConsent()) return

  if (hasGtag()) {
    window.gtag!("event", "pricing_interaction", { action })
  }
}

/**
 * Track site search queries.
 *
 * @param query       - The search term
 * @param resultCount - Number of results returned
 */
export function trackSearch(query: string, resultCount: number) {
  if (!hasAnalyticsConsent()) return

  if (hasGtag()) {
    window.gtag!("event", "search", { query, result_count: resultCount })
  }
}

/**
 * Track an error — logs to console in dev, sends to GA4 in production.
 * Designed as a lightweight wrapper that can be swapped for Sentry later.
 * Like every other tracking function this is gated on analytics consent,
 * so it is a no-op when the visitor has not granted it.
 *
 * @param error   - The Error object to track
 * @param context - Optional key-value metadata (e.g. { componentStack, fatal, route })
 */
export function trackError(error: Error, context?: Record<string, string>) {
  if (!hasAnalyticsConsent()) return

  // Dev: log to console with full context
  if (import.meta.env.DEV) {
    console.error("[Error Tracking]", error.message, context)
  }

  // Prod: send to GA4 as exception event
  if (hasGtag()) {
    window.gtag!("event", "exception", {
      description: error.message,
      fatal: context?.fatal === "true",
      ...context,
    })
  }
}
