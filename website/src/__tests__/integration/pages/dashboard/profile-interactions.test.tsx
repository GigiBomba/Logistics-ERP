import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import ProfilePage from "@/pages/dashboard/profile"
import { useAuth } from "@/contexts/auth-provider"
import { useTheme } from "@/contexts/theme-provider"
import {
  useProfile,
  useUpdateProfile,
  useChangePassword,
  useSessions,
  useRevokeSession,
  useAvatarUpload,
  useUpdateNotificationPreferences,
} from "@/services/queries"
import { createMockAuthUser, createMockAuthContext, createMockThemeContext } from "@/test-utils"
import { toast } from "sonner"
import userEvent from "@testing-library/user-event"

vi.mock("@/services/queries", () => ({
  useProfile: vi.fn(),
  useUpdateProfile: vi.fn(),
  useChangePassword: vi.fn(),
  useSessions: vi.fn(),
  useRevokeSession: vi.fn(),
  useAvatarUpload: vi.fn(),
  useUpdateNotificationPreferences: vi.fn(),
}))

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

vi.mock("@/contexts/theme-provider", () => ({
  useTheme: vi.fn(),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const makeMutation = (overrides: Record<string, any> = {}) => ({
  mutate: vi.fn(),
  isPending: false,
  ...overrides,
})

const mockUser = createMockAuthUser()

/** Mock FileReader that synchronously resolves to a data URL. */
function installFileReaderMock() {
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
        if (mockOnload) mockOnload.call(this, {} as ProgressEvent<FileReader>)
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
  return () => {
    globalThis.FileReader = OriginalFileReader
  }
}

describe("ProfilePage — interactions", () => {
  const mockSetTheme = vi.fn()
  const mockUpdateUser = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ user: mockUser, isAuthenticated: true, updateUser: mockUpdateUser })
    )
    vi.mocked(useTheme).mockReturnValue(createMockThemeContext({ setTheme: mockSetTheme }))
    vi.mocked(useProfile).mockReturnValue({ data: mockUser, isLoading: false } as any)
    vi.mocked(useUpdateProfile).mockReturnValue(makeMutation() as any)
    vi.mocked(useChangePassword).mockReturnValue(makeMutation() as any)
    vi.mocked(useSessions).mockReturnValue({ data: [], isLoading: false, isError: false } as any)
    vi.mocked(useRevokeSession).mockReturnValue(makeMutation() as any)
    vi.mocked(useAvatarUpload).mockReturnValue(makeMutation() as any)
    vi.mocked(useUpdateNotificationPreferences).mockReturnValue(makeMutation() as any)
  })

  it("updates the profile on form submit", async () => {
    const mutate = vi.fn()
    vi.mocked(useUpdateProfile).mockReturnValue(makeMutation({ mutate }) as any)
    const user = userEvent.setup()
    render(<ProfilePage />)

    const nameInput = screen.getByLabelText(/full name/i)
    await user.clear(nameInput)
    await user.type(nameInput, "New Name")
    await user.click(screen.getByRole("button", { name: /save changes/i }))

    expect(mutate).toHaveBeenCalledWith({ name: "New Name", email: "test@operionerp.xyz" })
  })

  it("shows validation errors on invalid profile form", async () => {
    const mutate = vi.fn()
    vi.mocked(useUpdateProfile).mockReturnValue(makeMutation({ mutate }) as any)
    const user = userEvent.setup()
    render(<ProfilePage />)

    const nameInput = screen.getByLabelText(/full name/i)
    await user.clear(nameInput)
    await user.type(nameInput, "A")
    await user.click(screen.getByRole("button", { name: /save changes/i }))

    expect(screen.getByText("Name must be at least 2 characters")).toBeInTheDocument()
    expect(mutate).not.toHaveBeenCalled()
  })

  it("changes the password on submit", async () => {
    const mutate = vi.fn()
    vi.mocked(useChangePassword).mockReturnValue(makeMutation({ mutate }) as any)
    const user = userEvent.setup()
    render(<ProfilePage />)
    fireEvent.click(screen.getByRole("tab", { name: /security/i }))

    await user.type(screen.getByLabelText(/current password/i), "oldpass")
    await user.type(screen.getByLabelText(/^new password$/i), "newpassword")
    await user.type(screen.getByLabelText(/confirm new password/i), "newpassword")
    await user.click(screen.getByRole("button", { name: /change password/i }))

    expect(mutate).toHaveBeenCalledWith({
      current_password: "oldpass",
      new_password: "newpassword",
    })
  })

  it("shows a mismatch error when passwords differ", async () => {
    const mutate = vi.fn()
    vi.mocked(useChangePassword).mockReturnValue(makeMutation({ mutate }) as any)
    const user = userEvent.setup()
    render(<ProfilePage />)
    fireEvent.click(screen.getByRole("tab", { name: /security/i }))

    await user.type(screen.getByLabelText(/current password/i), "oldpass")
    await user.type(screen.getByLabelText(/^new password$/i), "newpassword")
    await user.type(screen.getByLabelText(/confirm new password/i), "different")
    await user.click(screen.getByRole("button", { name: /change password/i }))

    expect(screen.getByText("Passwords don't match")).toBeInTheDocument()
    expect(mutate).not.toHaveBeenCalled()
  })

  it("saves notification preferences", () => {
    const mutate = vi.fn((_args, opts: any) => opts?.onSuccess?.())
    vi.mocked(useUpdateNotificationPreferences).mockReturnValue(makeMutation({ mutate }) as any)
    render(<ProfilePage />)
    fireEvent.click(screen.getByRole("tab", { name: /notifications/i }))
    fireEvent.click(screen.getByLabelText(/marketing emails/i))
    fireEvent.click(screen.getByRole("button", { name: /save preferences/i }))
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ marketing_emails: true }), expect.anything())
    expect(toast.success).toHaveBeenCalledWith("Preferences saved successfully")
  })

  it("switches theme from the theme preference buttons", () => {
    render(<ProfilePage />)
    fireEvent.click(screen.getByText("dark"))
    expect(mockSetTheme).toHaveBeenCalledWith("dark")
  })

  describe("avatar upload", () => {
    it("rejects unsupported file types", async () => {
      const restore = installFileReaderMock()
      render(<ProfilePage />)
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
      // bypass the accept attribute filter to exercise the app's own validation
      const gif = new File(["x"], "avatar.gif", { type: "image/gif" })
      Object.defineProperty(fileInput, "files", { configurable: true, value: [gif] })
      fireEvent.change(fileInput)
      expect(toast.error).toHaveBeenCalledWith("Only PNG, JPG, and WebP images are accepted.")
      restore()
    })

    it("rejects oversized files", async () => {
      const restore = installFileReaderMock()
      const user = userEvent.setup()
      render(<ProfilePage />)
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
      const big = new File(["x"], "avatar.png", { type: "image/png" })
      Object.defineProperty(big, "size", { value: 6 * 1024 * 1024 })
      await user.upload(fileInput, big)
      expect(toast.error).toHaveBeenCalledWith("File size must be under 5 MB.")
      restore()
    })

    it("saves the avatar and updates the user", async () => {
      const restore = installFileReaderMock()
      const mutate = vi.fn((_file, opts: any) =>
        opts?.onSuccess?.({ data: { avatar_url: "https://example.com/new-avatar.png" } })
      )
      vi.mocked(useAvatarUpload).mockReturnValue(makeMutation({ mutate }) as any)
      const user = userEvent.setup()
      render(<ProfilePage />)
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement

      await user.upload(fileInput, new File(["x"], "avatar.png", { type: "image/png" }))
      await waitFor(() => expect(screen.getByRole("button", { name: /save photo/i })).toBeInTheDocument())

      await user.click(screen.getByRole("button", { name: /save photo/i }))
      expect(mutate).toHaveBeenCalled()
      expect(mockUpdateUser).toHaveBeenCalledWith(
        expect.objectContaining({ avatar_url: "https://example.com/new-avatar.png" })
      )
      expect(toast.success).toHaveBeenCalledWith("Avatar updated successfully!")
      restore()
    })

    it("toasts an error when the avatar upload fails", async () => {
      const restore = installFileReaderMock()
      const mutate = vi.fn((_file, opts: any) => opts?.onError?.())
      vi.mocked(useAvatarUpload).mockReturnValue(makeMutation({ mutate }) as any)
      const user = userEvent.setup()
      render(<ProfilePage />)
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement

      await user.upload(fileInput, new File(["x"], "avatar.png", { type: "image/png" }))
      await waitFor(() => expect(screen.getByRole("button", { name: /save photo/i })).toBeInTheDocument())
      await user.click(screen.getByRole("button", { name: /save photo/i }))

      expect(toast.error).toHaveBeenCalledWith("Failed to upload avatar. Please try again.")
      restore()
    })

    it("cancels the pending avatar preview", async () => {
      const restore = installFileReaderMock()
      const user = userEvent.setup()
      render(<ProfilePage />)
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement

      await user.upload(fileInput, new File(["x"], "avatar.png", { type: "image/png" }))
      await waitFor(() => expect(screen.getByRole("button", { name: /save photo/i })).toBeInTheDocument())
      await user.click(screen.getByRole("button", { name: /^cancel$/i }))
      expect(screen.getByRole("button", { name: /upload picture/i })).toBeInTheDocument()
      restore()
    })
  })

  describe("sessions tab", () => {
    it("shows a loading skeleton", () => {
      vi.mocked(useSessions).mockReturnValue({ data: [], isLoading: true, isError: false } as any)
      render(<ProfilePage />)
      fireEvent.click(screen.getByRole("tab", { name: /sessions/i }))
      expect(screen.getByText("Active Sessions")).toBeInTheDocument()
    })

    it("shows a load error callout", () => {
      vi.mocked(useSessions).mockReturnValue({ data: [], isLoading: false, isError: true } as any)
      render(<ProfilePage />)
      fireEvent.click(screen.getByRole("tab", { name: /sessions/i }))
      expect(screen.getByText("Failed to load sessions")).toBeInTheDocument()
    })

    it("shows the empty state", () => {
      vi.mocked(useSessions).mockReturnValue({ data: [], isLoading: false, isError: false } as any)
      render(<ProfilePage />)
      fireEvent.click(screen.getByRole("tab", { name: /sessions/i }))
      expect(screen.getByText("No active sessions")).toBeInTheDocument()
    })

    it("revokes a session", () => {
      const revoke = vi.fn()
      vi.mocked(useSessions).mockReturnValue({
        data: [
          { id: 42, device_name: "Chrome", device_platform: "Windows", ip_address: "1.2.3.4", last_active_at: "2026-07-01T00:00:00Z" },
        ],
        isLoading: false,
        isError: false,
      } as any)
      vi.mocked(useRevokeSession).mockReturnValue(makeMutation({ mutate: revoke }) as any)
      render(<ProfilePage />)
      fireEvent.click(screen.getByRole("tab", { name: /sessions/i }))
      const revokeButton = screen
        .getAllByRole("button")
        .find((b) => b.classList.contains("text-destructive")) as HTMLButtonElement
      expect(revokeButton).toBeDefined()
      fireEvent.click(revokeButton)
      expect(revoke).toHaveBeenCalledWith(42)
    })

    it("renders a smartphone icon for mobile devices", () => {
      vi.mocked(useSessions).mockReturnValue({
        data: [
          { id: 7, device_name: "iPhone 15", device_platform: "iOS", ip_address: "9.9.9.9", last_active_at: "2026-07-01T00:00:00Z" },
        ],
        isLoading: false,
        isError: false,
      } as any)
      render(<ProfilePage />)
      fireEvent.click(screen.getByRole("tab", { name: /sessions/i }))
      expect(screen.getByText("iPhone 15")).toBeInTheDocument()
      expect(screen.getByText("iOS · 9.9.9.9")).toBeInTheDocument()
    })
  })
})
