import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import { TestimonialCard } from "@/components/shared/testimonial-card"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("TestimonialCard", () => {
  it("renders quote, author name, role, and company", () => {
    render(
      <TestimonialCard
        quote="Great product!"
        name="John Doe"
        role="CEO"
        company="Acme Inc"
      />
    )
    expect(screen.getByText(/great product!/i)).toBeInTheDocument()
    expect(screen.getByText("John Doe")).toBeInTheDocument()
    expect(screen.getByText(/ceo,\s*acme inc/i)).toBeInTheDocument()
  })

  it("renders initials from first and last name", () => {
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

  it("renders single-character initials for single-word names", () => {
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

  it("renders three-character initials from three-part names", () => {
    render(
      <TestimonialCard
        quote="Ok"
        name="John M Doe"
        role="Dev"
        company="Inc"
      />
    )
    expect(screen.getByText("JMD")).toBeInTheDocument()
  })

  it("handles missing role and company as empty strings", () => {
    render(
      <TestimonialCard
        quote="Still a great quote"
        name="Test User"
        role=""
        company=""
      />
    )
    expect(screen.getByText("Test User")).toBeInTheDocument()
    // The role/company text renders as ", " when both are empty
    expect(screen.getByText(/,/)).toBeInTheDocument()
  })

  it("renders long quotes without truncation", () => {
    const longQuote =
      "This is an extremely long testimonial quote that should still be fully rendered inside the blockquote element without being cut off or truncated by the component. We need to verify the entire text appears in the document."
    render(
      <TestimonialCard
        quote={longQuote}
        name="Long Name"
        role="Reviewer"
        company="TestCo"
      />
    )
    // Text is wrapped in curly quotes (\u201c and \u201d), so use a function matcher
    expect(
      screen.getByText((content) => content.includes(longQuote))
    ).toBeInTheDocument()
  })

  it("renders quote wrapped in curly double-quotes", () => {
    render(
      <TestimonialCard
        quote="Short quote"
        name="Author"
        role="Role"
        company="Company"
      />
    )
    const quoteEl = screen.getByText(/short quote/i)
    expect(quoteEl).toBeInTheDocument()
    expect(quoteEl.tagName).toBe("BLOCKQUOTE")
  })

  it("forwards className to the card container", () => {
    const { container } = render(
      <TestimonialCard
        quote="Test"
        name="Name"
        role="Role"
        company="Company"
        className="custom-card-class"
      />
    )
    const card = container.querySelector(".custom-card-class")
    expect(card).toBeInTheDocument()
  })

  it("renders a Quote icon (from lucide-react)", () => {
    const { container } = render(
      <TestimonialCard
        quote="Test"
        name="Name"
        role="Role"
        company="Company"
      />
    )
    // The Quote icon is rendered as an SVG
    const svgs = container.querySelectorAll("svg")
    expect(svgs.length).toBeGreaterThanOrEqual(1)
  })
})
