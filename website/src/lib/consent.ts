// ---------------------------------------------------------------------------
// Cookie consent state — storage, versioning, expiry & GCMv2 application
// ---------------------------------------------------------------------------

const CONSENT_KEY = "operion_consent_v2"
const CONSENT_VERSION = "2.0.0" // Bump to force re-consent
const MAX_AGE_MS = 365 * 24 * 60 * 60 * 1000 // 12 months

export interface ConsentState {
  version: string
  timestamp: number
  analytics: boolean
  marketing: boolean
  necessary: boolean // always true
}

const DEFAULT: ConsentState = {
  version: CONSENT_VERSION,
  timestamp: 0,
  necessary: true,
  analytics: false,
  marketing: false,
}

/** Read stored consent — returns `null` if missing, expired, or version mismatch. */
export function loadConsent(): ConsentState | null {
  try {
    const raw = localStorage.getItem(CONSENT_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as ConsentState
    // Force re-consent on version change
    if (parsed.version !== CONSENT_VERSION) return null
    // Force re-consent if expired
    if (Date.now() - parsed.timestamp > MAX_AGE_MS) return null
    return parsed
  } catch {
    return null
  }
}

/** Persist consent state to localStorage. */
export function saveConsent(state: ConsentState): void {
  localStorage.setItem(CONSENT_KEY, JSON.stringify(state))
}

/** Remove stored consent (e.g. for reset/debug). */
export function clearConsent(): void {
  localStorage.removeItem(CONSENT_KEY)
}

/** Return a fresh default (denied) consent object. */
export function getDefaultConsent(): ConsentState {
  return { ...DEFAULT }
}

/** Read current consent state — defaults to all-denied when not stored. */
export function getConsent(): ConsentState {
  return loadConsent() ?? getDefaultConsent()
}

/**
 * Apply the given consent to Google Consent Mode v2.
 * Safe to call even when gtag is not loaded (no-op).
 */
export function applyConsent(state: ConsentState): void {
  if (typeof window.gtag !== "function") return
  window.gtag("consent", "update", {
    analytics_storage: state.analytics ? "granted" : "denied",
    ad_storage: state.marketing ? "granted" : "denied",
    ad_user_data: state.marketing ? "granted" : "denied",
    ad_personalization: state.marketing ? "granted" : "denied",
  })
}
