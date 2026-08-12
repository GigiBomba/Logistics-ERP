import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import ToolkitPage from "@/pages/public/toolkit"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/config/site", async () => {
  const actual = await vi.importActual<typeof import("@/config/site")>("@/config/site")
  return {
    ...actual,
    toolkitConfig: {
      latestVersion: "1.0.0",
      releaseDate: "2026-09-01",
      downloadUrl: "/downloads/operion-toolkit-1.0.0.exe",
    },
  }
})

describe("ToolkitPage", () => {
  it("renders 'Operion Toolkit' heading", () => {
    render(<ToolkitPage />)
    expect(screen.getByText("Operion Toolkit")).toBeInTheDocument()
  })

  it("shows download button", () => {
    render(<ToolkitPage />)
    const downloadButtons = screen.getAllByText("Download Toolkit")
    expect(downloadButtons.length).toBeGreaterThanOrEqual(1)
  })

  it("shows system requirements", () => {
    render(<ToolkitPage />)
    expect(screen.getByText("System Requirements")).toBeInTheDocument()
    expect(screen.getByText("Operating System")).toBeInTheDocument()
    expect(screen.getByText("Processor")).toBeInTheDocument()
    expect(screen.getByText("RAM & Storage")).toBeInTheDocument()
    expect(screen.getByText("Dependencies")).toBeInTheDocument()
  })

  it("shows installation instructions", () => {
    render(<ToolkitPage />)
    expect(screen.getByText("Installation")).toBeInTheDocument()
    expect(screen.getByText("Download the installer")).toBeInTheDocument()
    expect(screen.getByText("Run the installer")).toBeInTheDocument()
    expect(screen.getByText("Verify the installation")).toBeInTheDocument()
  })

  it("shows release history", () => {
    render(<ToolkitPage />)
    expect(screen.getByText("Release History")).toBeInTheDocument()
    expect(screen.getByText("Previous Versions")).toBeInTheDocument()
  })

  it("shows what's included section", () => {
    render(<ToolkitPage />)
    expect(screen.getByText("What's Included")).toBeInTheDocument()
    expect(screen.getByText("CLI Interface")).toBeInTheDocument()
    expect(screen.getByText("Authentication Helper")).toBeInTheDocument()
    expect(screen.getByText("Data Import / Export")).toBeInTheDocument()
    expect(screen.getByText("Local Development Server")).toBeInTheDocument()
    expect(screen.getByText("Schema Validator")).toBeInTheDocument()
    expect(screen.getByText("Log Analyzer")).toBeInTheDocument()
  })

  it("shows CTA", () => {
    render(<ToolkitPage />)
    expect(screen.getByText("Need help getting started?")).toBeInTheDocument()
    expect(screen.getByText("Contact support")).toBeInTheDocument()
  })
})
