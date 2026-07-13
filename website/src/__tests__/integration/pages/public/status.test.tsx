import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import StatusPage from "@/pages/public/status"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    p: ({ children, ...props }: any) => <p {...props}>{children}</p>,
  },
}))

describe("StatusPage", () => {
  it("renders System Status heading", () => {
    render(<StatusPage />)
    expect(screen.getByText("System Status")).toBeInTheDocument()
  })

  it("shows overall status banner with All Systems Operational", () => {
    render(<StatusPage />)
    expect(
      screen.getByText("All Systems Operational")
    ).toBeInTheDocument()
    expect(
      screen.getByText(/all operion services are running normally/i)
    ).toBeInTheDocument()
  })

  it("renders service group titles", () => {
    render(<StatusPage />)
    expect(screen.getByText("Core Services")).toBeInTheDocument()
    expect(screen.getByText("Platform")).toBeInTheDocument()
    expect(screen.getByText("Communication")).toBeInTheDocument()
  })

  it("renders service names", () => {
    render(<StatusPage />)
    expect(screen.getByText("Website")).toBeInTheDocument()
    expect(screen.getByText("API")).toBeInTheDocument()
    expect(screen.getByText("Authentication")).toBeInTheDocument()
    expect(screen.getByText("Downloads")).toBeInTheDocument()
    expect(screen.getByText("Documentation")).toBeInTheDocument()
    expect(screen.getByText("Customer Portal")).toBeInTheDocument()
    expect(screen.getByText("Support System")).toBeInTheDocument()
    expect(screen.getByText("Email Notifications")).toBeInTheDocument()
  })

  it("shows service status badges (Operational)", () => {
    render(<StatusPage />)
    const operationalBadges = screen.getAllByText("Operational")
    // All mock services are operational
    expect(operationalBadges.length).toBe(8)
  })

  it("renders last updated timestamp", () => {
    render(<StatusPage />)
    expect(screen.getByText(/last updated/i)).toBeInTheDocument()
  })

  it("renders service group descriptions", () => {
    render(<StatusPage />)
    expect(
      screen.getByText(/essential platform services/i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/customer-facing tools/i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/notification and support infrastructure/i)
    ).toBeInTheDocument()
  })
})
