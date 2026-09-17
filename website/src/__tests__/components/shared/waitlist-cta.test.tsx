import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { WaitlistCta } from "@/components/shared/waitlist-cta"
import { trackCTAClick } from "@/services/analytics"

vi.mock("@/services/analytics", () => ({
  trackCTAClick: vi.fn(),
}))

describe("WaitlistCta", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders a link to the waitlist with the source query param", () => {
    render(<WaitlistCta source="route_calculator" />)
    const link = screen.getByRole("link", { name: /join waitlist/i })
    expect(link).toHaveAttribute("href", "/waitlist?source=route_calculator")
  })

  it("keeps blog-style source values (blog:<slug>) intact in the href", () => {
    render(<WaitlistCta source="blog:operion-ai-copilot-intelligent-logistics-automation" />)
    const link = screen.getByRole("link", { name: /join waitlist/i })
    expect(link).toHaveAttribute(
      "href",
      "/waitlist?source=blog:operion-ai-copilot-intelligent-logistics-automation"
    )
  })

  it("fires trackCTAClick with the source and current page on click", () => {
    render(<WaitlistCta source="profit_calculator" />, { initialEntries: ["/roi-calculator"] })
    fireEvent.click(screen.getByRole("link", { name: /join waitlist/i }))
    expect(trackCTAClick).toHaveBeenCalledWith("profit_calculator", "/roi-calculator")
  })

  it("applies an optional className", () => {
    const { container } = render(<WaitlistCta source="x" className="mt-8" />)
    expect(container.querySelector("a")).toHaveClass("mt-8")
  })
})