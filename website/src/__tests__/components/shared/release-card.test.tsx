import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { ReleaseCard } from "@/components/shared/release-card"

const baseRelease = {
  version: "2.5.0",
  release_date: "2026-07-01T00:00:00Z",
  sections: [
    {
      title: "New Features",
      items: ["Real-time tracking", "Geofencing support"],
    },
    {
      title: "Bug Fixes",
      items: ["Fixed login timeout", "Fixed map rendering on Safari"],
    },
  ],
  type: "app" as const,
}

describe("ReleaseCard", () => {
  it("renders version number", () => {
    render(<ReleaseCard release={baseRelease} />)
    expect(screen.getByText("v2.5.0")).toBeInTheDocument()
  })

  it("renders release date", () => {
    render(<ReleaseCard release={baseRelease} />)
    expect(screen.getByText("July 1, 2026")).toBeInTheDocument()
  })

  it("renders type badge for app", () => {
    render(<ReleaseCard release={baseRelease} />)
    expect(screen.getByText("Application")).toBeInTheDocument()
  })

  it("renders type badge for toolkit", () => {
    const toolkitRelease = { ...baseRelease, type: "toolkit" as const }
    render(<ReleaseCard release={toolkitRelease} />)
    expect(screen.getByText("Toolkit")).toBeInTheDocument()
  })

  it("renders changelog sections", () => {
    render(<ReleaseCard release={baseRelease} />)
    expect(screen.getByText("New Features")).toBeInTheDocument()
    expect(screen.getByText("Bug Fixes")).toBeInTheDocument()
    expect(screen.getByText("Real-time tracking")).toBeInTheDocument()
    expect(screen.getByText("Geofencing support")).toBeInTheDocument()
    expect(screen.getByText("Fixed login timeout")).toBeInTheDocument()
    expect(screen.getByText("Fixed map rendering on Safari")).toBeInTheDocument()
  })

  it("renders file size when provided", () => {
    const releaseWithSize = { ...baseRelease, size_mb: 42.5 }
    render(<ReleaseCard release={releaseWithSize} />)
    expect(screen.getByText("42.5 MB")).toBeInTheDocument()
  })

  it("does not render file size when not provided", () => {
    render(<ReleaseCard release={baseRelease} />)
    expect(screen.queryByText(/MB/)).not.toBeInTheDocument()
  })

  it("renders download button when downloads_url is provided", () => {
    const releaseWithDownload = {
      ...baseRelease,
      downloads_url: "https://example.com/download/v2.5.0",
    }
    render(<ReleaseCard release={releaseWithDownload} />)
    const downloadButton = screen.getByRole("link", { name: /download v2.5.0/i })
    expect(downloadButton).toBeInTheDocument()
    expect(downloadButton).toHaveAttribute(
      "href",
      "https://example.com/download/v2.5.0"
    )
  })

  it("does not render download button when downloads_url is not provided", () => {
    render(<ReleaseCard release={baseRelease} />)
    expect(screen.queryByRole("link", { name: /download/i })).not.toBeInTheDocument()
  })
})
