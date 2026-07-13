import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { SectionWrapper } from "@/components/shared/section-wrapper"

describe("SectionWrapper", () => {
  it("renders children", () => {
    render(<SectionWrapper><p>Content</p></SectionWrapper>)
    expect(screen.getByText("Content")).toBeInTheDocument()
  })

  it("applies default spacing classes", () => {
    render(<SectionWrapper>Content</SectionWrapper>)
    const section = screen.getByText("Content").closest("section")!
    expect(section.className).toContain("py-16")
    expect(section.className).toContain("md:py-24")
  })

  it("applies custom className", () => {
    render(<SectionWrapper className="bg-muted/30">Content</SectionWrapper>)
    const section = screen.getByText("Content").closest("section")!
    expect(section.className).toContain("bg-muted/30")
  })

  it("applies id prop", () => {
    render(<SectionWrapper id="test-section">Content</SectionWrapper>)
    const section = screen.getByText("Content").closest("section")!
    expect(section).toHaveAttribute("id", "test-section")
  })

  it("renders with container-wide", () => {
    render(<SectionWrapper>Content</SectionWrapper>)
    const container = screen.getByText("Content").closest("[class*='container-wide']")
    expect(container).toBeInTheDocument()
  })
})
