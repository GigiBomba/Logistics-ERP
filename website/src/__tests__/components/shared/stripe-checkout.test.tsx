import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import { StripeCheckout } from "@/components/shared/stripe-checkout"
import { AxiosError } from "axios"

const { toastErrorMock } = vi.hoisted(() => ({
  toastErrorMock: vi.fn(),
}))

vi.mock("sonner", () => ({
  toast: { error: toastErrorMock },
}))

vi.mock("@/api/client", () => ({
  default: { get: vi.fn(), post: vi.fn() },
  extractApiError: (error: unknown) =>
    error instanceof Error ? error.message : "unexpected",
}))

const { createCheckoutSessionMock } = vi.hoisted(() => ({
  createCheckoutSessionMock: vi.fn(),
}))

vi.mock("@/api/endpoints", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/endpoints")>()
  return {
    ...actual,
    subscriptionApi: { ...actual.subscriptionApi, createCheckoutSession: createCheckoutSessionMock },
  }
})

describe("StripeCheckout", () => {
  const originalLocation = window.location

  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, href: "" },
      writable: true,
    })
    createCheckoutSessionMock.mockResolvedValue({
      data: { session_id: "cs_test_1", url: "https://checkout.stripe.com/c/pay/cs_test_1" },
    })
  })

  it("renders children", () => {
    render(<StripeCheckout>Upgrade</StripeCheckout>)
    expect(screen.getByText("Upgrade")).toBeInTheDocument()
  })

  it("starts checkout on click and redirects to Stripe", async () => {
    const onStart = vi.fn()
    const onComplete = vi.fn()
    render(
      <StripeCheckout onCheckoutStart={onStart} onCheckoutComplete={onComplete}>
        Pay
      </StripeCheckout>
    )

    fireEvent.click(screen.getByRole("button", { name: /pay/i }))

    await waitFor(() => {
      expect(createCheckoutSessionMock).toHaveBeenCalledTimes(1)
    })
    expect(onStart).toHaveBeenCalledTimes(1)
    expect(onComplete).toHaveBeenCalledWith("cs_test_1")
    expect(window.location.href).toBe("https://checkout.stripe.com/c/pay/cs_test_1")
  })

  it("handles checkout errors with toast and onError callback", async () => {
    createCheckoutSessionMock.mockRejectedValueOnce(
      new AxiosError("Checkout failed", "ERR_BAD_REQUEST")
    )
    const onError = vi.fn()
    render(<StripeCheckout onError={onError}>Pay</StripeCheckout>)

    fireEvent.click(screen.getByRole("button", { name: /pay/i }))

    await waitFor(() => {
      expect(onError).toHaveBeenCalledTimes(1)
    })
    expect(toastErrorMock).toHaveBeenCalledWith("Checkout failed")
    expect(window.location.href).toBe("")
  })

  it("triggers checkout on Enter key", async () => {
    render(<StripeCheckout>Pay</StripeCheckout>)
    fireEvent.keyDown(screen.getByRole("button", { name: /pay/i }), { key: "Enter" })
    await waitFor(() => {
      expect(createCheckoutSessionMock).toHaveBeenCalledTimes(1)
    })
  })

  it("triggers checkout on Space key", async () => {
    render(<StripeCheckout>Pay</StripeCheckout>)
    fireEvent.keyDown(screen.getByRole("button", { name: /pay/i }), { key: " " })
    await waitFor(() => {
      expect(createCheckoutSessionMock).toHaveBeenCalledTimes(1)
    })
  })

  it("ignores non-activation keys", () => {
    render(<StripeCheckout>Pay</StripeCheckout>)
    fireEvent.keyDown(screen.getByRole("button", { name: /pay/i }), { key: "Tab" })
    expect(createCheckoutSessionMock).not.toHaveBeenCalled()
  })

  it("ignores clicks while a checkout is in progress", async () => {
    let resolve!: (v: unknown) => void
    createCheckoutSessionMock.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolve = r
        })
    )
    const onStart = vi.fn()
    render(<StripeCheckout onCheckoutStart={onStart}>Pay</StripeCheckout>)

    fireEvent.click(screen.getByRole("button", { name: /pay/i }))
    // Click again while the first checkout is pending
    fireEvent.click(screen.getByRole("button", { name: /pay/i }))

    resolve({ data: { session_id: "cs_test_1", url: "https://checkout.stripe.com/c/pay/x" } })

    await waitFor(() => {
      expect(createCheckoutSessionMock).toHaveBeenCalledTimes(1)
    })
    expect(onStart).toHaveBeenCalledTimes(1)
  })
})
