import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import ProfilePage from "@/pages/dashboard/profile"
import { useAuth } from "@/contexts/auth-provider"
import { useProfile, useUpdateProfile, useChangePassword } from "@/services/queries"
import { createMockAuthUser, createMockAuthContext } from "@/test-utils"

vi.mock("@/services/queries", () => ({
  useProfile: vi.fn(),
  useUpdateProfile: vi.fn(),
  useChangePassword: vi.fn(),
  useSessions: vi.fn(() => ({ data: [], isLoading: false })),
  useRevokeSession: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useAvatarUpload: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useUpdateNotificationPreferences: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

vi.mock("@/contexts/theme-provider", () => ({
  useTheme: vi.fn(() => ({ theme: "light" as const, setTheme: vi.fn(), resolvedTheme: "light" as const })),
}))

vi.mock("@/i18n/locale-context", () => ({
  LocaleProvider: ({ children }: any) => <>{children}</>,
  useLocale: vi.fn(() => ({
    locale: "en" as const,
    setLocale: vi.fn(),
    t: (key: string) => {
      const defaults: Record<string, string> = {
        "profile.title": "Profile",
        "profile.description": "Manage your personal information",
        "profile.general": "General",
        "profile.security": "Security",
        "profile.notifications": "Notifications",
        "profile.sessions": "Sessions",
        "profile.information": "Profile Information",
        "profile.avatar": "Avatar",
        "profile.avatarDesc": "Your profile picture across Operion.",
        "profile.timezone": "Timezone",
        "profile.language": "Language",
        "profile.theme": "Theme",
        "profile.changePassword": "Change Password",
        "profile.informationDesc": "Update your name and email address.",
        "profile.timezoneDesc": "Set your local timezone",
        "profile.languageDesc": "Choose your preferred language",
        "profile.changePasswordDesc": "Update your account password.",
        "profile.currentPassword": "Current Password",
        "profile.changing": "Changing...",
        "profile.saving": "Saving...",
        "profile.saveChanges": "Save Changes",
        "profile.preferences": "Preferences",
        "profile.preferencesDesc": "Manage your notification preferences",
        "profile.preferencesPlaceholder": "Additional settings coming soon",
        "profile.uploadAvatar": "Upload Picture",
        "profile.changePhoto": "Change Photo",
        "profile.savePhoto": "Save Photo",
        "profile.uploadHint": "PNG, JPG or WebP. Max 2 MB.",
        "profile.photoSaved": "Avatar updated successfully!",
        "common.comingSoon": "Coming soon",
        "common.current": "Current",
        "common.cancel": "Cancel",
        "auth.fullName": "Full Name",
        "auth.email": "Email",
        "auth.newPassword": "New Password",
        "auth.confirmNewPassword": "Confirm New Password",
        "language.en": "English",
        "language.ro": "Romanian",
        "language.de": "German",
        "language.fr": "French",
        "language.es": "Spanish",
        "language.pl": "Polish",
        "profile.moreLanguages": "More languages coming soon",
        "profile.themeDesc": "Choose your preferred appearance",
        "profile.twoFactor": "Two-Factor Authentication",
        "profile.twoFactorDesc": "Add extra security",
        "profile.twoFactorComingSoon": "2FA will be available in a future update.",
        "profile.enable2FA": "Enable 2FA",
        "profile.accountSecurity": "Account Security",
        "profile.accountSecurityDesc": "Review account security",
        "profile.password": "Password",
        "profile.lastChanged": "Last changed",
        "profile.secure": "Secure",
        "profile.notEnabled": "Not enabled",
        "profile.disabled": "Disabled",
        "profile.sessionsCount": "3 sessions",
        "profile.normal": "Normal",
        "profile.notificationPreferences": "Notification Preferences",
        "profile.notificationPrefsDesc": "Choose notifications",
        "profile.emailNotifications": "Email Notifications",
        "profile.emailNotificationsDesc": "Email updates",
        "profile.productUpdates": "Product Updates",
        "profile.productUpdatesDesc": "New features",
        "profile.securityAlerts": "Security Alerts",
        "profile.securityAlertsDesc": "Security alerts",
        "profile.marketingEmails": "Marketing Emails",
        "profile.marketingEmailsDesc": "Marketing updates",
        "profile.blogDigest": "Blog Digest",
        "profile.blogDigestDesc": "Weekly blog summary",
        "profile.savePreferences": "Save Preferences",
        "profile.savePrefsPlaceholder": "Saving coming soon",
        "profile.activeSessions": "Active Sessions",
        "profile.activeSessionsDesc": "Manage sessions",
        "profile.lastActive": "Last active",
        "profile.connectedDevices": "Connected Devices",
        "profile.connectedDevicesDesc": "Authorized devices",
        "profile.noConnectedDevices": "No connected devices",
        "profile.noConnectedDevicesDesc": "Device management coming soon",
        "Shield": "Shield",
        "Smartphone": "Smartphone",
        "Monitor": "Monitor",
        "LogOut": "Log Out",
        "Fingerprint": "Fingerprint",
        "KeyRound": "Key",
      }
      return defaults[key] || key
    },
  })),
}))

const mockUser = createMockAuthUser()
const mockUserWithAvatar = createMockAuthUser({
  avatar_url: "https://example.com/avatar.jpg",
})

describe("ProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ user: mockUser, isAuthenticated: true, updateUser: vi.fn() })
    )
    vi.mocked(useProfile).mockReturnValue({ data: mockUser, isLoading: false } as any)
    vi.mocked(useUpdateProfile).mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
    vi.mocked(useChangePassword).mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
  })

  it("renders profile page", () => {
    render(<ProfilePage />)
    expect(screen.getByText("Profile")).toBeInTheDocument()
    expect(screen.getByText("Profile Information")).toBeInTheDocument()
    expect(screen.getByText("Avatar")).toBeInTheDocument()
  })

  it("displays user name on page", () => {
    render(<ProfilePage />)
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
  })

  it("renders preferences and sessions placeholders", () => {
    render(<ProfilePage />)
    expect(screen.getByText("Preferences")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /sessions/i })).toBeInTheDocument()
  })

  describe("avatar upload", () => {
    it("shows 'Upload Picture' button when user has no avatar", () => {
      render(<ProfilePage />)
      expect(screen.getByText("Upload Picture")).toBeInTheDocument()
      expect(screen.getByText("PNG, JPG or WebP. Max 2 MB.")).toBeInTheDocument()
    })

    it("shows 'Change Photo' button when user has an avatar", () => {
      vi.mocked(useAuth).mockReturnValue(
        createMockAuthContext({ user: mockUserWithAvatar, isAuthenticated: true, updateUser: vi.fn() })
      )
      render(<ProfilePage />)
      expect(screen.getByText("Change Photo")).toBeInTheDocument()
    })

    it("has a hidden file input that accepts images", () => {
      render(<ProfilePage />)
      const fileInput = document.querySelector('input[type="file"]')
      expect(fileInput).toBeInTheDocument()
      expect(fileInput).toHaveAttribute("accept", "image/png,image/jpeg,image/webp")
      expect(fileInput).toHaveClass("hidden")
    })

    it("opens file picker when Upload Picture is clicked", async () => {
      const user = userEvent.setup()
      render(<ProfilePage />)

      const button = screen.getByText("Upload Picture")
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
      const clickSpy = vi.spyOn(fileInput, "click")

      await user.click(button)

      expect(clickSpy).toHaveBeenCalledTimes(1)
    })

    it("shows Save and Cancel buttons after avatar file selection", async () => {
      const OriginalFileReader = globalThis.FileReader
      let mockOnload: ((ev: ProgressEvent<FileReader>) => void) | null = null

      class MockFileReader extends OriginalFileReader {
        private _result: string | null = null
        override get result(): string | ArrayBuffer | null {
          return this._result
        }
        constructor() {
          super()
          mockOnload = null
        }
        override readAsDataURL(_blob: Blob): void {
          this._result = "data:image/png;base64,test"
          Promise.resolve().then(() => {
            if (mockOnload) {
              mockOnload.call(this, {} as ProgressEvent<FileReader>)
            }
          })
        }
        set onload(fn: ((ev: ProgressEvent<FileReader>) => void) | null) {
          mockOnload = fn
        }
        get onload(): ((ev: ProgressEvent<FileReader>) => void) | null {
          return mockOnload
        }
      }

      globalThis.FileReader = MockFileReader

      render(<ProfilePage />)
      const user = userEvent.setup()
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
      const file = new File(["test"], "avatar.png", { type: "image/png" })

      await user.upload(fileInput, file)

      await vi.waitFor(() => {
        expect(screen.getByText("Save Photo")).toBeInTheDocument()
      })
      expect(screen.getByText("Cancel")).toBeInTheDocument()

      globalThis.FileReader = OriginalFileReader
    })
  })
})
