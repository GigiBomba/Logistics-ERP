import { describe, it, expect, vi, beforeEach, afterAll } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { useTheme, ThemeProvider } from "@/contexts/theme-provider"

function renderThemeHook() {
  return renderHook(() => useTheme(), {
    wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>,
  })
}

describe("ThemeProvider", () => {
  const originalMatchMedia = window.matchMedia

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    document.documentElement.classList.remove("light", "dark")
  })

  afterAll(() => {
    window.matchMedia = originalMatchMedia
  })

  it("defaults to system theme", () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as any

    const { result } = renderThemeHook()
    expect(result.current.theme).toBe("system")
  })

  it("reads stored light theme", () => {
    localStorage.setItem("operion-theme", "light")
    const { result } = renderThemeHook()
    expect(result.current.theme).toBe("light")
    expect(result.current.resolvedTheme).toBe("light")
  })

  it("reads stored dark theme", () => {
    localStorage.setItem("operion-theme", "dark")
    const { result } = renderThemeHook()
    expect(result.current.theme).toBe("dark")
    expect(result.current.resolvedTheme).toBe("dark")
  })

  it("setTheme updates theme and persists", () => {
    const { result } = renderThemeHook()
    act(() => {
      result.current.setTheme("dark")
    })
    expect(result.current.theme).toBe("dark")
    expect(localStorage.getItem("operion-theme")).toBe("dark")
  })

  it("setTheme to light adds light class to html", () => {
    const { result } = renderThemeHook()
    act(() => {
      result.current.setTheme("light")
    })
    expect(document.documentElement.classList.contains("light")).toBe(true)
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })

  it("setTheme to dark adds dark class to html", () => {
    const { result } = renderThemeHook()
    act(() => {
      result.current.setTheme("dark")
    })
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })

  it("stored theme overrides system preference", () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: true, // system prefers dark
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as any

    localStorage.setItem("operion-theme", "light")
    const { result } = renderThemeHook()
    expect(result.current.theme).toBe("light")
    expect(result.current.resolvedTheme).toBe("light")
  })

  it("useTheme throws outside ThemeProvider", () => {
    expect(() => {
      renderHook(() => useTheme())
    }).toThrow("useTheme must be used within ThemeProvider")
  })
})

describe("ThemeProvider — system theme", () => {
  const originalMatchMedia = window.matchMedia

  /** Controllable matchMedia mock that lets a test fire the change handler. */
  function createMatchMediaMock(initialMatches: boolean) {
    const listeners: Array<(e: { matches: boolean }) => void> = []
    const mql = {
      matches: initialMatches,
      media: "(prefers-color-scheme: dark)",
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((_: string, cb: (e: { matches: boolean }) => void) => {
        listeners.push(cb)
      }),
      removeEventListener: vi.fn((_: string, cb: (e: { matches: boolean }) => void) => {
        const idx = listeners.indexOf(cb)
        if (idx !== -1) listeners.splice(idx, 1)
      }),
      dispatchEvent: vi.fn(),
    }
    return {
      mql,
      emit(matches: boolean) {
        listeners.forEach((cb) => cb({ matches }))
      },
    }
  }

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    document.documentElement.classList.remove("light", "dark")
  })

  afterAll(() => {
    window.matchMedia = originalMatchMedia
  })

  it("resolves system theme to dark when the OS prefers dark", () => {
    const mm = createMatchMediaMock(true)
    window.matchMedia = vi.fn().mockReturnValue(mm.mql) as any

    const { result } = renderThemeHook()
    expect(result.current.theme).toBe("system")
    expect(result.current.resolvedTheme).toBe("dark")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })

  it("listens for system preference changes and updates the class", () => {
    const mm = createMatchMediaMock(true)
    window.matchMedia = vi.fn().mockReturnValue(mm.mql) as any

    const { result } = renderThemeHook()
    expect(result.current.resolvedTheme).toBe("dark")

    act(() => mm.emit(false))
    expect(result.current.resolvedTheme).toBe("light")
    expect(document.documentElement.classList.contains("light")).toBe(true)
    expect(document.documentElement.classList.contains("dark")).toBe(false)

    act(() => mm.emit(true))
    expect(result.current.resolvedTheme).toBe("dark")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })

  it("does not register a change listener when the theme is explicit", () => {
    const mm = createMatchMediaMock(true)
    window.matchMedia = vi.fn().mockReturnValue(mm.mql) as any
    localStorage.setItem("operion-theme", "dark")

    renderThemeHook()
    expect(mm.mql.addEventListener).not.toHaveBeenCalled()
  })

  it("registers a change listener when switching from explicit to system", () => {
    const mm = createMatchMediaMock(false)
    window.matchMedia = vi.fn().mockReturnValue(mm.mql) as any
    localStorage.setItem("operion-theme", "light")

    const { result } = renderThemeHook()
    act(() => result.current.setTheme("system"))
    expect(mm.mql.addEventListener).toHaveBeenCalled()
    expect(result.current.resolvedTheme).toBe("light")
  })

  it("removes the change listener when the provider unmounts", () => {
    const mm = createMatchMediaMock(true)
    window.matchMedia = vi.fn().mockReturnValue(mm.mql) as any

    const { unmount } = renderThemeHook()
    expect(mm.mql.removeEventListener).not.toHaveBeenCalled()
    unmount()
    expect(mm.mql.removeEventListener).toHaveBeenCalled()
  })

  it("switching to an explicit theme stops following the system preference", () => {
    const mm = createMatchMediaMock(true)
    window.matchMedia = vi.fn().mockReturnValue(mm.mql) as any

    const { result } = renderThemeHook()
    act(() => result.current.setTheme("light"))
    // The system emits a dark change but the explicit light theme wins.
    act(() => mm.emit(true))
    expect(result.current.theme).toBe("light")
    expect(result.current.resolvedTheme).toBe("light")
    expect(document.documentElement.classList.contains("light")).toBe(true)
  })
})
