import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, act, renderHook } from "@testing-library/react"
import { SkipToContent, useReducedMotion } from "@/services/accessibility"

// ─── SkipToContent ────────────────────────────────────────────

describe("SkipToContent", () => {
  it("renders a skip link with default href", () => {
    render(<SkipToContent />)
    const link = screen.getByRole("link", { name: /skip to content/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "#main-content")
  })

  it("uses custom contentId when provided", () => {
    render(<SkipToContent contentId="custom-area" />)
    const link = screen.getByRole("link", { name: /skip to content/i })
    expect(link).toHaveAttribute("href", "#custom-area")
  })

  it("has sr-only class by default (hidden when not focused)", () => {
    render(<SkipToContent />)
    const link = screen.getByRole("link", { name: /skip to content/i })
    // sr-only is present when not focused
    expect(link.className).toContain("sr-only")
  })

  it("has focus-visible classes that would make it visible on focus", () => {
    render(<SkipToContent />)
    const link = screen.getByRole("link", { name: /skip to content/i })
    // The className includes both sr-only (default hidden) and focus:not-sr-only (visible on focus)
    expect(link.className).toContain("focus:not-sr-only")
    expect(link.className).toContain("focus:fixed")
    expect(link.className).toContain("focus:left-4")
    expect(link.className).toContain("focus:top-4")
    expect(link.className).toContain("focus:z-[9999]")
  })

  it("renders a down-arrow icon", () => {
    render(<SkipToContent />)
    const link = screen.getByRole("link", { name: /skip to content/i })
    expect(link.innerHTML).toContain("↓")
  })
})

// ─── useReducedMotion ─────────────────────────────────────────

describe("useReducedMotion", () => {
  type MockMqListener = (event: { matches: boolean }) => void
  let addEventListenerSpy: ReturnType<typeof vi.fn>
  let removeEventListenerSpy: ReturnType<typeof vi.fn>
  let listeners: MockMqListener[]

  beforeEach(() => {
    listeners = []
    addEventListenerSpy = vi.fn((_event: string, handler: MockMqListener) => {
      listeners.push(handler)
    })
    removeEventListenerSpy = vi.fn((_event: string, handler: MockMqListener) => {
      const idx = listeners.indexOf(handler)
      if (idx !== -1) listeners.splice(idx, 1)
    })

    // Reset matchMedia before each test
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: addEventListenerSpy,
      removeEventListener: removeEventListenerSpy,
      dispatchEvent: vi.fn(),
    }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("returns false when media query does not match", () => {
    ;(window.matchMedia as ReturnType<typeof vi.fn>).mockReturnValue({
      matches: false,
      media: "(prefers-reduced-motion: reduce)",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })

    const { result } = renderHook(() => useReducedMotion())
    expect(result.current).toBe(false)
  })

  it("returns true when media query matches reduce", () => {
    ;(window.matchMedia as ReturnType<typeof vi.fn>).mockReturnValue({
      matches: true,
      media: "(prefers-reduced-motion: reduce)",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })

    const { result } = renderHook(() => useReducedMotion())
    expect(result.current).toBe(true)
  })

  it("updates value when the media query changes", () => {
    let currentHandler: MockMqListener | null = null

    window.matchMedia = vi.fn().mockImplementation(() => ({
      matches: false,
      media: "(prefers-reduced-motion: reduce)",
      addEventListener: vi.fn((_event: string, handler: MockMqListener) => {
        currentHandler = handler
      }),
      removeEventListener: vi.fn(),
    }))

    const { result } = renderHook(() => useReducedMotion())
    expect(result.current).toBe(false)

    // Simulate OS setting change to reduced motion
    act(() => {
      currentHandler!({ matches: true })
    })
    expect(result.current).toBe(true)

    // Simulate OS setting change back
    act(() => {
      currentHandler!({ matches: false })
    })
    expect(result.current).toBe(false)
  })

  it("passes the correct media query string", () => {
    renderHook(() => useReducedMotion())
    expect(window.matchMedia).toHaveBeenCalledWith("(prefers-reduced-motion: reduce)")
  })

  it("registers a change event listener", () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: addEventListenerSpy,
      removeEventListener: vi.fn(),
    }))

    renderHook(() => useReducedMotion())
    expect(addEventListenerSpy).toHaveBeenCalledWith("change", expect.any(Function))
  })

  it("cleans up event listener on unmount", () => {
    const removeSpy = vi.fn()
    window.matchMedia = vi.fn().mockImplementation(() => ({
      matches: false,
      media: "(prefers-reduced-motion: reduce)",
      addEventListener: vi.fn(),
      removeEventListener: removeSpy,
    }))

    const { unmount } = renderHook(() => useReducedMotion())
    unmount()
    expect(removeSpy).toHaveBeenCalledWith("change", expect.any(Function))
  })

  // SSR test is skipped because renderHook requires window (React 19 creates
  // a real DOM container). The hook itself guards with `typeof window === "undefined"`.
  it.skip("returns false when window is undefined (SSR)", () => {
    const originalWindow = globalThis.window
    // @ts-expect-error - simulating SSR by deleting window
    delete (globalThis as any).window
    try {
      const { result } = renderHook(() => useReducedMotion())
      expect(result.current).toBe(false)
    } finally {
      ;(globalThis as any).window = originalWindow
    }
  })
})
