import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import { PricingCard } from "@/components/shared/pricing-card"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

const baseProps = {
  name: "Starter",
  price: "€49",
  description: "For small fleets",
  features: ["Up to 5 vehicles", "Route planning", "Email support"],
}

describe("PricingCard", () => {
  it("renders plan name and price", () => {
    render(<PricingCard {...baseProps} />)
    expect(screen.getByText("Starter")).toBeInTheDocument()
    expect(screen.getByText("€49")).toBeInTheDocument()
  })

  it("renders description", () => {
    render(<PricingCard {...baseProps} />)
    expect(screen.getByText("For small fleets")).toBeInTheDocument()
  })

  it("renders all features", () => {
    render(<PricingCard {...baseProps} />)
    expect(screen.getByText("Up to 5 vehicles")).toBeInTheDocument()
    expect(screen.getByText("Route planning")).toBeInTheDocument()
    expect(screen.getByText("Email support")).toBeInTheDocument()
  })

  it("shows yearly price when provided", () => {
    render(<PricingCard {...baseProps} yearlyPrice="€39" />)
    expect(screen.getByText(/€39.*month billed yearly/)).toBeInTheDocument()
  })

  it("shows Most Popular badge when highlighted", () => {
    render(<PricingCard {...baseProps} highlighted />)
    expect(screen.getByText("Most Popular")).toBeInTheDocument()
  })

  it("does not show Most Popular badge when not highlighted", () => {
    render(<PricingCard {...baseProps} />)
    expect(screen.queryByText("Most Popular")).not.toBeInTheDocument()
  })

  it("renders CTA button with default label", () => {
    render(<PricingCard {...baseProps} />)
    expect(screen.getByRole("link", { name: /start free trial/i })).toBeInTheDocument()
  })

  it("renders CTA button with custom label", () => {
    render(<PricingCard {...baseProps} ctaLabel="Buy Now" />)
    expect(screen.getByRole("link", { name: /buy now/i })).toBeInTheDocument()
  })

  it("renders CTA with custom href", () => {
    render(<PricingCard {...baseProps} ctaHref="/checkout" />)
    expect(screen.getByRole("link")).toHaveAttribute("href", "/checkout")
  })

  it("has /month suffix on price", () => {
    render(<PricingCard {...baseProps} />)
    expect(screen.getByText(/\/month/)).toBeInTheDocument()
  })
})
