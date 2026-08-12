import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
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
import { toast } from "sonner"

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

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const makeMutation = (overrides: Record<string, any> = {}) => ({
  mutate: vi.fn(),
  isPending: false,
  isError: false,
  error: null,
  data: undefined,
  ...overrides,
})

describe("SettingsPage — interactions", () => {
  const mockSetTheme = vi.fn()

  // Capture pristine globals so per-test stubs (clipboard, URL) can be restored.
  // The fake `localStorage` in src/__tests__/setup.ts keeps a module-level store that
  // is never cleared between tests — clear it explicitly so LocaleProvider's
  // `operion-locale` read can never leak state across tests.
  const originalURL = globalThis.URL

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    vi.mocked(useTheme).mockReturnValue(createMockThemeContext({ setTheme: mockSetTheme }))
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({
        user: { id: "1", name: "Test", email: "test@test.com", role: "dispatcher", is_admin: false },
        isAuthenticated: true,
      })
    )
    vi.mocked(useSessions).mockReturnValue({ data: [], isLoading: false, isError: false } as any)
    vi.mocked(useCreateTicket).mockReturnValue(makeMutation() as any)
    vi.mocked(useUpdateNotificationPreferences).mockReturnValue(makeMutation() as any)
    vi.mocked(useMfaStatus).mockReturnValue({ data: { mfa_enabled: false }, isLoading: false } as any)
    vi.mocked(useMfaEnroll).mockReturnValue(makeMutation() as any)
    vi.mocked(useMfaConfirm).mockReturnValue(makeMutation() as any)
    vi.mocked(useMfaDisable).mockReturnValue(makeMutation() as any)
  })

  afterEach(() => {
    // Undo per-test globals so nothing leaks into later tests in this file:
    // navigator.clipboard (Object.defineProperty) and the URL stub (vi.stubGlobal).
    // The settings page schedules real timers (100ms MFA auto-advance, 2000ms copy
    // indicator) — returning to real timers + RTL auto-cleanup keeps them inert.
    delete (navigator as { clipboard?: unknown }).clipboard
    vi.stubGlobal("URL", originalURL)
    vi.useRealTimers()
    localStorage.clear()
  })

  describe("appearance", () => {
    it("switches theme when clicking a theme button", () => {
      render(<SettingsPage />)
      fireEvent.click(screen.getByText("dark"))
      expect(mockSetTheme).toHaveBeenCalledWith("dark")
    })
  })

  describe("notification preferences", () => {
    it("saves notification preferences with toggled values", () => {
      const mutate = vi.fn((_args, opts: any) => opts?.onSuccess?.())
      vi.mocked(useUpdateNotificationPreferences).mockReturnValue(makeMutation({ mutate }) as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /notifications/i }))
      // marketing emails starts false -> toggle on
      const marketing = screen.getByLabelText(/Marketing Emails/i)
      fireEvent.click(marketing)
      fireEvent.click(screen.getByRole("button", { name: /save preferences/i }))
      expect(mutate).toHaveBeenCalledWith(
        expect.objectContaining({ marketing_emails: true, email_notifications: true }),
        expect.anything()
      )
      expect(toast.success).toHaveBeenCalledWith("Preferences saved successfully")
    })

    it("toasts an error when saving preferences fails", () => {
      const mutate = vi.fn((_args, opts: any) => opts?.onError?.())
      vi.mocked(useUpdateNotificationPreferences).mockReturnValue(makeMutation({ mutate }) as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /notifications/i }))
      fireEvent.click(screen.getByRole("button", { name: /save preferences/i }))
      expect(toast.error).toHaveBeenCalledWith("Failed to save preferences")
    })
  })

  describe("language & region", () => {
    it("changes language, region and timezone selects", () => {
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /language & region/i }))
      const language = screen.getByRole("combobox", { name: /language/i })
      fireEvent.change(language, { target: { value: "de" } })
      expect((language as HTMLSelectElement).value).toBe("de")

      const region = screen.getByRole("combobox", { name: /country \/ region/i })
      fireEvent.change(region, { target: { value: "US" } })
      expect((region as HTMLSelectElement).value).toBe("US")

      const tz = screen.getByRole("combobox", { name: /^timezone$/i })
      fireEvent.change(tz, { target: { value: "UTC" } })
      expect((tz as HTMLSelectElement).value).toBe("UTC")
    })
  })

  describe("MFA enroll flow (disabled)", () => {
    it("enrolls, confirms with a code, and reaches done with backup codes", async () => {
      const enrollMutate = vi.fn((_args, opts: any) => opts?.onSuccess?.())
      const confirmMutate = vi.fn((_code: string, opts: any) => opts?.onSuccess?.())
      vi.mocked(useMfaEnroll).mockReturnValue(
        makeMutation({
          mutate: enrollMutate,
          data: { secret: "SECRETKEY", otpauth_uri: "otpauth://totp/Test", backup_codes: ["111111", "222222"] },
        }) as any
      )
      vi.mocked(useMfaConfirm).mockReturnValue(
        makeMutation({ mutate: confirmMutate, data: { backup_codes: ["111111", "222222"] } }) as any
      )
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText: vi.fn().mockResolvedValue(undefined) },
      })
      vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:test"), revokeObjectURL: vi.fn() })

      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))

      fireEvent.click(screen.getByRole("button", { name: /enable 2fa/i }))
      expect(enrollMutate).toHaveBeenCalledWith(undefined, expect.anything())
      expect(toast.success).toHaveBeenCalledWith(
        "Scan the QR code or enter the key manually, then type the 6-digit code."
      )

      // confirming phase shows QR, secret and otpauth URI
      expect(screen.getByText("Set up your authenticator app")).toBeInTheDocument()
      expect(screen.getByText("SECRETKEY")).toBeInTheDocument()
      expect(screen.getByText("otpauth://totp/Test")).toBeInTheDocument()

      // copy the secret key
      fireEvent.click(screen.getByRole("button", { name: /copy setup key/i }))
      await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith("SECRETKEY"), { timeout: 5000 })

      // enter a 6-digit code, then click verify to confirm
      const codeInput = screen.getByLabelText(/6-digit verification code/i)
      fireEvent.change(codeInput, { target: { value: "123456" } })
      fireEvent.click(screen.getByRole("button", { name: /enable two-factor authentication/i }))
      await waitFor(() => expect(confirmMutate).toHaveBeenCalledWith("123456", expect.anything()), { timeout: 5000 })
      await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Two-factor authentication enabled."), { timeout: 5000 })

      // done phase shows backup codes and download button
      await waitFor(() => expect(screen.getByText("Backup codes")).toBeInTheDocument(), { timeout: 5000 })
      expect(screen.getByText("111111")).toBeInTheDocument()
      expect(screen.getByText("222222")).toBeInTheDocument()

      fireEvent.click(screen.getByRole("button", { name: /download as .txt/i }))
      expect(URL.createObjectURL).toHaveBeenCalled()

      // done button is disabled until the checkbox is checked
      const doneBtn = screen.getByRole("button", { name: /^done$/i })
      expect(doneBtn).toBeDisabled()
      fireEvent.click(screen.getByLabelText(/I've saved these codes/i))
      expect(doneBtn).toBeEnabled()
    })

    it("keeps the verify button disabled until all 6 digits are entered", async () => {
      vi.mocked(useMfaEnroll).mockReturnValue(
        makeMutation({
          mutate: vi.fn((_args, opts: any) => opts?.onSuccess?.()),
          data: { secret: "SECRETKEY", otpauth_uri: "otpauth://totp/Test" },
        }) as any
      )
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      fireEvent.click(screen.getByRole("button", { name: /enable 2fa/i }))

      const verify = screen.getByRole("button", { name: /enable two-factor authentication/i })
      fireEvent.change(screen.getByLabelText(/6-digit verification code/i), { target: { value: "123" } })
      expect(verify).toBeDisabled()
    })

    it("shows an enrollment error callout when enroll mutation fails", () => {
      vi.mocked(useMfaEnroll).mockReturnValue(
        makeMutation({ isError: true, error: { message: "enroll boom" } }) as any
      )
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      expect(screen.getByText("Enrollment failed")).toBeInTheDocument()
      expect(screen.getByText("enroll boom")).toBeInTheDocument()
    })

    it("toasts on enroll error", () => {
      const enrollMutate = vi.fn((_args, opts: any) => opts?.onError?.({}))
      vi.mocked(useMfaEnroll).mockReturnValue(makeMutation({ mutate: enrollMutate }) as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      fireEvent.click(screen.getByRole("button", { name: /enable 2fa/i }))
      expect(toast.error).toHaveBeenCalledWith("Failed to start MFA enrollment.")
    })

    it("toasts a copy failure when clipboard is unavailable", async () => {
      const enrollMutate = vi.fn((_args, opts: any) => opts?.onSuccess?.())
      vi.mocked(useMfaEnroll).mockReturnValue(
        makeMutation({
          mutate: enrollMutate,
          data: { secret: "SECRETKEY", otpauth_uri: "otpauth://totp/Test" },
        }) as any
      )
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: {
          writeText: vi.fn().mockRejectedValue(new Error("denied")),
        },
      })
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      fireEvent.click(screen.getByRole("button", { name: /enable 2fa/i }))
      fireEvent.click(screen.getByRole("button", { name: /copy setup key/i }))
      await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Unable to copy. Please select and copy manually."), { timeout: 5000 })
    })

    it("shows a confirm error callout", () => {
      vi.mocked(useMfaEnroll).mockReturnValue(
        makeMutation({
          mutate: vi.fn((_args, opts: any) => opts?.onSuccess?.()),
          data: { secret: "S", otpauth_uri: "otpauth://totp/Test" },
        }) as any
      )
      vi.mocked(useMfaConfirm).mockReturnValue(
        makeMutation({ isError: true, error: { message: "bad code" } }) as any
      )
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      fireEvent.click(screen.getByRole("button", { name: /enable 2fa/i }))
      expect(screen.getByText("Invalid code")).toBeInTheDocument()
      expect(screen.getByText("bad code")).toBeInTheDocument()
    })

    it("renders MFA status skeleton while loading", () => {
      vi.mocked(useMfaStatus).mockReturnValue({ data: undefined, isLoading: true } as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      expect(screen.getByText("Two-Factor Authentication")).toBeInTheDocument()
    })
  })

  describe("MFA disable flow (enabled)", () => {
    const enabledMfa = () =>
      vi.mocked(useMfaStatus).mockReturnValue({ data: { mfa_enabled: true }, isLoading: false } as any)

    it("disables 2FA with the current password", () => {
      const disableMutate = vi.fn((_args, opts: any) => opts?.onSuccess?.())
      enabledMfa()
      vi.mocked(useMfaDisable).mockReturnValue(makeMutation({ mutate: disableMutate }) as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))

      expect(screen.getByText("Two-factor authentication is enabled")).toBeInTheDocument()
      fireEvent.click(screen.getByRole("button", { name: /disable two-factor authentication/i }))

      fireEvent.change(screen.getByPlaceholderText("Current password"), { target: { value: "pw" } })
      fireEvent.click(screen.getByRole("button", { name: /disable 2fa/i }))
      expect(disableMutate).toHaveBeenCalledWith("pw", expect.anything())
      expect(toast.success).toHaveBeenCalledWith("Two-factor authentication disabled.")
    })

    it("requires a password before disabling", () => {
      enabledMfa()
      vi.mocked(useMfaDisable).mockReturnValue(makeMutation() as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      fireEvent.click(screen.getByRole("button", { name: /disable two-factor authentication/i }))
      fireEvent.click(screen.getByRole("button", { name: /disable 2fa/i }))
      expect(toast.error).toHaveBeenCalledWith("Enter your password to disable 2FA.")
    })

    it("toggles password visibility", () => {
      enabledMfa()
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      fireEvent.click(screen.getByRole("button", { name: /disable two-factor authentication/i }))
      const input = screen.getByPlaceholderText("Current password") as HTMLInputElement
      expect(input.type).toBe("password")
      fireEvent.click(screen.getByRole("button", { name: /show password/i }))
      expect(input.type).toBe("text")
      fireEvent.click(screen.getByRole("button", { name: /hide password/i }))
      expect(input.type).toBe("password")
    })

    it("cancels the disable flow", () => {
      enabledMfa()
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      fireEvent.click(screen.getByRole("button", { name: /disable two-factor authentication/i }))
      fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }))
      // back to the disable trigger button
      expect(screen.getByRole("button", { name: /disable two-factor authentication/i })).toBeInTheDocument()
    })

    it("shows a disable error callout and toast", () => {
      const disableMutate = vi.fn((_args, opts: any) => opts?.onError?.({}))
      enabledMfa()
      vi.mocked(useMfaDisable).mockReturnValue(makeMutation({ mutate: disableMutate, isError: true, error: { message: "pw wrong" } }) as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      fireEvent.click(screen.getByRole("button", { name: /disable two-factor authentication/i }))
      fireEvent.change(screen.getByPlaceholderText("Current password"), { target: { value: "pw" } })
      fireEvent.click(screen.getByRole("button", { name: /disable 2fa/i }))
      expect(toast.error).toHaveBeenCalledWith("Failed to disable 2FA. Check your password.")
      expect(screen.getByText("pw wrong")).toBeInTheDocument()
    })
  })

  describe("connected sessions", () => {
    it("shows a loading skeleton", () => {
      vi.mocked(useSessions).mockReturnValue({ data: [], isLoading: true, isError: false } as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      expect(screen.getByText("Connected Sessions")).toBeInTheDocument()
    })

    it("shows a load error callout", () => {
      vi.mocked(useSessions).mockReturnValue({ data: [], isLoading: false, isError: true } as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      expect(screen.getByText("Could not load sessions")).toBeInTheDocument()
    })

    it("renders a session summary with current session details", () => {
      vi.mocked(useSessions).mockReturnValue({
        data: [
          { id: 1, device_name: "Chrome on Windows", device_platform: "Windows", ip_address: "1.2.3.4", last_active_at: "2026-07-01T00:00:00Z" },
        ],
        isLoading: false,
        isError: false,
      } as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      expect(screen.getByText("1 active session(s)")).toBeInTheDocument()
      expect(screen.getByText("Current Session")).toBeInTheDocument()
      expect(screen.getByText("Chrome on Windows")).toBeInTheDocument()
      expect(screen.getByText("1.2.3.4")).toBeInTheDocument()
    })

    it("falls back to platform name for unknown device", () => {
      vi.mocked(useSessions).mockReturnValue({
        data: [
          { id: 1, device_name: null, device_platform: "iPhone", ip_address: null, last_active_at: null },
        ],
        isLoading: false,
        isError: false,
      } as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /security/i }))
      expect(screen.getByText("iPhone")).toBeInTheDocument()
    })
  })

  describe("data & privacy", () => {
    it("submits a data export request via support ticket", () => {
      const mutate = vi.fn((_args, opts: any) => opts?.onSuccess?.())
      vi.mocked(useCreateTicket).mockReturnValue(makeMutation({ mutate }) as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /data & privacy/i }))
      fireEvent.click(screen.getByRole("button", { name: /request via support/i }))
      expect(mutate).toHaveBeenCalledWith(
        expect.objectContaining({ subject: "Data Export Request", priority: "low" }),
        expect.anything()
      )
      expect(toast.success).toHaveBeenCalledWith(
        "Your request has been submitted. We'll process it shortly."
      )
    })

    it("toasts an error when the export request fails", () => {
      const mutate = vi.fn((_args, opts: any) => opts?.onError?.())
      vi.mocked(useCreateTicket).mockReturnValue(makeMutation({ mutate }) as any)
      render(<SettingsPage />)
      fireEvent.click(screen.getByRole("tab", { name: /data & privacy/i }))
      fireEvent.click(screen.getByRole("button", { name: /request via support/i }))
      expect(toast.error).toHaveBeenCalledWith(
        "Failed to submit your request. Please try again or contact support directly."
      )
    })
  })
})
