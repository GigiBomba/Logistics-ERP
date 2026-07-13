import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { LogoCloud } from "@/components/shared/logo-cloud"

const mockLogos = [
  { name: "Company A", src: "/logos/a.png" },
  { name: "Company B", src: "/logos/b.png", href: "https://company-b.com" },
  { name: "Company C", src: "/logos/c.png" },
]

describe("LogoCloud", () => {
  it("renders all logos", () => {
    render(<LogoCloud logos={mockLogos} />)
    expect(screen.getByAltText("Company A logo")).toBeInTheDocument()
    expect(screen.getByAltText("Company B logo")).toBeInTheDocument()
    expect(screen.getByAltText("Company C logo")).toBeInTheDocument()
  })

  it("renders optional title", () => {
    render(<LogoCloud logos={mockLogos} title="Trusted by companies" />)
    expect(screen.getByText("Trusted by companies")).toBeInTheDocument()
  })

  it("does not render title when not provided", () => {
    render(<LogoCloud logos={mockLogos} />)
    expect(screen.queryByText("Trusted by companies")).not.toBeInTheDocument()
  })

  it("renders logo as link when href is provided", () => {
    render(<LogoCloud logos={mockLogos} />)
    const link = screen.getByAltText("Company B logo").closest("a")
    expect(link).toHaveAttribute("href", "https://company-b.com")
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", "noopener noreferrer")
  })

  it("renders logo as plain image when no href", () => {
    render(<LogoCloud logos={mockLogos} />)
    const imgA = screen.getByAltText("Company A logo")
    expect(imgA.closest("a")).toBeNull()

    const imgC = screen.getByAltText("Company C logo")
    expect(imgC.closest("a")).toBeNull()
  })

  it("applies grayscale and opacity classes to images", () => {
    render(<LogoCloud logos={mockLogos} />)
    const img = screen.getByAltText("Company A logo")
    expect(img.className).toContain("grayscale")
    expect(img.className).toContain("opacity-50")
  })

  it("has correct src attributes", () => {
    render(<LogoCloud logos={mockLogos} />)
    const img = screen.getByAltText("Company A logo") as HTMLImageElement
    expect(img.src).toContain("/logos/a.png")
  })
})
