import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import ProfilePage from "@/pages/dashboard/profile"
import { useAuth } from "@/contexts/auth-provider"
import { useProfile, useUpdateProfile, useChangePassword } from "@/services/queries"
import { createMockAuthUser, createMockAuthContext } from "@/test-utils"

vi.mock("@/services/queries", () => ({
  useProfile: vi.fn(),
  useUpdateProfile: vi.fn(),
  useChangePassword: vi.fn(),
}))

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

vi.mock("@/contexts/theme-provider", () => ({
  useTheme: vi.fn(() => ({ theme: "light" as const, setTheme: vi.fn(), resolvedTheme: "light" as const })),
}))

const mockUser = createMockAuthUser()

describe("ProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ user: mockUser, isAuthenticated: true })
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
})
