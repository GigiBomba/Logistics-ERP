import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, act } from "@/test-utils"
import TurnstileWidget from "@/components/shared/turnstile-widget"

const { envConfig } = vi.hoisted(() => ({
  envConfig: { turnstileSiteKey: "test-site-key", maintenanceMode: false, stripePublishableKey: "" },
}))

vi.mock("@/config/env", () => ({ envConfig }))

const { turnstilePropsRef } = vi.hoisted(() => ({
  turnstilePropsRef: { current: null as any },
}))

vi.mock("@marsidev/react-turnstile", () => ({
  Turnstile: (props: any) => {
    turnstilePropsRef.current = props
    return <div data-testid="mock-turnstile" />
  },
}))

describe("TurnstileWidget", () => {
  beforeEach(() => {
    turnstilePropsRef.current = null
  })

  it("renders nothing when no site key is configured", () => {
    envConfig.turnstileSiteKey = ""
    const { container } = render(<TurnstileWidget onVerify={vi.fn()} />)
    expect(container.firstChild).toBeNull()
    envConfig.turnstileSiteKey = "test-site-key"
  })

  it("renders the Turnstile widget with the configured site key", () => {
    render(<TurnstileWidget onVerify={vi.fn()} />)
    expect(screen.getByTestId("mock-turnstile")).toBeInTheDocument()
    expect(turnstilePropsRef.current.siteKey).toBe("test-site-key")
    expect(turnstilePropsRef.current.options).toMatchObject({ size: "normal" })
  })

  it("shows verifying indicator while loading", () => {
    render(<TurnstileWidget onVerify={vi.fn()} />)
    expect(screen.getByText("Verifying...")).toBeInTheDocument()
  })

  it("passes theme through options when provided", () => {
    render(<TurnstileWidget onVerify={vi.fn()} theme="dark" />)
    expect(turnstilePropsRef.current.options).toMatchObject({ theme: "dark", size: "normal" })
  })

  it("omits theme from options when not provided", () => {
    render(<TurnstileWidget onVerify={vi.fn()} />)
    expect(turnstilePropsRef.current.options.theme).toBeUndefined()
  })

  it("calls onVerify with the token on success and hides the indicator", () => {
    const onVerify = vi.fn()
    render(<TurnstileWidget onVerify={onVerify} />)
    act(() => turnstilePropsRef.current.onSuccess("tok-123"))
    expect(onVerify).toHaveBeenCalledWith("tok-123")
    expect(screen.queryByText("Verifying...")).not.toBeInTheDocument()
  })

  it("calls onExpired and re-shows the indicator on expire", () => {
    const onExpired = vi.fn()
    render(<TurnstileWidget onVerify={vi.fn()} onExpired={onExpired} />)
    act(() => turnstilePropsRef.current.onExpire())
    expect(onExpired).toHaveBeenCalledTimes(1)
    expect(screen.getByText("Verifying...")).toBeInTheDocument()
  })

  it("calls onError and hides the indicator on error", () => {
    const onError = vi.fn()
    render(<TurnstileWidget onVerify={vi.fn()} onError={onError} />)
    act(() => turnstilePropsRef.current.onError())
    expect(onError).toHaveBeenCalledTimes(1)
    expect(screen.queryByText("Verifying...")).not.toBeInTheDocument()
  })

  it("hides the indicator on load", () => {
    render(<TurnstileWidget onVerify={vi.fn()} />)
    act(() => turnstilePropsRef.current.onLoad())
    expect(screen.queryByText("Verifying...")).not.toBeInTheDocument()
  })

  it("does not throw when optional callbacks are omitted", () => {
    render(<TurnstileWidget onVerify={vi.fn()} />)
    expect(() => {
      act(() => {
        turnstilePropsRef.current.onExpire()
        turnstilePropsRef.current.onError()
      })
    }).not.toThrow()
  })
})
