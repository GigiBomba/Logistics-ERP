import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import ErrorMaintenancePage from "@/pages/public/error-maintenance"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("ErrorMaintenancePage", () => {
  it("renders maintenance heading", () => {
    render(<ErrorMaintenancePage />)
    expect(screen.getByText("Under Maintenance")).toBeInTheDocument()
  })

  it("renders maintenance description", () => {
    render(<ErrorMaintenancePage />)
    expect(
      screen.getByText(/we're performing scheduled maintenance/i)
    ).toBeInTheDocument()
  })

  it("shows expected duration", () => {
    render(<ErrorMaintenancePage />)
    expect(screen.getByText(/within 2 hours/i)).toBeInTheDocument()
  })

  it("renders status page link pointing to /status", () => {
    render(<ErrorMaintenancePage />)
    const statusLink = screen.getByText("Status Page").closest("a")
    expect(statusLink).toHaveAttribute("href", "/status")
  })

  it("renders go home link pointing to /", () => {
    render(<ErrorMaintenancePage />)
    const homeLink = screen.getByText("Go Home").closest("a")
    expect(homeLink).toHaveAttribute("href", "/")
  })

  it("renders both action buttons", () => {
    render(<ErrorMaintenancePage />)
    expect(screen.getByText("Status Page")).toBeInTheDocument()
    expect(screen.getByText("Go Home")).toBeInTheDocument()
  })
})
