import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import ChangelogPage from "@/pages/public/changelog"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    p: ({ children, ...props }: any) => <p {...props}>{children}</p>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("ChangelogPage", () => {
  it("renders Changelog heading", () => {
    render(<ChangelogPage />)
    expect(screen.getByText("Changelog")).toBeInTheDocument()
  })

  it("renders introduction text", () => {
    render(<ChangelogPage />)
    expect(
      screen.getByText(/this changelog covers all notable changes/i)
    ).toBeInTheDocument()
  })

  it("renders release version items", () => {
    render(<ChangelogPage />)
    expect(screen.getByText("v1.0.0")).toBeInTheDocument()
    expect(screen.getByText("v0.9.0")).toBeInTheDocument()
    expect(screen.getByText("v0.8.0")).toBeInTheDocument()
    expect(screen.getByText("v0.7.0")).toBeInTheDocument()
    expect(screen.getByText("v0.6.0")).toBeInTheDocument()
  })

  it("renders release section titles for the first release", () => {
    render(<ChangelogPage />)
    // Multiple releases have same section titles, so getAllByText
    const addedHeadings = screen.getAllByText("Added")
    expect(addedHeadings.length).toBeGreaterThanOrEqual(1)
    const changedHeadings = screen.getAllByText("Changed")
    expect(changedHeadings.length).toBeGreaterThanOrEqual(1)
    const fixedHeadings = screen.getAllByText("Fixed")
    expect(fixedHeadings.length).toBeGreaterThanOrEqual(1)
  })

  it("shows download CTA section", () => {
    render(<ChangelogPage />)
    expect(
      screen.getByText("Download the latest release")
    ).toBeInTheDocument()
    expect(
      screen.getByText(/get the most recent version/i)
    ).toBeInTheDocument()
  })

  it("renders Go to Downloads button", () => {
    render(<ChangelogPage />)
    expect(screen.getByText("Go to Downloads")).toBeInTheDocument()
  })

  it("renders release date for version 1.0.0", () => {
    render(<ChangelogPage />)
    expect(screen.getByText("June 15, 2026")).toBeInTheDocument()
  })
})
