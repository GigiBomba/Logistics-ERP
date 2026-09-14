// ---------------------------------------------------------------------------
// Error reporting service — lightweight, client-only fatal-error reporter.
//
// Deliberately NOT Sentry: the approved decision for this repo is a lightweight
// hook that (a) ALWAYS feeds the existing analytics `trackError` funnel and
// (b) for AUTHENTICATED users files a support ticket so the incident reaches
// the team's existing queue.  For UNAUTHENTICATED / opted-out users the same
// PII-free digest is POSTed to a rate-limited anonymous channel
// (POST /api/v1/support/anonymous-error) so fatal errors are never silent.
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
 * ALWAYS calls `trackError` first (consent-gated inside that service).
 * When the user is authenticated (in-memory access token present), a support
 * ticket is filed fire-and-forget; when NOT authenticated, the same PII-free
 * digest is POSTed to the rate-limited anonymous channel.  Either way the
 * request is fire-and-forget — failures are swallowed so a broken network
 * never masks the original crash. Duplicate signatures are suppressed per
 * browser session via sessionStorage on both paths.
 */
export function reportFatalError(error: unknown, componentStack?: string): void {
  const digest = buildReportDigest(error, componentStack ?? "")

  trackError(error instanceof Error ? error : new Error(String(error)), {
    componentStack: componentStack ?? "",
    fatal: "true",
  })

  // Session dedupe applies to both paths — the same crash is reported at most
  // once per browser session (identical to the previous authed-only behaviour).
  const signature = errorSignature(error, componentStack)
  if (hasReportedThisSession(signature)) return
  markReportedThisSession(signature)

  if (getAccessToken()) {
    // AUTHENTICATED: file a support ticket so the incident reaches the team's
    // existing queue (server-side auth is required to create tickets).
    const payload: CreateTicketRequest = {
      category: "bug",
      subject: "[Fatal UI Error]",
      description: digest,
    }
    supportApi.createTicket(payload).catch(() => {})
    return
  }

  // UNAUTHENTICATED: file the same digest to the anonymous channel (rate-limited
  // per IP server-side). The digest is kept within the 4KB server-side cap, and
  // the URL is included for repro context.
  // Swap this block for `Sentry.captureException(error)` when Sentry is adopted.
  supportApi
    .reportAnonymousError({
      digest: digest.slice(0, DIGEST_CAP),
      component_stack: componentStack ?? "",
      url: typeof window !== "undefined" ? window.location.href : undefined,
    })
    .catch(() => {})
}