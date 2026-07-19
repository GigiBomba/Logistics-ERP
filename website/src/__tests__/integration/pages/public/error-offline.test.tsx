import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import ErrorOfflinePage from "@/pages/public/error-offline"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("ErrorOfflinePage", () => {
  beforeEach(() => {
    // Default: simulate offline
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: false,
    })
  })

  it("renders offline heading when offline", () => {
    render(<ErrorOfflinePage />)
    expect(screen.getByText("You're Offline")).toBeInTheDocument()
  })

  it("renders offline description", () => {
    render(<ErrorOfflinePage />)
    expect(
      screen.getByText(/please check your internet connection/i)
    ).toBeInTheDocument()
  })

  it("renders retry button", () => {
    render(<ErrorOfflinePage />)
    expect(screen.getByText("Retry")).toBeInTheDocument()
  })

  it("shows back online state when navigator.onLine is true", () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    })
    render(<ErrorOfflinePage />)
    expect(screen.getByText("You're Back Online")).toBeInTheDocument()
    expect(screen.getByText("Reload Page")).toBeInTheDocument()
  })

  it("renders reload button when back online", () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    })
    render(<ErrorOfflinePage />)
    const reloadBtn = screen.getByText("Reload Page")
    expect(reloadBtn).toBeInTheDocument()
  })
})
