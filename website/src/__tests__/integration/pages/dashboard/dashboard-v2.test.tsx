import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import DashboardPage from "@/pages/dashboard/dashboard"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders "Welcome back" heading', () => {
    render(<DashboardPage />)
    expect(screen.getByText("Welcome back")).toBeInTheDocument()
  })

  it("renders stats cards", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Active Licenses")).toBeInTheDocument()
    expect(screen.getByText("Team Members")).toBeInTheDocument()
  })

  it("shows tabs (Overview / Recent Activity)", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Overview")).toBeInTheDocument()
    expect(screen.getByText("Recent Activity")).toBeInTheDocument()
  })

  it("shows quick action cards", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Downloads")).toBeInTheDocument()
    expect(screen.getByText("Support")).toBeInTheDocument()
  })

  it("shows announcements", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Announcements")).toBeInTheDocument()
  })

  it("shows Quick Actions heading", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Quick Actions")).toBeInTheDocument()
  })
})
