import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act, waitFor } from "@testing-library/react"
import { useTheme, ThemeProvider } from "@/contexts/theme-provider"

function renderThemeHook() {
  return renderHook(() => useTheme(), {
    wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>,
  })
}

describe("ThemeProvider", () => {
  const originalMatchMedia = window.matchMedia
  const originalLocalStorage = window.localStorage

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
