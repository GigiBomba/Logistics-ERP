import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import WaitlistPage from "@/pages/public/waitlist"
import { useWaitlistCount } from "@/services/queries"
import { waitlistApi } from "@/api/endpoints"
import { trackEvent } from "@/services/analytics"

vi.mock("@/services/queries", () => ({
  useWaitlistCount: vi.fn(),
}))

vi.mock("@/api/endpoints", () => ({
  waitlistApi: { join: vi.fn() },
}))

vi.mock("@/services/analytics", () => ({
  trackEvent: vi.fn(),
}))

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useInView: () => true,
}))

vi.mock("@/components/shared/turnstile-widget", () => ({
  default: () => null,
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe("WaitlistPage", () => {
  it("renders the live waitlist count from the API", async () => {
    vi.mocked(useWaitlistCount).mockReturnValue({
      data: { count: 513, cached_at: "2026-08-02T00:00:00Z" },
      isLoading: false,
    } as any)

    render(<WaitlistPage />)
    // AnimatedCounter counts up from 0 — wait for it to reach the live figure
    await waitFor(() => expect(screen.getByText(/513/)).toBeVisible(), { timeout: 5000 })
    expect(screen.getByText(/logistics professionals have joined/i)).toBeInTheDocument()
  })

  it("shows a loading skeleton while the count is loading", () => {
    vi.mocked(useWaitlistCount).mockReturnValue({ data: undefined, isLoading: true } as any)

    render(<WaitlistPage />)
    expect(document.querySelector(".animate-pulse")).not.toBeNull()
  })

  it("falls back to the 500 default when the count request errors", async () => {
    vi.mocked(useWaitlistCount).mockReturnValue({ data: undefined, isLoading: false } as any)

    render(<WaitlistPage />)
    expect(await screen.findByText(/500/, {}, { timeout: 3000 })).toBeInTheDocument()
  })

  it("shows the referral code after joining and tracks the WhatsApp share", async () => {
    vi.mocked(useWaitlistCount).mockReturnValue({
      data: { count: 513, cached_at: "2026-08-02T00:00:00Z" },
      isLoading: false,
    } as any)
    vi.mocked(waitlistApi.join).mockResolvedValueOnce({
      data: { status: "joined", referral_code: "REF-123" },
    } as any)

    const user = userEvent.setup()
    render(<WaitlistPage />)

    await user.type(screen.getByLabelText(/company name/i), "Acme Logistics")
    await user.type(screen.getByLabelText(/email/i), "ops@acme.example")
    await user.click(screen.getByRole("button", { name: /join waitlist/i }))

    expect(await screen.findByText("REF-123")).toBeInTheDocument()
    expect(waitlistApi.join).toHaveBeenCalledWith({
      company_name: "Acme Logistics",
      email: "ops@acme.example",
      source: "landing_page",
      turnstile_token: undefined,
    })

    await user.click(screen.getByRole("link", { name: /share on whatsapp/i }))
    expect(trackEvent).toHaveBeenCalledWith("referral_shared", "referral", "whatsapp:REF-123")
  })

  it("hides the optional onboarding fields by default and reveals them via the toggle", async () => {
    vi.mocked(useWaitlistCount).mockReturnValue({
      data: { count: 513, cached_at: "2026-08-02T00:00:00Z" },
      isLoading: false,
    } as any)

    const user = userEvent.setup()
    render(<WaitlistPage />)

    // Progressive-disclosure fields are hidden by default
    expect(screen.queryByLabelText(/contact name/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/company size/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/country/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/fleet size/i)).not.toBeInTheDocument()

    // Toggle reveals them
    await user.click(screen.getByRole("button", { name: /more details/i }))

    expect(screen.getByLabelText(/contact name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/company size/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/country/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/fleet size/i)).toBeInTheDocument()
  })

  it("includes the optional onboarding fields in the join request when provided", async () => {
    vi.mocked(useWaitlistCount).mockReturnValue({
      data: { count: 513, cached_at: "2026-08-02T00:00:00Z" },
      isLoading: false,
    } as any)
    vi.mocked(waitlistApi.join).mockResolvedValueOnce({
      data: { status: "joined", referral_code: "REF-456" },
    } as any)

    const user = userEvent.setup()
    render(<WaitlistPage />)

    await user.type(screen.getByLabelText(/company name/i), "Acme Logistics")
    await user.type(screen.getByLabelText(/email/i), "ops@acme.example")
    await user.click(screen.getByRole("button", { name: /more details/i }))

    await user.type(screen.getByLabelText(/contact name/i), "Jane Doe")
    await user.selectOptions(screen.getByLabelText(/company size/i), "11-50")
    await user.type(screen.getByLabelText(/country/i), "RO")
    await user.selectOptions(screen.getByLabelText(/fleet size/i), "21-50")

    await user.click(screen.getByRole("button", { name: /join waitlist/i }))

    await waitFor(() =>
      expect(waitlistApi.join).toHaveBeenCalledWith({
        company_name: "Acme Logistics",
        email: "ops@acme.example",
        contact_name: "Jane Doe",
        company_size: "11-50",
        country: "RO",
        fleet_size: "21-50",
        source: "landing_page",
        turnstile_token: undefined,
      })
    )
  })

  it("pre-fills the source from the /waitlist?source= route param", async () => {
    vi.mocked(useWaitlistCount).mockReturnValue({
      data: { count: 513, cached_at: "2026-08-02T00:00:00Z" },
      isLoading: false,
    } as any)
    vi.mocked(waitlistApi.join).mockResolvedValueOnce({
      data: { status: "joined", referral_code: "REF-789" },
    } as any)

    const user = userEvent.setup()
    render(<WaitlistPage />, { initialEntries: ["/waitlist?source=route_calculator"] })

    await user.type(screen.getByLabelText(/company name/i), "Acme Logistics")
    await user.type(screen.getByLabelText(/email/i), "ops@acme.example")
    await user.click(screen.getByRole("button", { name: /join waitlist/i }))

    await waitFor(() =>
      expect(waitlistApi.join).toHaveBeenCalledWith(
        expect.objectContaining({ source: "route_calculator" })
      )
    )
  })

  it("submits the form when Enter is pressed in an input", async () => {
    vi.mocked(useWaitlistCount).mockReturnValue({
      data: { count: 513, cached_at: "2026-08-02T00:00:00Z" },
      isLoading: false,
    } as any)
    vi.mocked(waitlistApi.join).mockResolvedValueOnce({
      data: { status: "joined", referral_code: "REF-000" },
    } as any)

    const user = userEvent.setup()
    render(<WaitlistPage />)

    await user.type(screen.getByLabelText(/company name/i), "Acme Logistics")
    await user.type(screen.getByLabelText(/email/i), "ops@acme.example")
    await user.keyboard("{Enter}")

    await waitFor(() => expect(waitlistApi.join).toHaveBeenCalled())
    expect(await screen.findByText("REF-000")).toBeInTheDocument()
  })
})