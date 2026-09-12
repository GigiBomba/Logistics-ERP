import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import DashboardDownloadsPage from "@/pages/dashboard/downloads"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("DashboardDownloadsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders "Downloads" heading and description', () => {
    render(<DashboardDownloadsPage />)
    expect(screen.getByText("Downloads")).toBeInTheDocument()
    expect(screen.getByText(/Download the latest Operion desktop application/i)).toBeInTheDocument()
  })

  it("shows Pre-release badge and coming-soon version info", () => {
    render(<DashboardDownloadsPage />)
    expect(screen.getByText("Pre-release")).toBeInTheDocument()
    expect(screen.getByText("Operion ERP — Coming Soon")).toBeInTheDocument()
  })

  it("shows waitlist CTA while the installer is a pre-release", () => {
    render(<DashboardDownloadsPage />)
    expect(screen.getByText("Join the Waitlist")).toBeInTheDocument()
  })

  it("shows System Requirements card with OS, CPU, RAM", () => {
    render(<DashboardDownloadsPage />)
    expect(screen.getByText("System Requirements")).toBeInTheDocument()
    expect(screen.getByText("Windows 10 (64-bit)")).toBeInTheDocument()
    expect(screen.getByText("Intel Core i5+")).toBeInTheDocument()
    expect(screen.getByText("8 GB (16 GB rec.)")).toBeInTheDocument()
  })

  it("shows Previous Versions card with empty state", () => {
    render(<DashboardDownloadsPage />)
    expect(screen.getByText("Previous Versions")).toBeInTheDocument()
    expect(screen.getByText(/No previous versions/i)).toBeInTheDocument()
  })

  it("shows Toolkit card with Coming Soon status", () => {
    render(<DashboardDownloadsPage />)
    expect(screen.getByText("Toolkit")).toBeInTheDocument()
    expect(screen.getByText("Coming soon")).toBeInTheDocument()
  })

  it("shows Release Notes card with link", () => {
    render(<DashboardDownloadsPage />)
    expect(screen.getByText("Release Notes")).toBeInTheDocument()
    expect(screen.getByText(/View full release notes/i)).toBeInTheDocument()
  })
})
