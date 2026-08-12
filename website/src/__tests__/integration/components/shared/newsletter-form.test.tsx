import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import { NewsletterForm } from "@/components/shared/newsletter-form"
import { newsletterApi } from "@/api/endpoints"
import { toast } from "sonner"

vi.mock("@/api/endpoints", () => ({
  newsletterApi: { subscribe: vi.fn(), unsubscribe: vi.fn() },
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

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

beforeEach(() => {
  vi.clearAllMocks()
})

// The email <Input> is labelled by its placeholder ("you@company.com") via
// aria-label — there is no visible <label>, so query it as a textbox.
const emailInput = () => screen.getByRole("textbox", { name: /you@company\.com/i })

describe("NewsletterForm", () => {
  it("renders the card variant with email input, preferences, and subscribe button", () => {
    render(<NewsletterForm variant="card" />)
    expect(screen.getByText("Stay Updated")).toBeInTheDocument()
    expect(emailInput()).toBeInTheDocument()
    expect(screen.getByText("Product Updates")).toBeInTheDocument()
    expect(screen.getByText("Blog Digest")).toBeInTheDocument()
    expect(screen.getByText("Event Invites")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /subscribe/i })).toBeInTheDocument()
  })

  it("submits the email and default preferences to the newsletter API", async () => {
    vi.mocked(newsletterApi.subscribe).mockResolvedValue({ data: { status: "ok" } } as any)
    const user = userEvent.setup()

    render(<NewsletterForm variant="card" />)
    await user.type(emailInput(), "ops@acme.example")
    await user.click(screen.getByRole("button", { name: /subscribe/i }))

    expect(await screen.findByText(/thanks for subscribing/i)).toBeInTheDocument()
    expect(newsletterApi.subscribe).toHaveBeenCalledWith({
      email: "ops@acme.example",
      preferences: ["product_updates"],
    })
    expect(toast.success).toHaveBeenCalled()
  })

  it("toggles a preference off before submitting", async () => {
    vi.mocked(newsletterApi.subscribe).mockResolvedValue({ data: { status: "ok" } } as any)
    const user = userEvent.setup()

    render(<NewsletterForm variant="card" />)
    await user.type(emailInput(), "ops@acme.example")
    await user.click(screen.getByLabelText(/product updates/i))

    await user.click(screen.getByRole("button", { name: /subscribe/i }))

    expect(await screen.findByText(/thanks for subscribing/i)).toBeInTheDocument()
    expect(newsletterApi.subscribe).toHaveBeenCalledWith({
      email: "ops@acme.example",
      preferences: [],
    })
  })

  it("shows an error message when the API call fails", async () => {
    vi.mocked(newsletterApi.subscribe).mockRejectedValue(new Error("rate limited"))
    const user = userEvent.setup()

    render(<NewsletterForm variant="card" />)
    await user.type(emailInput(), "ops@acme.example")
    await user.click(screen.getByRole("button", { name: /subscribe/i }))

    expect(await screen.findByText("rate limited")).toBeInTheDocument()
    expect(screen.queryByText(/thanks for subscribing/i)).not.toBeInTheDocument()
  })

  it("does not submit when the email is empty", async () => {
    const user = userEvent.setup()
    render(<NewsletterForm variant="card" />)

    await user.click(screen.getByRole("button", { name: /subscribe/i }))
    expect(newsletterApi.subscribe).not.toHaveBeenCalled()
  })
})
