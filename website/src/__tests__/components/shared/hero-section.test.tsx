import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { HeroSection } from "@/components/shared/hero-section"

describe("HeroSection", () => {
  it("renders title", () => {
    render(<HeroSection title="Welcome" />)
    expect(screen.getByRole("heading", { name: /welcome/i })).toBeInTheDocument()
  })

  it("renders description", () => {
    render(<HeroSection title="Title" description="Hero description" />)
    expect(screen.getByText("Hero description")).toBeInTheDocument()
  })

  it("renders without description", () => {
    render(<HeroSection title="Title" />)
    expect(screen.queryByText("Hero description")).not.toBeInTheDocument()
  })

  it("applies text-center class for center alignment", () => {
    const { container } = render(<HeroSection title="Centered" align="center" />)
    const innerDiv = container.querySelector(".container-wide")
    expect(innerDiv?.className).toContain("text-center")
  })

  it("does not apply text-center for left alignment (default)", () => {
    const { container } = render(<HeroSection title="Left" />)
    const innerDiv = container.querySelector(".container-wide")
    expect(innerDiv?.className).not.toContain("text-center")
  })

  it("applies correct padding for default size", () => {
    const { container } = render(<HeroSection title="Default" />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toContain("py-20")
  })

  it("applies correct padding for large size", () => {
    const { container } = render(<HeroSection title="Large" size="large" />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toContain("py-24")
  })

  it("applies correct padding for compact size", () => {
    const { container } = render(<HeroSection title="Compact" size="compact" />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toContain("py-12")
  })

  it("renders children", () => {
    render(
      <HeroSection title="With Children">
        <button>Action Button</button>
      </HeroSection>
    )
    expect(screen.getByRole("button", { name: /action button/i })).toBeInTheDocument()
  })

  it("renders background slot", () => {
    const { container } = render(
      <HeroSection title="With Background" background={<div data-testid="bg-slot" />} />
    )
    const bgSlot = container.querySelector('[data-testid="bg-slot"]')
    expect(bgSlot).toBeInTheDocument()
  })
})
