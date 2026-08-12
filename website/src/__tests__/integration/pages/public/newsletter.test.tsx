import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import NewsletterPage from "@/pages/public/newsletter"
import { useSubscribeNewsletter } from "@/services/queries"

const { mutateMock } = vi.hoisted(() => ({ mutateMock: vi.fn() }))

vi.mock("@/services/queries", () => ({
  useSubscribeNewsletter: vi.fn(),
}))

const { motionMock } = vi.hoisted(() => {
  const MockMotionDiv = ({ children, ...rest }: any) => <div {...rest}>{children}</div>
  return {
    motionMock: new Proxy({}, { get: () => MockMotionDiv }),
  }
})

vi.mock("motion/react", () => ({
  motion: motionMock,
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useInView: () => true,
}))

vi.mock("@/config/site", async () => {
  const actual = await vi.importActual<typeof import("@/config/site")>("@/config/site")
  return {
    ...actual,
    siteConfig: {
      name: "Operion",
    },
    apiConfig: { baseUrl: "http://localhost:8000", timeout: 15000 },
  }
})

describe("NewsletterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mutateMock.mockReset()
    vi.mocked(useSubscribeNewsletter).mockReturnValue({
      mutate: mutateMock,
      isPending: false,
    } as any)
  })

  it("renders heading and description", () => {
    render(<NewsletterPage />)
    expect(screen.getByText("Stay Updated")).toBeInTheDocument()
    expect(screen.getByText(/get the latest news/i)).toBeInTheDocument()
  })

  it("renders subscription form", () => {
    render(<NewsletterPage />)
    expect(screen.getByPlaceholderText(/you@company.com/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /subscribe/i })).toBeInTheDocument()
  })

  it("renders privacy policy link", () => {
    render(<NewsletterPage />)
    expect(screen.getByText(/privacy policy/i)).toBeInTheDocument()
  })

  it("subscribes and shows the success state", async () => {
    const user = userEvent.setup()
    render(<NewsletterPage />)
    await user.type(screen.getByPlaceholderText(/you@company.com/i), "sub@operionerp.xyz")
    await user.click(screen.getByRole("button", { name: /subscribe/i }))

    expect(mutateMock).toHaveBeenCalledWith(
      { email: "sub@operionerp.xyz" },
      expect.objectContaining({ onSuccess: expect.any(Function) })
    )
    // Simulate the mutation success callback
    const call = mutateMock.mock.calls[0][1] as { onSuccess: () => void }
    call.onSuccess()
    expect(await screen.findByText(/thanks for subscribing/i)).toBeInTheDocument()
  })

  it("shows an error message when the mutation fails", async () => {
    const user = userEvent.setup()
    render(<NewsletterPage />)
    await user.type(screen.getByPlaceholderText(/you@company.com/i), "sub@operionerp.xyz")
    await user.click(screen.getByRole("button", { name: /subscribe/i }))

    const call = mutateMock.mock.calls[0][1] as { onError: () => void }
    call.onError()
    expect(await screen.findByText(/subscription failed/i)).toBeInTheDocument()
  })

  it("does not submit when the email is empty", async () => {
    const user = userEvent.setup()
    render(<NewsletterPage />)
    await user.click(screen.getByRole("button", { name: /subscribe/i }))
    expect(mutateMock).not.toHaveBeenCalled()
  })
})
