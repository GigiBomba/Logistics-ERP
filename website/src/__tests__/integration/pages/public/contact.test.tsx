import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor, fireEvent, act } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import ContactPage from "@/pages/public/contact"
import { contactApi } from "@/api/endpoints"
import { toast } from "sonner"
import { AxiosError } from "axios"

vi.mock("@/api/endpoints", () => ({
  contactApi: { send: vi.fn() },
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
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

const { turnstilePropsRef } = vi.hoisted(() => ({ turnstilePropsRef: { current: null as any } }))

vi.mock("@/components/shared/turnstile-widget", () => ({
  default: (props: any) => {
    turnstilePropsRef.current = props
    return <div data-testid="mock-turnstile" />
  },
}))

function getForm(container: HTMLElement): HTMLFormElement {
  const form = container.querySelector("form")
  if (!form) throw new Error("form not found")
  return form as HTMLFormElement
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/name/i), "Jane Doe")
  await user.type(screen.getByLabelText(/email/i), "jane@operionerp.xyz")
  await user.type(screen.getByLabelText(/subject/i), "Product question")
  await user.type(screen.getByLabelText(/message/i), "I would like to know more about pricing.")
}

describe("ContactPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    turnstilePropsRef.current = null
  })

  it("renders the contact form and contact details", () => {
    render(<ContactPage />)
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/subject/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/message/i)).toBeInTheDocument()
    expect(screen.getAllByText("contact@operionerp.xyz").length).toBeGreaterThan(0)
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument()
  })

  it("shows validation errors for an invalid submission", async () => {
    const user = userEvent.setup()
    const { container } = render(<ContactPage />)
    await user.type(screen.getByLabelText(/email/i), "bad")
    fireEvent.submit(getForm(container))

    expect(await screen.findByText("Name must be at least 2 characters")).toBeInTheDocument()
    expect(screen.getByText("Please enter a valid email")).toBeInTheDocument()
    expect(screen.getByText("Subject must be at least 5 characters")).toBeInTheDocument()
    expect(screen.getByText("Message must be at least 10 characters")).toBeInTheDocument()
    expect(contactApi.send).not.toHaveBeenCalled()
  })

  it("submits the contact form and shows a success toast", async () => {
    vi.mocked(contactApi.send).mockResolvedValue({ data: { status: "ok" } } as any)
    const user = userEvent.setup()
    render(<ContactPage />)
    await fillValidForm(user)
    await user.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => {
      expect(contactApi.send).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Jane Doe",
          email: "jane@operionerp.xyz",
          subject: "Product question",
          message: "I would like to know more about pricing.",
          hp_field: undefined,
          turnstile_token: undefined,
        })
      )
    })
    expect(toast.success).toHaveBeenCalled()
  })

  it("passes the turnstile token with the submission", async () => {
    vi.mocked(contactApi.send).mockResolvedValue({ data: { status: "ok" } } as any)
    const user = userEvent.setup()
    render(<ContactPage />)
    await fillValidForm(user)
    act(() => turnstilePropsRef.current.onVerify("tok-contact"))
    await user.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => {
      expect(contactApi.send).toHaveBeenCalledWith(
        expect.objectContaining({ turnstile_token: "tok-contact" })
      )
    })
  })

  it("shows the rate-limit toast on a 429 response", async () => {
    const err = new AxiosError("Too many", "ERR_BAD_RESPONSE")
    err.response = { status: 429, data: {}, statusText: "x", headers: {}, config: {} as any }
    vi.mocked(contactApi.send).mockRejectedValue(err)
    const user = userEvent.setup()
    render(<ContactPage />)
    await fillValidForm(user)
    await user.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Too many requests. Please wait a moment and try again.")
    })
  })

  it("shows an extracted error toast for other failures", async () => {
    const err = new AxiosError("Request failed", "ERR_BAD_RESPONSE")
    err.response = { status: 500, data: { detail: "Server exploded" }, statusText: "x", headers: {}, config: {} as any }
    vi.mocked(contactApi.send).mockRejectedValue(err)
    const user = userEvent.setup()
    render(<ContactPage />)
    await fillValidForm(user)
    await user.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Server exploded")
    })
  })

  it("clears the turnstile token when it expires", async () => {
    vi.mocked(contactApi.send).mockResolvedValue({ data: { status: "ok" } } as any)
    const user = userEvent.setup()
    render(<ContactPage />)
    await fillValidForm(user)
    act(() => {
      turnstilePropsRef.current.onVerify("tok-x")
      turnstilePropsRef.current.onExpired()
    })
    await user.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => {
      expect(contactApi.send).toHaveBeenCalledWith(
        expect.objectContaining({ turnstile_token: undefined })
      )
    })
  })

  it("resets the form fields after a successful submit", async () => {
    vi.mocked(contactApi.send).mockResolvedValue({ data: { status: "ok" } } as any)
    const user = userEvent.setup()
    render(<ContactPage />)
    await fillValidForm(user)
    await user.click(screen.getByRole("button", { name: /send/i }))

    await waitFor(() => expect(toast.success).toHaveBeenCalled())
    expect(screen.getByLabelText(/name/i)).toHaveValue("")
    expect(screen.getByLabelText(/email/i)).toHaveValue("")
  })
})
