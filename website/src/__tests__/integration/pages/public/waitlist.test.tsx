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
})
