import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import CookieConsentBanner from "@/components/shared/cookie-consent-banner"
import { loadConsent, saveConsent, getDefaultConsent } from "@/lib/consent"

describe("CookieConsentBanner", () => {
  beforeEach(() => {
    localStorage.clear()
    Object.defineProperty(window, "gtag", { writable: true, value: vi.fn() })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("renders the banner when no consent is stored", () => {
    render(<CookieConsentBanner />)
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.getByText("Cookie Consent")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /accept all/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /reject all/i })).toBeInTheDocument()
  })

  it("does not render when a valid consent is already stored", () => {
    saveConsent({ ...getDefaultConsent(), timestamp: Date.now() })
    render(<CookieConsentBanner />)
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("accept all persists granted consent and applies it to gtag", () => {
    render(<CookieConsentBanner />)
    fireEvent.click(screen.getByRole("button", { name: /accept all/i }))

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(window.gtag).toHaveBeenCalledWith("consent", "update", {
      analytics_storage: "granted",
      ad_storage: "granted",
      ad_user_data: "granted",
      ad_personalization: "granted",
    })
    const stored = loadConsent()
    expect(stored?.analytics).toBe(true)
    expect(stored?.marketing).toBe(true)
    expect(stored?.necessary).toBe(true)
  })

  it("reject all persists denied consent and applies it to gtag", () => {
    render(<CookieConsentBanner />)
    fireEvent.click(screen.getByRole("button", { name: /reject all/i }))

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(window.gtag).toHaveBeenCalledWith("consent", "update", {
      analytics_storage: "denied",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    })
  })

  it("manage preferences reveals toggles and saving applies the chosen categories", () => {
    render(<CookieConsentBanner />)
    fireEvent.click(screen.getByRole("button", { name: /manage preferences/i }))

    expect(screen.getByText("Strictly Necessary")).toBeInTheDocument()
    const analyticsToggle = screen.getByRole("switch", { name: /toggle analytics cookies/i })
    fireEvent.click(analyticsToggle)

    fireEvent.click(screen.getByRole("button", { name: /save preferences/i }))

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(window.gtag).toHaveBeenCalledWith("consent", "update", {
      analytics_storage: "granted",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    })
    const stored = loadConsent()
    expect(stored?.analytics).toBe(true)
    expect(stored?.marketing).toBe(false)
  })

  it("applies a stored consent to gtag on mount", () => {
    saveConsent({ ...getDefaultConsent(), timestamp: Date.now(), analytics: true, marketing: false })
    render(<CookieConsentBanner />)

    expect(window.gtag).toHaveBeenCalledWith("consent", "update", {
      analytics_storage: "granted",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    })
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })
})
