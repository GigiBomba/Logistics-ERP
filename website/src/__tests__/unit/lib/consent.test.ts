import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import {
  loadConsent,
  saveConsent,
  clearConsent,
  getDefaultConsent,
  getConsent,
  applyConsent,
  type ConsentState,
} from "@/lib/consent"

const CONSENT_KEY = "operion_consent_v2"
const VERSION = "2.0.0"
const YEAR_MS = 365 * 24 * 60 * 60 * 1000

function makeState(overrides: Partial<ConsentState> = {}): ConsentState {
  return {
    version: VERSION,
    timestamp: Date.now(),
    necessary: true,
    analytics: false,
    marketing: false,
    ...overrides,
  }
}

/** Read raw stored JSON directly for storage-shape assertions. */
function readStored(): Record<string, unknown> | null {
  const raw = localStorage.getItem(CONSENT_KEY)
  return raw ? JSON.parse(raw) : null
}

describe("loadConsent()", () => {
  beforeEach(() => localStorage.clear())

  it("returns null when nothing is stored", () => {
    expect(loadConsent()).toBeNull()
  })

  it("returns the stored state verbatim", () => {
    const state = makeState({ analytics: true })
    saveConsent(state)
    expect(loadConsent()).toEqual(state)
  })

  it("returns null for invalid JSON", () => {
    localStorage.setItem(CONSENT_KEY, "{not-json")
    expect(loadConsent()).toBeNull()
  })

  it("returns null when the stored version does not match (re-prompt on version bump)", () => {
    saveConsent(makeState({ version: "1.0.0", analytics: true }))
    expect(loadConsent()).toBeNull()
  })

  it("returns null when the consent has expired (older than 12 months)", () => {
    saveConsent(makeState({ timestamp: Date.now() - YEAR_MS - 1000 }))
    expect(loadConsent()).toBeNull()
  })

  it("returns the state when still inside the 12-month window (1s before expiry)", () => {
    // Not exactly AT the boundary — wall-clock time advances between save and
    // load, so use a timestamp comfortably inside the window.
    const state = makeState({ timestamp: Date.now() - YEAR_MS + 1000 })
    saveConsent(state)
    expect(loadConsent()).toEqual(state)
  })
})

describe("saveConsent() / clearConsent()", () => {
  beforeEach(() => localStorage.clear())

  it("persists the full state as JSON under the consent key", () => {
    const state = makeState({ analytics: true, marketing: true })
    saveConsent(state)
    expect(readStored()).toEqual({ ...state })
  })

  it("clearConsent removes the stored key", () => {
    saveConsent(makeState())
    expect(localStorage.getItem(CONSENT_KEY)).not.toBeNull()
    clearConsent()
    expect(localStorage.getItem(CONSENT_KEY)).toBeNull()
  })
})

describe("getDefaultConsent()", () => {
  it("returns a fresh all-denied default with necessary always true", () => {
    const d = getDefaultConsent()
    expect(d).toEqual({
      version: VERSION,
      timestamp: 0,
      necessary: true,
      analytics: false,
      marketing: false,
    })
  })

  it("returns a fresh copy on every call (no shared mutable object)", () => {
    const a = getDefaultConsent()
    const b = getDefaultConsent()
    a.marketing = true
    expect(b.marketing).toBe(false)
  })
})

describe("getConsent()", () => {
  beforeEach(() => localStorage.clear())

  it("returns the stored consent when present", () => {
    const state = makeState({ analytics: true })
    saveConsent(state)
    expect(getConsent()).toEqual(state)
  })

  it("falls back to the all-denied default when nothing is stored", () => {
    expect(getConsent()).toEqual(getDefaultConsent())
  })

  it("falls back to the default when the stored consent is expired", () => {
    saveConsent(makeState({ timestamp: Date.now() - YEAR_MS - 1000, analytics: true }))
    const consent = getConsent()
    expect(consent.analytics).toBe(false)
    expect(consent.marketing).toBe(false)
  })
})

describe("applyConsent()", () => {
  beforeEach(() => {
    localStorage.clear()
    Object.defineProperty(window, "gtag", { writable: true, value: vi.fn() })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("is a no-op when gtag is not loaded", () => {
    ;(window as any).gtag = undefined
    expect(() => applyConsent(makeState())).not.toThrow()
    expect(window.gtag).toBeUndefined()
  })

  it("maps analytics consent to analytics_storage granted", () => {
    applyConsent(makeState({ analytics: true, marketing: false }))
    expect(window.gtag).toHaveBeenCalledWith("consent", "update", {
      analytics_storage: "granted",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    })
  })

  it("maps marketing consent to the ad_* flags granted", () => {
    applyConsent(makeState({ analytics: false, marketing: true }))
    expect(window.gtag).toHaveBeenCalledWith("consent", "update", {
      analytics_storage: "denied",
      ad_storage: "granted",
      ad_user_data: "granted",
      ad_personalization: "granted",
    })
  })

  it("grants everything when both categories are allowed", () => {
    applyConsent(makeState({ analytics: true, marketing: true }))
    expect(window.gtag).toHaveBeenCalledWith("consent", "update", {
      analytics_storage: "granted",
      ad_storage: "granted",
      ad_user_data: "granted",
      ad_personalization: "granted",
    })
  })
})
