import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import SettingsPage from "@/pages/dashboard/settings"
import { useTheme } from "@/contexts/theme-provider"
import { createMockThemeContext } from "@/test-utils"

vi.mock("@/contexts/theme-provider", () => ({
  useTheme: vi.fn(),
}))

describe("SettingsPage", () => {
  const mockSetTheme = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useTheme).mockReturnValue(
      createMockThemeContext({ setTheme: mockSetTheme })
    )
  })

  it("renders settings page heading", () => {
    render(<SettingsPage />)
    expect(screen.getByText("Settings")).toBeInTheDocument()
    expect(screen.getAllByText("Appearance").length).toBeGreaterThanOrEqual(1)
  })

  it("renders theme toggle buttons", () => {
    render(<SettingsPage />)
    expect(screen.getByText("light")).toBeInTheDocument()
    expect(screen.getByText("dark")).toBeInTheDocument()
    expect(screen.getByText("system")).toBeInTheDocument()
  })

  it("calls setTheme when clicking theme button", () => {
    render(<SettingsPage />)
    screen.getByText("dark").click()
    expect(mockSetTheme).toHaveBeenCalledWith("dark")
  })

  it("shows change password link", () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /security/i }))
    expect(screen.getByRole("link", { name: /change password/i })).toHaveAttribute("href", "/dashboard/profile")
  })
})
