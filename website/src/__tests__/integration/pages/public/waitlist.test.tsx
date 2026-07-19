import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import WaitlistPage from "@/pages/public/waitlist"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/api/endpoints", () => ({
  waitlistApi: {
    join: vi.fn(),
  },
}))

vi.mock("@/api/client", () => ({
  extractApiError: vi.fn(() => "Signup failed. Please try again."),
}))

vi.mock("axios", () => {
  const AxiosError = class extends Error {
    response?: { status: number; data: unknown }
    constructor(message?: string) {
      super(message)
      this.name = "AxiosError"
    }
  }
  return { AxiosError }
})

describe("WaitlistPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders the page title", () => {
    render(<WaitlistPage />)
    expect(screen.getByText("Join the Waitlist")).toBeInTheDocument()
  })

  it("shows social proof counter", () => {
    render(<WaitlistPage />)
    expect(screen.getByText("500+")).toBeInTheDocument()
    expect(screen.getByText("logistics professionals have joined")).toBeInTheDocument()
  })

  it("shows next launch info", () => {
    render(<WaitlistPage />)
    expect(screen.getByText("Q3 2026")).toBeInTheDocument()
    expect(screen.getByText("Next Launch")).toBeInTheDocument()
  })

  it("renders the signup form with company name and email fields", () => {
    render(<WaitlistPage />)
    expect(screen.getByLabelText("Company name")).toBeInTheDocument()
    const emailLabel = screen.getByText("Email")
    expect(emailLabel).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /join waitlist/i })).toBeInTheDocument()
  })

  it("renders the 'More details' button and toggles optional fields", () => {
    render(<WaitlistPage />)
    const moreDetailsBtn = screen.getByText(/more details/i)
    expect(moreDetailsBtn).toBeInTheDocument()

    // Optional fields should be hidden initially
    expect(screen.queryByLabelText("Contact name")).not.toBeInTheDocument()

    // Click to show optional fields
    fireEvent.click(moreDetailsBtn)
    expect(screen.getByLabelText("Contact name")).toBeInTheDocument()
    expect(screen.getByLabelText("Company size")).toBeInTheDocument()
    expect(screen.getByLabelText("Country")).toBeInTheDocument()
    expect(screen.getByLabelText("Fleet size")).toBeInTheDocument()
  })

  it("renders benefits section", () => {
    render(<WaitlistPage />)
    expect(screen.getByText("What you'll get")).toBeInTheDocument()
    expect(screen.getByText("Early Access")).toBeInTheDocument()
    expect(screen.getByText("Launch Notifications")).toBeInTheDocument()
  })

  it("renders launch roadmap section", () => {
    render(<WaitlistPage />)
    expect(screen.getByText("Launch Roadmap")).toBeInTheDocument()
    expect(screen.getByText("AI Dispatch Assistant")).toBeInTheDocument()
    expect(screen.getByText("Mobile Driver App")).toBeInTheDocument()
    expect(screen.getByText("Advanced Analytics Suite")).toBeInTheDocument()
    expect(screen.getByText("Multi-Entity Support")).toBeInTheDocument()
  })

  it("renders 'No spam' disclaimer", () => {
    render(<WaitlistPage />)
    expect(screen.getByText(/no spam, ever/i)).toBeInTheDocument()
  })

  it("shows validation errors on empty submit", async () => {
    render(<WaitlistPage />)
    const joinBtn = screen.getByRole("button", { name: /join waitlist/i })
    fireEvent.click(joinBtn)

    await waitFor(() => {
      expect(
        screen.getByText("Company name must be at least 2 characters")
      ).toBeInTheDocument()
      expect(screen.getByText("Please enter a valid email")).toBeInTheDocument()
    })
  })
})
