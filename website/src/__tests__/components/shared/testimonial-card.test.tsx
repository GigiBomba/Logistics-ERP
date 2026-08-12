import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import { TestimonialCard } from "@/components/shared/testimonial-card"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("TestimonialCard", () => {
  it("renders quote, name, role, company", () => {
    render(
      <TestimonialCard
        quote="Great product!"
        name="John Doe"
        role="CEO"
        company="Acme Inc"
      />
    )
    expect(screen.getByText(/great product/i)).toBeInTheDocument()
    expect(screen.getByText("John Doe")).toBeInTheDocument()
    expect(screen.getByText(/ceo.*acme inc/i)).toBeInTheDocument()
  })

  it("renders initials from name", () => {
    render(
      <TestimonialCard
        quote="Amazing!"
        name="Jane Smith"
        role="Manager"
        company="Co"
      />
    )
    expect(screen.getByText("JS")).toBeInTheDocument()
  })

  it("renders single-char initials", () => {
    render(
      <TestimonialCard
        quote="Wow"
        name="Alice"
        role="Engineer"
        company="Tech"
      />
    )
    expect(screen.getByText("A")).toBeInTheDocument()
  })

  it("renders two-char initials for a multi-word name", () => {
    render(
      <TestimonialCard
        quote="Ok"
        name="John M Doe"
        role="Dev"
        company="Inc"
      />
    )
    expect(screen.getByText("JM")).toBeInTheDocument()
  })
})
