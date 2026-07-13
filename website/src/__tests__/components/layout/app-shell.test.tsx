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

vi.mock("@/i18n/locale-context", () => ({
  useLocale: vi.fn(() => ({
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
      }
      return defaults[key] || key
    },
  })),
}))

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
    const toggleBtn = screen.getByLabelText(/toggle theme/i)
    expect(toggleBtn).toBeInTheDocument()
  })

  it("renders footer sections", () => {
    vi.mocked(useAuth).mockReturnValue(mockUnauthenticated)
    render(<AppShell />)
    expect(screen.getByText("Product")).toBeInTheDocument()
    expect(screen.getByText("Resources")).toBeInTheDocument()
  })
})
