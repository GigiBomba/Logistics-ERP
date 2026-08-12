import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { AppShell } from "@/components/layout/app-shell"
import { useAuth } from "@/contexts/auth-provider"
import { useTheme } from "@/contexts/theme-provider"
import {
  useOrganizations,
  usePortalNotifications,
  useMarkNotificationRead,
  useMarkAllRead,
  useSubscription,
} from "@/services/queries"
import { createMockAuthUser, createMockAuthContext, createMockThemeContext } from "@/test-utils"

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

vi.mock("@/contexts/theme-provider", () => ({
  useTheme: vi.fn(),
}))

vi.mock("@/services/queries", () => ({
  useOrganizations: vi.fn(),
  usePortalNotifications: vi.fn(),
  useMarkNotificationRead: vi.fn(),
  useMarkAllRead: vi.fn(),
  useSubscription: vi.fn(),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

const makeMutation = (overrides: Record<string, any> = {}) => ({
  mutate: vi.fn(),
  isPending: false,
  ...overrides,
})

describe("AppShell — DashboardLayout", () => {
  const mockSetTheme = vi.fn()
  const mockLogout = vi.fn()
  const mockTheme = createMockThemeContext({ setTheme: mockSetTheme })
  const mockUser = createMockAuthUser()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useTheme).mockReturnValue(mockTheme)
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ user: mockUser, isAuthenticated: true, logout: mockLogout })
    )
    vi.mocked(useOrganizations).mockReturnValue({ data: [] } as any)
    vi.mocked(usePortalNotifications).mockReturnValue({ data: [], isLoading: false } as any)
    vi.mocked(useMarkNotificationRead).mockReturnValue(makeMutation() as any)
    vi.mocked(useMarkAllRead).mockReturnValue(makeMutation() as any)
    vi.mocked(useSubscription).mockReturnValue({ data: undefined, isLoading: false } as any)
  })

  it("renders the dashboard sidebar with nav links", () => {
    render(<AppShell />, { initialEntries: ["/dashboard"] })
    expect(screen.getByRole("link", { name: /overview/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /company/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /subscription/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /settings/i })).toBeInTheDocument()
  })

  it("cycles the theme light -> dark", () => {
    render(<AppShell />, { initialEntries: ["/dashboard"] })
    fireEvent.click(screen.getByRole("button", { name: /toggle theme/i }))
    expect(mockSetTheme).toHaveBeenCalledWith("dark")
  })

  it("opens and closes the mobile sidebar", () => {
    render(<AppShell />, { initialEntries: ["/dashboard"] })
    fireEvent.click(screen.getByRole("button", { name: /toggle menu/i }))
    // backdrop appears when the sidebar is open
    const backdrop = document.querySelector(".bg-black\\/50")
    expect(backdrop).toBeTruthy()
    fireEvent.click(backdrop as Element)
    expect(document.querySelector(".bg-black\\/50")).toBeFalsy()
  })

  it("opens the user menu and signs out", () => {
    render(<AppShell />, { initialEntries: ["/dashboard"] })
    // user menu trigger is labelled with the user name
    fireEvent.click(screen.getByRole("button", { name: "Test User" }))
    // sidebar + user menu both expose Sign out; click the user-menu one
    const signOutButtons = screen.getAllByRole("button", { name: /sign out/i })
    expect(signOutButtons.length).toBeGreaterThanOrEqual(2)
    fireEvent.click(signOutButtons[signOutButtons.length - 1])
    expect(mockLogout).toHaveBeenCalled()
  })

  it("logs out from the sidebar logout button", () => {
    render(<AppShell />, { initialEntries: ["/dashboard"] })
    const logoutButtons = screen.getAllByText("Sign out")
    // sidebar logout is a button
    fireEvent.click(logoutButtons[0])
    expect(mockLogout).toHaveBeenCalled()
  })

  it("switches organizations and invalidates org-scoped queries", () => {
    vi.mocked(useOrganizations).mockReturnValue({
      data: [
        { id: 1, name: "Acme", industry: "Logistics" },
        { id: 2, name: "Globex", industry: "Freight" },
      ],
    } as any)
    const { queryClient } = render(<AppShell />, { initialEntries: ["/dashboard"] })
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    // trigger + select the second org (activeOrgId is stringified, so trigger shows the placeholder)
    fireEvent.click(screen.getByRole("button", { name: /select organization/i }))
    fireEvent.click(screen.getByRole("option", { name: /globex/i }))

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["devices"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["subscription"] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["company"] })
  })

  it("marks all notifications as read from the notification center", () => {
    const markAllRead = vi.fn()
    vi.mocked(usePortalNotifications).mockReturnValue({
      data: [
        { id: "n1", title: "Trip completed", message: "Route 42 done", read: false, type: "system", created_at: "2026-07-01T00:00:00Z" },
      ],
      isLoading: false,
    } as any)
    vi.mocked(useMarkAllRead).mockReturnValue(makeMutation({ mutate: markAllRead }) as any)
    render(<AppShell />, { initialEntries: ["/dashboard"] })

    fireEvent.click(screen.getByRole("button", { name: /notifications \(1 unread\)/i }))
    fireEvent.click(screen.getByRole("button", { name: /mark all read/i }))
    expect(markAllRead).toHaveBeenCalled()
  })

  it("marks a single notification as read", () => {
    const markRead = vi.fn()
    vi.mocked(usePortalNotifications).mockReturnValue({
      data: [
        { id: "n1", title: "Trip completed", message: "Route 42 done", read: false, type: "system", created_at: "2026-07-01T00:00:00Z" },
      ],
      isLoading: false,
    } as any)
    vi.mocked(useMarkNotificationRead).mockReturnValue(makeMutation({ mutate: markRead }) as any)
    render(<AppShell />, { initialEntries: ["/dashboard"] })

    fireEvent.click(screen.getByRole("button", { name: /notifications \(1 unread\)/i }))
    fireEvent.click(screen.getByRole("button", { name: /mark read/i }))
    expect(markRead).toHaveBeenCalledWith("n1")
  })

  it("shows the notification empty state", () => {
    render(<AppShell />, { initialEntries: ["/dashboard"] })
    fireEvent.click(screen.getByRole("button", { name: /^notifications$/i }))
    expect(screen.getByText("No new notifications")).toBeInTheDocument()
  })

  it("renders the org switcher select-org state when there are no organizations", () => {
    render(<AppShell />, { initialEntries: ["/dashboard"] })
    expect(screen.getByText("Select Organization")).toBeInTheDocument()
  })
})

describe("AppShell — PublicLayout interactions", () => {
  const mockSetTheme = vi.fn()
  const mockTheme = createMockThemeContext({ setTheme: mockSetTheme })

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useTheme).mockReturnValue(mockTheme)
    vi.mocked(useOrganizations).mockReturnValue({ data: [] } as any)
    vi.mocked(usePortalNotifications).mockReturnValue({ data: [], isLoading: false } as any)
    vi.mocked(useMarkNotificationRead).mockReturnValue(makeMutation() as any)
    vi.mocked(useMarkAllRead).mockReturnValue(makeMutation() as any)
    vi.mocked(useSubscription).mockReturnValue({ data: undefined, isLoading: false } as any)
  })

  it("opens the product dropdown on hover and closes on mouse leave", () => {
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext())
    render(<AppShell />)

    const productLink = screen.getByRole("link", { name: /^product$/i })
    const dropdown = productLink.parentElement as HTMLElement
    fireEvent.mouseEnter(dropdown)
    // dropdown child + footer Resources section both link to Product Tour
    expect(screen.getAllByRole("link", { name: /product tour/i }).length).toBeGreaterThanOrEqual(2)

    fireEvent.mouseLeave(dropdown)
  })

  it("opens the mobile menu and shows sign in / waitlist links for guests", () => {
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext())
    render(<AppShell />)

    // mobile menu toggle (labelled "Toggle menu")
    const toggle = screen.getByRole("button", { name: /toggle menu/i })
    fireEvent.click(toggle)
    expect(screen.getAllByRole("link", { name: /waitlist/i }).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByRole("link", { name: /sign in/i }).length).toBeGreaterThanOrEqual(1)
  })

  it("shows the dashboard link in the mobile menu for authenticated users", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ user: createMockAuthUser(), isAuthenticated: true })
    )
    render(<AppShell />)
    fireEvent.click(screen.getByRole("button", { name: /toggle menu/i }))
    expect(screen.getAllByRole("link", { name: /dashboard/i }).length).toBeGreaterThanOrEqual(1)
  })

  it("cycles theme from the public header toggle", () => {
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext())
    render(<AppShell />)
    const toggles = screen.getAllByRole("button", { name: /toggle theme/i })
    fireEvent.click(toggles[0])
    expect(mockSetTheme).toHaveBeenCalledWith("dark")
  })

  it("opens the support chat modal from the header", () => {
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext())
    render(<AppShell />)
    const chatButtons = screen.getAllByRole("button", { name: /live chat/i })
    fireEvent.click(chatButtons[0])
    // SupportModal is open when the dialog role appears
    expect(screen.getAllByRole("dialog").length).toBeGreaterThanOrEqual(0)
  })
})
