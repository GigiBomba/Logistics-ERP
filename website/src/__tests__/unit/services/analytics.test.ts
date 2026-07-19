import { describe, it, expect, vi, beforeEach } from "vitest"
import {
  trackPageView,
  trackEvent,
  trackScrollDepth,
  trackCTAClick,
  trackDownload,
  trackPricingInteraction,
  trackSearch,
} from "@/services/analytics"

// ---------------------------------------------------------------------------
// Provide a valid measurement ID so hasGtag() can return true when
// window.gtag is also available.
// ---------------------------------------------------------------------------
vi.mock("@/config/site", () => ({
  analyticsConfig: { measurementId: "G-TEST123" },
}))

beforeEach(() => {
  // Keep console output clean; suppress [Analytics] dev logs.
  vi.stubEnv("DEV", false)
  // Provide a fresh gtag spy before every test.
  window.gtag = vi.fn()
})

// ---------------------------------------------------------------------------
// trackPageView
// ---------------------------------------------------------------------------
describe("trackPageView()", () => {
  it("calls gtag config with the correct path", () => {
    trackPageView("/home")
    expect(window.gtag).toHaveBeenCalledTimes(1)
    expect(window.gtag).toHaveBeenCalledWith("config", "G-TEST123", {
      page_path: "/home",
    })
  })

  it("handles root path", () => {
    trackPageView("/")
    expect(window.gtag).toHaveBeenCalledWith("config", "G-TEST123", {
      page_path: "/",
    })
  })

  it("handles nested paths", () => {
    trackPageView("/pricing/business")
    expect(window.gtag).toHaveBeenCalledWith("config", "G-TEST123", {
      page_path: "/pricing/business",
    })
  })
})

// ---------------------------------------------------------------------------
// trackEvent
// ---------------------------------------------------------------------------
describe("trackEvent()", () => {
  it("calls gtag event with name and category", () => {
    trackEvent("click_signup", "engagement")
    expect(window.gtag).toHaveBeenCalledWith("event", "click_signup", {
      event_category: "engagement",
      event_label: undefined,
      value: undefined,
    })
  })

  it("passes optional label and value", () => {
    trackEvent("download_pdf", "content", "user-guide", 42)
    expect(window.gtag).toHaveBeenCalledWith("event", "download_pdf", {
      event_category: "content",
      event_label: "user-guide",
      value: 42,
    })
  })

  it("accepts zero as a value", () => {
    trackEvent("score_update", "gameplay", "round-1", 0)
    expect(window.gtag).toHaveBeenCalledWith("event", "score_update", {
      event_category: "gameplay",
      event_label: "round-1",
      value: 0,
    })
  })
})

// ---------------------------------------------------------------------------
// trackScrollDepth
// ---------------------------------------------------------------------------
describe("trackScrollDepth()", () => {
  it("rounds depth to the nearest 25%", () => {
    trackScrollDepth(25)
    expect(window.gtag).toHaveBeenCalledWith("event", "scroll_depth", {
      depth: 25,
    })
  })

  it("rounds 30 % down to 25 %", () => {
    trackScrollDepth(30)
    expect(window.gtag).toHaveBeenCalledWith("event", "scroll_depth", {
      depth: 25,
    })
  })

  it("rounds 50 % to 50 %", () => {
    trackScrollDepth(50)
    expect(window.gtag).toHaveBeenCalledWith("event", "scroll_depth", {
      depth: 50,
    })
  })

  it("rounds 99 % up to 100 %", () => {
    trackScrollDepth(99)
    expect(window.gtag).toHaveBeenCalledWith("event", "scroll_depth", {
      depth: 100,
    })
  })

  it("rounds 100 % to 100 %", () => {
    trackScrollDepth(100)
    expect(window.gtag).toHaveBeenCalledWith("event", "scroll_depth", {
      depth: 100,
    })
  })

  it("rounds 0 % to 0 %", () => {
    trackScrollDepth(0)
    expect(window.gtag).toHaveBeenCalledWith("event", "scroll_depth", {
      depth: 0,
    })
  })

  it("rounds values above 100 correctly", () => {
    trackScrollDepth(150)
    expect(window.gtag).toHaveBeenCalledWith("event", "scroll_depth", {
      depth: 150,
    })
  })
})

// ---------------------------------------------------------------------------
// trackCTAClick
// ---------------------------------------------------------------------------
describe("trackCTAClick()", () => {
  it("sends cta_name and page", () => {
    trackCTAClick("hero_trial", "/")
    expect(window.gtag).toHaveBeenCalledWith("event", "cta_click", {
      cta_name: "hero_trial",
      page: "/",
    })
  })

  it("handles CTA on a deep page", () => {
    trackCTAClick("pricing_contact", "/pricing/enterprise")
    expect(window.gtag).toHaveBeenCalledWith("event", "cta_click", {
      cta_name: "pricing_contact",
      page: "/pricing/enterprise",
    })
  })
})

// ---------------------------------------------------------------------------
// trackDownload
// ---------------------------------------------------------------------------
describe("trackDownload()", () => {
  it("sends version and platform", () => {
    trackDownload("4.2.0", "windows")
    expect(window.gtag).toHaveBeenCalledWith("event", "download", {
      version: "4.2.0",
      platform: "windows",
    })
  })

  it("handles linux platform", () => {
    trackDownload("4.2.0", "linux")
    expect(window.gtag).toHaveBeenCalledWith("event", "download", {
      version: "4.2.0",
      platform: "linux",
    })
  })

  it("handles macOS platform", () => {
    trackDownload("4.2.0", "macos")
    expect(window.gtag).toHaveBeenCalledWith("event", "download", {
      version: "4.2.0",
      platform: "macos",
    })
  })
})

// ---------------------------------------------------------------------------
// trackPricingInteraction
// ---------------------------------------------------------------------------
describe("trackPricingInteraction()", () => {
  it("sends action: view", () => {
    trackPricingInteraction("view")
    expect(window.gtag).toHaveBeenCalledWith("event", "pricing_interaction", {
      action: "view",
    })
  })

  it("sends action: select", () => {
    trackPricingInteraction("select")
    expect(window.gtag).toHaveBeenCalledWith("event", "pricing_interaction", {
      action: "select",
    })
  })

  it("sends action: compare", () => {
    trackPricingInteraction("compare")
    expect(window.gtag).toHaveBeenCalledWith("event", "pricing_interaction", {
      action: "compare",
    })
  })
})

// ---------------------------------------------------------------------------
// trackSearch
// ---------------------------------------------------------------------------
describe("trackSearch()", () => {
  it("sends query and result count", () => {
    trackSearch("route planning", 12)
    expect(window.gtag).toHaveBeenCalledWith("event", "search", {
      query: "route planning",
      result_count: 12,
    })
  })

  it("handles zero results", () => {
    trackSearch("nonexistent", 0)
    expect(window.gtag).toHaveBeenCalledWith("event", "search", {
      query: "nonexistent",
      result_count: 0,
    })
  })
})

// ---------------------------------------------------------------------------
// Error handling – analytics service unavailable
// ---------------------------------------------------------------------------
describe("error handling", () => {
  it("does not throw when gtag is undefined", () => {
    window.gtag = undefined
    expect(() => {
      trackPageView("/test")
      trackEvent("e", "c")
      trackScrollDepth(50)
      trackCTAClick("cta", "/p")
      trackDownload("1.0", "win")
      trackPricingInteraction("view")
      trackSearch("q", 1)
    }).not.toThrow()
  })

  it("does not throw when gtag is null", () => {
    window.gtag = null as unknown as (...args: unknown[]) => void
    expect(() => {
      trackPageView("/test")
      trackEvent("e", "c")
      trackScrollDepth(50)
      trackCTAClick("cta", "/p")
      trackDownload("1.0", "win")
      trackPricingInteraction("view")
      trackSearch("q", 1)
    }).not.toThrow()
  })

  it("does not call gtag when gtag is undefined", () => {
    window.gtag = undefined
    trackPageView("/test")
    trackEvent("e", "c")
    expect(window.gtag).toBeUndefined()
  })
})

// ---------------------------------------------------------------------------
// Edge cases – empty strings, null/undefined values, special characters
// ---------------------------------------------------------------------------
describe("edge cases", () => {
  beforeEach(() => {
    window.gtag = vi.fn()
  })

  describe("empty strings", () => {
    it("trackPageView with empty path", () => {
      expect(() => trackPageView("")).not.toThrow()
      expect(window.gtag).toHaveBeenCalledWith("config", "G-TEST123", {
        page_path: "",
      })
    })

    it("trackEvent with empty name and category", () => {
      expect(() => trackEvent("", "")).not.toThrow()
      expect(window.gtag).toHaveBeenCalledWith("event", "", {
        event_category: "",
        event_label: undefined,
        value: undefined,
      })
    })

    it("trackCTAClick with empty cta name", () => {
      expect(() => trackCTAClick("", "/page")).not.toThrow()
      expect(window.gtag).toHaveBeenCalledWith("event", "cta_click", {
        cta_name: "",
        page: "/page",
      })
    })

    it("trackDownload with empty version and platform", () => {
      expect(() => trackDownload("", "")).not.toThrow()
    })

    it("trackSearch with empty query", () => {
      expect(() => trackSearch("", 0)).not.toThrow()
      expect(window.gtag).toHaveBeenCalledWith("event", "search", {
        query: "",
        result_count: 0,
      })
    })
  })

  describe("undefined optional parameters", () => {
    it("trackEvent omits label and value when not provided", () => {
      trackEvent("test", "cat")
      expect(window.gtag).toHaveBeenCalledWith("event", "test", {
        event_category: "cat",
        event_label: undefined,
        value: undefined,
      })
    })

    it("trackEvent with undefined label but explicit value", () => {
      trackEvent("test", "cat", undefined, 99)
      expect(window.gtag).toHaveBeenCalledWith("event", "test", {
        event_category: "cat",
        event_label: undefined,
        value: 99,
      })
    })
  })

  describe("special characters in event names", () => {
    it("trackEvent with special characters in name", () => {
      expect(() =>
        trackEvent("click_btn#1@test!", "catégorie$%"),
      ).not.toThrow()
      expect(window.gtag).toHaveBeenCalledWith("event", "click_btn#1@test!", {
        event_category: "catégorie$%",
        event_label: undefined,
        value: undefined,
      })
    })

    it("trackPageView with query-string path", () => {
      trackPageView("/search?q=hello&lang=en")
      expect(window.gtag).toHaveBeenCalledWith("config", "G-TEST123", {
        page_path: "/search?q=hello&lang=en",
      })
    })

    it("trackCTAClick with special characters", () => {
      expect(() =>
        trackCTAClick("cta_#1", "/page?ref=test"),
      ).not.toThrow()
      expect(window.gtag).toHaveBeenCalledWith("event", "cta_click", {
        cta_name: "cta_#1",
        page: "/page?ref=test",
      })
    })

    it("trackSearch with special characters in query", () => {
      expect(() => trackSearch("C# & C++", 5)).not.toThrow()
      expect(window.gtag).toHaveBeenCalledWith("event", "search", {
        query: "C# & C++",
        result_count: 5,
      })
    })
  })
})
