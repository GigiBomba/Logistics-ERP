import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, renderHook, act } from "@/test-utils"
import { SkipToContent, useReducedMotion } from "@/services/accessibility"

describe("SkipToContent", () => {
  it("renders a skip link pointing at the default content id", () => {
    render(<SkipToContent />)
    const link = screen.getByText("Skip to content")
    expect(link.tagName).toBe("A")
    expect(link).toHaveAttribute("href", "#main-content")
  })

  it("uses a custom content id when provided", () => {
    render(<SkipToContent contentId="page-content" />)
    expect(screen.getByText("Skip to content")).toHaveAttribute("href", "#page-content")
  })
})

describe("useReducedMotion", () => {
  const originalMatchMedia = window.matchMedia

  function makeMatchMedia(matches: boolean) {
    const listeners: Array<(e: { matches: boolean }) => void> = []
    return {
      mql: {
        matches,
        media: "(prefers-reduced-motion: reduce)",
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn((_: string, cb: (e: { matches: boolean }) => void) => {
          listeners.push(cb)
        }),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      },
      emit(m: boolean) {
        listeners.forEach((cb) => cb({ matches: m }))
      },
    }
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    window.matchMedia = originalMatchMedia
  })

  it("returns false when the OS does not prefer reduced motion", () => {
    window.matchMedia = vi.fn().mockReturnValue(makeMatchMedia(false).mql) as any
    const { result } = renderHook(() => useReducedMotion())
    expect(result.current).toBe(false)
  })

  it("returns true when the OS prefers reduced motion", () => {
    window.matchMedia = vi.fn().mockReturnValue(makeMatchMedia(true).mql) as any
    const { result } = renderHook(() => useReducedMotion())
    expect(result.current).toBe(true)
  })

  it("updates when the system preference changes", () => {
    const mm = makeMatchMedia(false)
    window.matchMedia = vi.fn().mockReturnValue(mm.mql) as any
    const { result } = renderHook(() => useReducedMotion())
    expect(result.current).toBe(false)

    act(() => mm.emit(true))
    expect(result.current).toBe(true)
  })
})
