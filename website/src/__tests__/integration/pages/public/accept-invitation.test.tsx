import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@/test-utils"
import AcceptInvitationPage from "@/pages/public/accept-invitation"
import { organizationsApi } from "@/api/endpoints"
import { mockAxiosResponse } from "@/test-utils"
import { AxiosError } from "axios"

vi.mock("@/api/endpoints", () => ({
  organizationsApi: { acceptInvitation: vi.fn() },
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("AcceptInvitationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("shows invalid link when token is missing", () => {
    render(<AcceptInvitationPage />)
    expect(screen.getByText("Invalid Invitation Link")).toBeInTheDocument()
    expect(screen.getByText(/missing or invalid/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /contact support/i })).toHaveAttribute(
      "href",
      "/contact",
    )
  })

  it("shows loading then success on valid token", async () => {
    let resolvePromise: (value: any) => void
    vi.mocked(organizationsApi.acceptInvitation).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePromise = resolve
        }),
    )

    render(<AcceptInvitationPage />, {
      initialEntries: ["/accept-invitation?token=abc123"],
    })

    expect(await screen.findByText("Accepting invitation…")).toBeInTheDocument()
    expect(screen.getByText(/please wait/i)).toBeInTheDocument()

    resolvePromise!(
      mockAxiosResponse({
        id: 99,
        org_id: 1,
        user_id: "u-99",
        role: "member",
        status: "active",
        name: "New User",
        email: "new@operion.dev",
        joined_at: "2026-08-05T00:00:00Z",
      }),
    )

    await waitFor(() => {
      expect(screen.getByText("Invitation accepted")).toBeInTheDocument()
    })
    expect(screen.getByText(/successfully joined/i)).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /go to organizations/i }),
    ).toHaveAttribute("href", "/dashboard/organizations")
  })

  it("shows error state on generic API failure", async () => {
    let rejectPromise: (reason?: any) => void
    vi.mocked(organizationsApi.acceptInvitation).mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          rejectPromise = reject
        }),
    )

    render(<AcceptInvitationPage />, {
      initialEntries: ["/accept-invitation?token=badtoken"],
    })

    expect(await screen.findByText("Accepting invitation…")).toBeInTheDocument()

    rejectPromise!(new Error("network"))

    await waitFor(() => {
      expect(screen.getByText("Could not accept invitation")).toBeInTheDocument()
    })
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    const contactLinks = screen.getAllByRole("link", { name: /contact support/i })
    expect(contactLinks.length).toBeGreaterThanOrEqual(1)
    expect(contactLinks[0]).toHaveAttribute("href", "/contact")
  })

  it("shows already-accepted info state when API indicates duplicate", async () => {
    let rejectPromise: (reason?: any) => void
    vi.mocked(organizationsApi.acceptInvitation).mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          rejectPromise = reject
        }),
    )

    render(<AcceptInvitationPage />, {
      initialEntries: ["/accept-invitation?token=already"],
    })

    expect(await screen.findByText("Accepting invitation…")).toBeInTheDocument()

    const err = new AxiosError("Already accepted")
    err.response = {
      status: 409,
      data: { detail: "Invitation already accepted", error_code: "invitation/already-accepted" },
      statusText: "Conflict",
      headers: {},
      config: {} as any,
    }
    rejectPromise!(err)

    await waitFor(() => {
      expect(screen.getByText("Already a member")).toBeInTheDocument()
    })
    expect(screen.getByText(/already part of this organization/i)).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: /go to organizations/i }),
    ).toHaveAttribute("href", "/dashboard/organizations")
  })

  it("shows expired-specific message when API returns invitation/expired", async () => {
    let rejectPromise: (reason?: any) => void
    vi.mocked(organizationsApi.acceptInvitation).mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          rejectPromise = reject
        }),
    )

    render(<AcceptInvitationPage />, {
      initialEntries: ["/accept-invitation?token=expired"],
    })

    expect(await screen.findByText("Accepting invitation…")).toBeInTheDocument()

    const err = new AxiosError("Expired")
    err.response = {
      status: 400,
      data: { detail: "Invitation has expired", error_code: "invitation/expired" },
      statusText: "Bad Request",
      headers: {},
      config: {} as any,
    }
    rejectPromise!(err)

    await waitFor(() => {
      expect(screen.getByText("Could not accept invitation")).toBeInTheDocument()
    })
    expect(screen.getByText(/expired or is no longer valid/i)).toBeInTheDocument()
  })

  it("shows invalid-link message when API returns invitation/invalid", async () => {
    let rejectPromise: (reason?: any) => void
    vi.mocked(organizationsApi.acceptInvitation).mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          rejectPromise = reject
        }),
    )

    render(<AcceptInvitationPage />, {
      initialEntries: ["/accept-invitation?token=invalid"],
    })

    expect(await screen.findByText("Accepting invitation…")).toBeInTheDocument()

    const err = new AxiosError("Invalid")
    err.response = {
      status: 404,
      data: { detail: "Invalid invitation token", error_code: "invitation/invalid" },
      statusText: "Not Found",
      headers: {},
      config: {} as any,
    }
    rejectPromise!(err)

    await waitFor(() => {
      expect(screen.getByText("Could not accept invitation")).toBeInTheDocument()
    })
    expect(screen.getByText(/missing or invalid/i)).toBeInTheDocument()
  })
})
