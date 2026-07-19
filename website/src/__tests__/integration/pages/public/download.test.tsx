import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import DownloadPage from "@/pages/public/download"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/config/site", () => ({
  downloadConfig: {
    latestVersion: "In Development",
    releaseDate: "",
    windowsInstaller: "",
    fileSize: "TBD",
    systemRequirements: {
      os: ["Windows 10 (64-bit)", "Windows 11 (64-bit)"],
      ram: "8 GB minimum (16 GB recommended)",
      storage: "2 GB available space",
      processor: "Intel Core i5 or equivalent",
      additional: "Python 3.10+",
    },
  },
  toolkitConfig: {
    latestVersion: "1.0.0",
    releaseDate: "2026-09-01",
    downloadUrl: "/downloads/operion-toolkit-1.0.0.exe",
  },
}))

describe("DownloadPage", () => {
  it("renders page header", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Download Operion Desktop")).toBeInTheDocument()
    expect(
      screen.getByText(/Get the latest version of the Operion ERP desktop application/i)
    ).toBeInTheDocument()
  })

  it("renders primary download card with version and badge", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Latest Release")).toBeInTheDocument()
    expect(screen.getByText(/Operion ERP In Development/)).toBeInTheDocument()
    expect(screen.getByText("Not Yet Available")).toBeInTheDocument()
  })

  it("renders system requirements section", () => {
    render(<DownloadPage />)
    expect(screen.getByText("System Requirements")).toBeInTheDocument()
    expect(screen.getByText("Operating System")).toBeInTheDocument()
    expect(screen.getByText("Processor")).toBeInTheDocument()
    expect(screen.getByText("RAM & Storage")).toBeInTheDocument()
    expect(screen.getByText("Additional")).toBeInTheDocument()
  })

  it("renders installation instructions", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Installation Instructions")).toBeInTheDocument()
    expect(screen.getByText("Download the Installer")).toBeInTheDocument()
    expect(screen.getByText("Run the Installer")).toBeInTheDocument()
    expect(screen.getByText("Follow the Setup Wizard")).toBeInTheDocument()
    expect(screen.getByText("Launch Operion ERP")).toBeInTheDocument()
  })

  it("renders uninstallation section", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Uninstallation Instructions")).toBeInTheDocument()
  })

  it("renders release channel tabs", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Stable")).toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.getByText("Nightly")).toBeInTheDocument()
    expect(screen.getByText("Legacy")).toBeInTheDocument()
  })

  it("renders release history heading in stable tab", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Release History")).toBeInTheDocument()
  })

  it("renders migration guides section", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Migration Guides")).toBeInTheDocument()
  })

  it("renders documentation bundle section", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Documentation Bundle")).toBeInTheDocument()
    expect(screen.getByText("Operion Docs Offline")).toBeInTheDocument()
    expect(screen.getByText("Download Docs Bundle")).toBeInTheDocument()
  })

  it("renders auto-update callout", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Automatic Updates")).toBeInTheDocument()
  })

  it("renders toolkit section", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Operion Developer Toolkit")).toBeInTheDocument()
    expect(screen.getByText(/Toolkit v1\.0\.0/)).toBeInTheDocument()
  })

  it("renders Download Toolkit link with correct href", () => {
    render(<DownloadPage />)
    const toolkitLink = screen.getByRole("link", { name: /download toolkit/i })
    expect(toolkitLink).toBeInTheDocument()
    expect(toolkitLink).toHaveAttribute("href", "/downloads/operion-toolkit-1.0.0.exe")
  })

  it("renders Documentation link to /developers/toolkit", () => {
    render(<DownloadPage />)
    const docLinks = screen
      .getAllByRole("link")
      .filter((l) => l.getAttribute("href") === "/developers/toolkit")
    expect(docLinks.length).toBeGreaterThanOrEqual(1)
  })

  it("renders bottom CTA banner", () => {
    render(<DownloadPage />)
    expect(screen.getByText("Ready to Get Started?")).toBeInTheDocument()
    expect(screen.getByText("Start Free Trial")).toBeInTheDocument()
  })

  it("renders canonical link in helmet", () => {
    render(<DownloadPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operion.com/download")
  })
})
