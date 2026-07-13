import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import SettingsPage from "@/pages/dashboard/settings"
import { useTheme } from "@/contexts/theme-provider"
import { createMockThemeContext } from "@/test-utils"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

vi.mock("@/contexts/theme-provider", () => ({
  useTheme: vi.fn(),
}))

describe("SettingsPage (Enhanced)", () => {
  const mockSetTheme = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useTheme).mockReturnValue(
      createMockThemeContext({ setTheme: mockSetTheme })
    )
  })

  it("shows tabs (Appearance / Notifications / Language / Security / Data)", () => {
    render(<SettingsPage />)
    expect(screen.getByRole("tab", { name: /appearance/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /notifications/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /language/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /security/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /data/i })).toBeInTheDocument()
  })

  it("shows theme toggles (light / dark / system)", () => {
    render(<SettingsPage />)
    expect(screen.getByText("light")).toBeInTheDocument()
    expect(screen.getByText("dark")).toBeInTheDocument()
    expect(screen.getByText("system")).toBeInTheDocument()
  })

  it("shows notification preferences with checkboxes", () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /notifications/i }))
    expect(screen.getByText("Email Notifications")).toBeInTheDocument()
    expect(screen.getByText("Product Updates")).toBeInTheDocument()
    expect(screen.getByText("Security Alerts")).toBeInTheDocument()
    expect(screen.getByText("Marketing Emails")).toBeInTheDocument()
  })

  it("shows language selectors", () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /language/i }))
    // "Language", "Region", "Timezone" appear as both card headings and form labels
    expect(screen.getAllByText("Language").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Region").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Timezone").length).toBeGreaterThanOrEqual(1)
    // Language select element is present
    expect(screen.getByRole("combobox", { name: /language/i })).toBeInTheDocument()
  })

  it("shows region selector with country options", () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /language/i }))
    expect(screen.getByText("Romania")).toBeInTheDocument()
    expect(screen.getByText("United Kingdom")).toBeInTheDocument()
    expect(screen.getByText("Germany")).toBeInTheDocument()
    expect(screen.getByText("United States")).toBeInTheDocument()
  })

  it("shows timezone selector", () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /language/i }))
    // "Timezone" appears as both the card heading and the form label
    expect(screen.getAllByText("Timezone").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("UTC")).toBeInTheDocument()
    expect(screen.getByText("Europe/Bucharest (EET)")).toBeInTheDocument()
  })

  it("shows security section with 2FA placeholder", () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /security/i }))
    expect(screen.getByText("Two-Factor Authentication")).toBeInTheDocument()
    expect(screen.getByText("Enable 2FA")).toBeInTheDocument()
    expect(screen.getByText(/Coming Soon/i)).toBeInTheDocument()
  })

  it("shows API keys placeholder", () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /data/i }))
    expect(screen.getByText("API Keys")).toBeInTheDocument()
    expect(screen.getByText("Create API Key")).toBeInTheDocument()
  })

  it("shows password section in Security tab", () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /security/i }))
    expect(screen.getByText("Password")).toBeInTheDocument()
    expect(screen.getByText("Change Password")).toBeInTheDocument()
  })

  it("shows data export section in Data & Privacy tab", () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /data/i }))
    expect(screen.getByText("Data Export")).toBeInTheDocument()
    expect(screen.getByText("Request Data Export")).toBeInTheDocument()
  })

  it("shows delete account section with danger callout", () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /data/i }))
    // "Delete Account" appears as both the card title and the button text
    expect(screen.getAllByText("Delete Account").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/This action is irreversible/i)).toBeInTheDocument()
  })

  it("shows save preferences button in notifications tab", () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /notifications/i }))
    expect(screen.getByText("Save Preferences")).toBeInTheDocument()
  })
})
