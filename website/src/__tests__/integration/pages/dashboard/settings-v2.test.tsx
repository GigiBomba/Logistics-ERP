import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import SettingsPage from "@/pages/dashboard/settings"
import { useTheme } from "@/contexts/theme-provider"
import { useAuth } from "@/contexts/auth-provider"
import {
  useSessions,
  useCreateTicket,
  useUpdateNotificationPreferences,
  useMfaStatus,
  useMfaEnroll,
  useMfaConfirm,
  useMfaDisable,
} from "@/services/queries"
import { createMockThemeContext, createMockAuthContext } from "@/test-utils"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

vi.mock("@/contexts/theme-provider", () => ({
  useTheme: vi.fn(),
}))

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

vi.mock("@/services/queries", () => ({
  useSessions: vi.fn(),
  useCreateTicket: vi.fn(),
  useUpdateNotificationPreferences: vi.fn(),
  useMfaStatus: vi.fn(),
  useMfaEnroll: vi.fn(),
  useMfaConfirm: vi.fn(),
  useMfaDisable: vi.fn(),
}))

describe("SettingsPage (Enhanced)", () => {
  const mockSetTheme = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useTheme).mockReturnValue(
      createMockThemeContext({ setTheme: mockSetTheme })
    )
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ user: { id: "1", name: "Test", email: "test@test.com", role: "dispatcher", is_admin: false }, isAuthenticated: true })
    )
    vi.mocked(useSessions).mockReturnValue({ data: [], isLoading: false, isError: false } as any)
    vi.mocked(useCreateTicket).mockReturnValue({ mutate: vi.fn(), isPending: false, isError: false } as any)
    vi.mocked(useUpdateNotificationPreferences).mockReturnValue({ mutate: vi.fn(), isPending: false, isError: false } as any)
    vi.mocked(useMfaStatus).mockReturnValue({ data: { mfa_enabled: false }, isLoading: false } as any)
    vi.mocked(useMfaEnroll).mockReturnValue({ mutate: vi.fn(), isPending: false, isError: false, data: undefined } as any)
    vi.mocked(useMfaConfirm).mockReturnValue({ mutate: vi.fn(), isPending: false, isError: false, data: undefined } as any)
    vi.mocked(useMfaDisable).mockReturnValue({ mutate: vi.fn(), isPending: false, isError: false } as any)
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

  it("shows 2FA enroll flow when MFA is disabled", () => {
    vi.mocked(useMfaStatus).mockReturnValue({ data: { mfa_enabled: false }, isLoading: false } as any)
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /security/i }))
    expect(screen.getByText("Two-Factor Authentication")).toBeInTheDocument()
    // Enroll flow is visible (Enable 2FA CTA + description)
    expect(screen.getByText("Enable 2FA")).toBeInTheDocument()
    expect(screen.queryByText("Disable two-factor authentication")).not.toBeInTheDocument()
  })

  it("shows 2FA disable flow when MFA is enabled", () => {
    vi.mocked(useMfaStatus).mockReturnValue({ data: { mfa_enabled: true }, isLoading: false } as any)
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /security/i }))
    expect(screen.getByText("Two-Factor Authentication")).toBeInTheDocument()
    // Disable flow is visible; enroll flow is not
    expect(screen.getByText("Disable two-factor authentication")).toBeInTheDocument()
    expect(screen.queryByText("Enable 2FA")).not.toBeInTheDocument()
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
