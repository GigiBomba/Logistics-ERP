import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import { FeatureCard } from "@/components/shared/feature-card"
import { MapPin } from "lucide-react"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("FeatureCard", () => {
  it("renders title", () => {
    render(<FeatureCard icon={MapPin} title="Route Planning" description="Optimize your routes" />)
    expect(screen.getByText("Route Planning")).toBeInTheDocument()
  })

  it("renders description", () => {
    render(<FeatureCard icon={MapPin} title="Title" description="Description here" />)
    expect(screen.getByText("Description here")).toBeInTheDocument()
  })

  it("renders icon", () => {
    const { container } = render(
      <FeatureCard icon={MapPin} title="Title" description="Desc" />
    )
    const svg = container.querySelector("svg")
    expect(svg).toBeInTheDocument()
  })
})
