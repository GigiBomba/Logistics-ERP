import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

const gtag = vi.fn()

// Fake a configured measurement ID so the `hasGtag` gate can be exercised.
vi.mock("@/config/site", () => ({
  analyticsConfig: { measurementId: "G-TEST123" },
}))

const { consentMock } = vi.hoisted(() => ({
  consentMock: vi.fn(() => ({ analytics: false })),
}))

vi.mock("@/lib/consent", () => ({
  getConsent: consentMock,
}))

import {
  trackPageView,
  trackEvent,
  trackScrollDepth,
  trackCTAClick,
  trackDownload,
  trackPricingInteraction,
  trackSearch,
  trackError,
} from "@/services/analytics"

const logSpy = vi.spyOn(console, "log").mockImplementation(() => {})
const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {})

function grantConsent() {
  consentMock.mockReturnValue({ analytics: true } as any)
}

function denyConsent() {
  consentMock.mockReturnValue({ analytics: false } as any)
}

describe("analytics service", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    denyConsent()
    window.gtag = gtag
  })

  afterEach(() => {
    delete (window as any).gtag
  })

  describe("consent gating", () => {
    it("trackPageView is a no-op without consent", () => {
      trackPageView("/home")
      expect(gtag).not.toHaveBeenCalled()
      expect(logSpy).not.toHaveBeenCalled()
    })

    it("trackEvent is a no-op without consent", () => {
      trackEvent("click_signup", "engagement")
      expect(gtag).not.toHaveBeenCalled()
    })

    it("trackError is a no-op without consent", () => {
      trackError(new Error("boom"))
      expect(gtag).not.toHaveBeenCalled()
      expect(errorSpy).not.toHaveBeenCalled()
    })
  })

  describe("gtag dispatch with consent", () => {
    beforeEach(() => grantConsent())

    it("trackPageView sends config event with page_path", () => {
      trackPageView("/pricing")
      expect(gtag).toHaveBeenCalledWith("config", "G-TEST123", { page_path: "/pricing" })
    })

    it("trackEvent sends event with category/label/value", () => {
      trackEvent("click_signup", "engagement", "hero", 5)
      expect(gtag).toHaveBeenCalledWith("event", "click_signup", {
        event_category: "engagement",
        event_label: "hero",
        value: 5,
      })
    })

    it("trackEvent omits undefined label/value", () => {
      trackEvent("page_share", "sharing")
      expect(gtag).toHaveBeenCalledWith("event", "page_share", {
        event_category: "sharing",
        event_label: undefined,
        value: undefined,
      })
    })

    it("trackScrollDepth rounds depth to nearest 25%", () => {
      trackScrollDepth(63)
      expect(gtag).toHaveBeenCalledWith("event", "scroll_depth", { depth: 75 })
    })

    it("trackCTAClick sends cta_click event", () => {
      trackCTAClick("hero_trial", "/")
      expect(gtag).toHaveBeenCalledWith("event", "cta_click", { cta_name: "hero_trial", page: "/" })
    })

    it("trackDownload sends download event", () => {
      trackDownload("4.2.0", "windows")
      expect(gtag).toHaveBeenCalledWith("event", "download", { version: "4.2.0", platform: "windows" })
    })

    it("trackPricingInteraction sends pricing_interaction event", () => {
      trackPricingInteraction("toggle-annual")
      expect(gtag).toHaveBeenCalledWith("event", "pricing_interaction", { action: "toggle-annual" })
    })

    it("trackSearch sends search event with result count", () => {
      trackSearch("routes", 12)
      expect(gtag).toHaveBeenCalledWith("event", "search", { query: "routes", result_count: 12 })
    })

    it("trackError spreads context (fatal passthrough)", () => {
      trackError(new Error("kaboom"), { fatal: "true", route: "/dashboard" })
      expect(gtag).toHaveBeenCalledWith("event", "exception", {
        description: "kaboom",
        fatal: "true",
        route: "/dashboard",
      })
    })

    it("trackError sends exception event with fatal false when context missing", () => {
      trackError(new Error("kaboom"))
      expect(gtag).toHaveBeenCalledWith("event", "exception", {
        description: "kaboom",
        fatal: false,
      })
    })
  })

  describe("no gtag loaded", () => {
    beforeEach(() => {
      grantConsent()
      delete (window as any).gtag
    })

    it("does not throw and does not dispatch", () => {
      expect(() => trackPageView("/x")).not.toThrow()
      expect(gtag).not.toHaveBeenCalled()
    })
  })
})
