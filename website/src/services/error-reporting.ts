// ---------------------------------------------------------------------------
// Error reporting service — lightweight, client-only fatal-error reporter.
//
// Deliberately NOT Sentry: the approved decision for this repo is a lightweight
// hook that (a) ALWAYS feeds the existing analytics `trackError` funnel and
// (b) for AUTHENTICATED users files a support ticket so the incident reaches
// the team's existing queue.
//
// Sentry-swappable seam: to adopt Sentry later, replace the bodies of
// `reportFatalError` (and its digest builder) with `Sentry.captureException(...)`
// + `Sentry.withScope(...)`. The only call site is the ErrorBoundary `onError`
// in main.tsx, so nothing else needs to change.
//
// Client-only: depends on `window.sessionStorage` and the in-memory access
// token, so it must never be imported from SSR code (SSRApp intentionally
// does NOT wire this hook).
// ---------------------------------------------------------------------------

import { getAccessToken } from "@/api/client"
import { supportApi, type CreateTicketRequest } from "@/api/endpoints"
import { trackError } from "@/services/analytics"

const DIGEST_CAP = 4000
const DEDUPE_STORAGE_KEY = "operion-fatal-error-signatures"
const DEDUPE_MAX = 50

/** URL-safe, 4KB-capped digest — same shape as main.tsx `buildReportDigest`. */
function buildReportDigest(error: unknown, componentStack: string): string {
  const message =
    error instanceof Error ? `${error.message}\n\n${error.stack ?? ""}` : String(error)
  return encodeURIComponent(
    `[Fatal UI Error]\n\n${message}\n\nComponent stack:\n${componentStack}`.slice(0, DIGEST_CAP)
  )
}

/** Stable-ish per-error signature (message + first throw-site frames) for session dedupe. */
function errorSignature(error: unknown, componentStack?: string): string {
  const message = error instanceof Error ? error.message : String(error)
  const stackFrame = error instanceof Error ? (error.stack ?? "").split("\n")[1]?.trim() ?? "" : ""
  const componentFrame = (componentStack ?? "").split("\n")[1]?.trim() ?? ""
  return `${message}::${stackFrame}::${componentFrame}`
}

function loadReportedSignatures(): string[] {
  try {
    const raw = window.sessionStorage.getItem(DEDUPE_STORAGE_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    // sessionStorage unavailable (blocked/private mode) — dedupe is best-effort only
    return []
  }
}

function saveReportedSignatures(signatures: string[]): void {
  try {
    window.sessionStorage.setItem(DEDUPE_STORAGE_KEY, JSON.stringify(signatures.slice(-DEDUPE_MAX)))
  } catch {
    // Ignore — dedupe is best-effort; never let reporting break the app.
  }
}

function hasReportedThisSession(signature: string): boolean {
  return loadReportedSignatures().includes(signature)
}

function markReportedThisSession(signature: string): void {
  const signatures = loadReportedSignatures()
  if (!signatures.includes(signature)) {
    signatures.push(signature)
    saveReportedSignatures(signatures)
  }
}

/**
 * Report a fatal (uncaught render) error.
 *
 * ALWAYS calls `trackError` first (consent-gated inside that service). When the
 * user is authenticated (in-memory access token present), a support ticket is
 * filed fire-and-forget — failures are swallowed so a broken network never masks
 * the original crash. Duplicate signatures are suppressed per browser session
 * via sessionStorage.
 */
export function reportFatalError(error: unknown, componentStack?: string): void {
  const digest = buildReportDigest(error, componentStack ?? "")

  trackError(error instanceof Error ? error : new Error(String(error)), {
    componentStack: componentStack ?? "",
    fatal: "true",
  })

  // Only authenticated users can file tickets (server-side auth is required;
  // public visitors are routed to login via the normal support flow instead).
  if (!getAccessToken()) return

  const signature = errorSignature(error, componentStack)
  if (hasReportedThisSession(signature)) return
  markReportedThisSession(signature)

  // Swap this block for `Sentry.captureException(error)` when Sentry is adopted.
  const payload: CreateTicketRequest = {
    category: "bug",
    subject: "[Fatal UI Error]",
    description: digest,
  }

  supportApi.createTicket(payload).catch(() => {})
}