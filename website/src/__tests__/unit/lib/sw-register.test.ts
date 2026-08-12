import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { registerServiceWorker } from "@/lib/sw-register"

describe("registerServiceWorker()", () => {
  beforeEach(() => {
    vi.spyOn(console, "log").mockImplementation(() => {})
    vi.spyOn(console, "warn").mockImplementation(() => {})
  })

  afterEach(() => {
    // Remove the jsdom serviceWorker stub so it doesn't leak across tests.
    // NOTE: vi.clearAllMocks (not restoreAllMocks) — the global setup mocks
    // console.error via spyOn and restoring it here would break act() noise
    // suppression for every test in this file.
    try {
      delete (navigator as unknown as { serviceWorker?: unknown }).serviceWorker
    } catch {
      // Property may not be configurable in this environment — ignore.
    }
    vi.clearAllMocks()
  })

  it("does nothing when the browser has no Service Worker support", () => {
    const addEventListener = vi.spyOn(window, "addEventListener")

    registerServiceWorker()

    expect(addEventListener).not.toHaveBeenCalledWith("load", expect.any(Function))
    expect(navigator.serviceWorker).toBeUndefined()
  })

  it("registers /sw.js on window load when Service Worker is supported", () => {
    const registerMock = vi.fn().mockResolvedValue({ scope: "/" })
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: { register: registerMock },
    })

    registerServiceWorker()
    // Registration must be deferred until the window load event
    expect(registerMock).not.toHaveBeenCalled()

    window.dispatchEvent(new Event("load"))

    expect(registerMock).toHaveBeenCalledTimes(1)
    expect(registerMock).toHaveBeenCalledWith("/sw.js")
    // Successful registration logs the scope (microtask — flush with await)
    return Promise.resolve().then(() => {
      expect(console.log).toHaveBeenCalledWith("[PWA] Service worker registered:", "/")
    })
  })

  it("warns (but does not throw) when registration rejects", async () => {
    const registerMock = vi.fn().mockRejectedValue(new Error("permission denied"))
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: { register: registerMock },
    })

    registerServiceWorker()
    window.dispatchEvent(new Event("load"))

    // catch() is async — flush the microtask queue
    await Promise.resolve()
    await Promise.resolve()

    expect(console.warn).toHaveBeenCalledWith(
      "[PWA] Service worker registration failed:",
      expect.any(Error)
    )
  })
})
