import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import { CtaSection } from "@/components/shared/cta-section"

describe("CtaSection", () => {
  it("renders title", () => {
    render(<CtaSection title="Get Started" />)
    expect(screen.getByRole("heading", { name: /get started/i })).toBeInTheDocument()
  })

  it("renders description", () => {
    render(<CtaSection title="Title" description="Description text" />)
    expect(screen.getByText("Description text")).toBeInTheDocument()
  })

  it("renders primary CTA with default label and href", () => {
    render(<CtaSection title="Title" />)
    const link = screen.getByRole("link", { name: /get started/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "/register")
  })

  it("renders primary CTA with custom label and href", () => {
    render(<CtaSection title="Title" primaryLabel="Sign Up" primaryHref="/signup" />)
    const link = screen.getByRole("link", { name: /sign up/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "/signup")
  })

  it("renders secondary CTA when provided", () => {
    render(<CtaSection title="Title" secondaryLabel="Learn More" secondaryHref="/learn" />)
    expect(screen.getByRole("link", { name: /learn more/i })).toBeInTheDocument()
  })

  it("does not render secondary CTA when not provided", () => {
    render(<CtaSection title="Title" />)
    const links = screen.getAllByRole("link")
    expect(links).toHaveLength(1)
  })
})
