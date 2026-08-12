import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { AppShell } from "@/components/layout/app-shell"
import { useAuth } from "@/contexts/auth-provider"
import { useTheme } from "@/contexts/theme-provider"
import { createMockAuthUser, createMockAuthContext, createMockThemeContext } from "@/test-utils"

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

vi.mock("@/contexts/theme-provider", () => ({
  useTheme: vi.fn(),
}))

vi.mock("@/i18n/locale-context", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/locale-context")>("@/i18n/locale-context")
  return {
    ...actual,
    useLocale: () => ({
      locale: "en" as const,
      setLocale: vi.fn(),
      t: (key: string) => {
        const defaults: Record<string, string> = {
          "nav.features": "Features",
          "nav.pricing": "Pricing",
          "footer.product": "Product",
          "footer.resources": "Resources",
          "footer.privacy": "Privacy",
          "footer.terms": "Terms",
          "footer.tagline": "Enterprise logistics management platform.",
          "common.search": "Search...",
          "common.toggleTheme": "Toggle theme",
          "common.dashboard": "Dashboard",
        }
        return defaults[key] || key
      },
    }),
  }
})

const mockTheme = createMockThemeContext()

const mockUnauthenticated = createMockAuthContext()

const mockAuthenticated = createMockAuthContext({
  isAuthenticated: true,
  user: createMockAuthUser(),
})

describe("AppShell", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useTheme).mockReturnValue(mockTheme)
  })

  it("renders logo with brand name", () => {
    vi.mocked(useAuth).mockReturnValue(mockUnauthenticated)
    render(<AppShell />)
    const operionTexts = screen.getAllByText("Operion")
    expect(operionTexts.length).toBeGreaterThanOrEqual(1)
  })

  it("renders nav items in the header", () => {
    vi.mocked(useAuth).mockReturnValue(mockUnauthenticated)
    render(<AppShell />)
    // Nav items appear in both header and footer — just verify at least once
    expect(screen.getAllByText("Features").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Pricing").length).toBeGreaterThanOrEqual(1)
  })

  it("renders the footer with legal links", () => {
    vi.mocked(useAuth).mockReturnValue(mockUnauthenticated)
    render(<AppShell />)
    const privacyLinks = screen.getAllByText("Privacy")
    expect(privacyLinks.length).toBeGreaterThanOrEqual(1)
    const termsLinks = screen.getAllByText("Terms")
    expect(termsLinks.length).toBeGreaterThanOrEqual(1)
  })

  it("renders theme toggle button", () => {
    vi.mocked(useAuth).mockReturnValue(mockUnauthenticated)
    render(<AppShell />)
    // Desktop and mobile headers each have a labeled theme toggle.
    const toggleBtns = screen.getAllByLabelText(/toggle theme/i)
    expect(toggleBtns.length).toBeGreaterThanOrEqual(1)
  })

  it("renders footer sections", () => {
    vi.mocked(useAuth).mockReturnValue(mockUnauthenticated)
    render(<AppShell />)
    expect(screen.getByText("Product")).toBeInTheDocument()
    expect(screen.getByText("Resources")).toBeInTheDocument()
  })

  describe("public header avatar", () => {
    it("shows avatar in public header when authenticated", () => {
      vi.mocked(useAuth).mockReturnValue(mockAuthenticated)
      render(<AppShell />)
      // The avatar contains the user initials as fallback
      const avatarElement = screen.getByText("TU") // "Test User" → "TU"
      expect(avatarElement).toBeInTheDocument()
    })

    it("shows initials fallback when authenticated user has no avatar_url", () => {
      vi.mocked(useAuth).mockReturnValue(mockAuthenticated)
      render(<AppShell />)
      const fallback = screen.getByText("TU")
      expect(fallback).toBeInTheDocument()
      expect(fallback.className).toContain("text-xs")
    })

    it("avatar links to dashboard", () => {
      vi.mocked(useAuth).mockReturnValue(mockAuthenticated)
      render(<AppShell />)
      const avatarLink = screen.getByLabelText("Dashboard").closest("a")
      expect(avatarLink).toHaveAttribute("href", "/dashboard")
    })

    it("does not show avatar when not authenticated", () => {
      vi.mocked(useAuth).mockReturnValue(mockUnauthenticated)
      render(<AppShell />)
      expect(screen.queryByLabelText("Dashboard")).not.toBeInTheDocument()
    })
  })
})
