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

  it("shows development status banner", () => {
    render(<StatusPage />)
    expect(screen.getByText("In Active Development")).toBeInTheDocument()
  })

  it("renders component names", () => {
    render(<StatusPage />)
    expect(screen.getByText("Desktop App")).toBeInTheDocument()
    expect(screen.getByText("Web Portal")).toBeInTheDocument()
    expect(screen.getByText("API Backend")).toBeInTheDocument()
  })

  it("renders status badges", () => {
    render(<StatusPage />)
    const badges = screen.getAllByText("In Development")
    expect(badges.length).toBeGreaterThanOrEqual(1)
  })
})
