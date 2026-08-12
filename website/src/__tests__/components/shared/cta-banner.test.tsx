import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { CtaBanner } from "@/components/shared/cta-banner"

describe("CtaBanner", () => {
  const defaultProps = {
    title: "Get Started Today",
    description: "Sign up now and start building.",
    buttonText: "Get Started",
    buttonHref: "/signup",
  }

  it("renders title", () => {
    render(<CtaBanner {...defaultProps} />)
    expect(screen.getByText("Get Started Today")).toBeInTheDocument()
  })

  it("renders description", () => {
    render(<CtaBanner {...defaultProps} />)
    expect(screen.getByText("Sign up now and start building.")).toBeInTheDocument()
  })

  it("renders without description", () => {
    render(<CtaBanner title="Title" buttonText="Go" buttonHref="/go" />)
    expect(screen.queryByText("Sign up now and start building.")).not.toBeInTheDocument()
  })

  it("renders button with correct text", () => {
    render(<CtaBanner {...defaultProps} />)
    expect(screen.getByRole("link", { name: /get started/i })).toBeInTheDocument()
  })

  it("renders button link with correct href", () => {
    render(<CtaBanner {...defaultProps} />)
    const link = screen.getByRole("link", { name: /get started/i })
    expect(link).toHaveAttribute("href", "/signup")
  })

  it("applies primary variant styles by default", () => {
    const { container } = render(<CtaBanner {...defaultProps} />)
    const card = container.querySelector("[class*='border-primary']")
    expect(card).toBeTruthy()
  })

  it("applies outline variant styles when specified", () => {
    const { container } = render(<CtaBanner {...defaultProps} variant="outline" />)
    const card = container.querySelector("[class*='border-accent']")
    expect(card).toBeTruthy()
  })

  it("renders ArrowRight icon in button", () => {
    const { container } = render(<CtaBanner {...defaultProps} />)
    const svg = container.querySelector("svg")
    expect(svg).toBeInTheDocument()
  })
})
