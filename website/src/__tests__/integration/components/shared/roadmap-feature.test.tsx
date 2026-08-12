import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { RoadmapFeature } from "@/components/shared/roadmap-feature"
import { trackEvent } from "@/services/analytics"

vi.mock("@/services/analytics", () => ({
  trackEvent: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe("RoadmapFeature", () => {
  it("renders the title, description, and target quarter badge", () => {
    render(
      <RoadmapFeature
        title="Route Optimization v2"
        description="Better ETAs and fuel savings."
        targetQuarter="Q4 2026"
      />
    )

    expect(screen.getByRole("article", { name: /route optimization v2/i })).toBeInTheDocument()
    expect(screen.getByText("Route Optimization v2")).toBeInTheDocument()
    expect(screen.getByText("Better ETAs and fuel savings.")).toBeInTheDocument()
    expect(screen.getByText("Q4 2026")).toBeInTheDocument()
  })

  it("does not render a quarter badge when none is provided", () => {
    render(<RoadmapFeature title="No date" description="desc" />)
    expect(screen.queryByText(/Q[1-4] 20\d\d/)).not.toBeInTheDocument()
  })

  it("renders custom children content", () => {
    render(
      <RoadmapFeature title="With children" description="desc">
        <button type="button">Custom CTA</button>
      </RoadmapFeature>
    )
    expect(screen.getByRole("button", { name: /custom cta/i })).toBeInTheDocument()
  })

  it("does not show the notify button when notifyAction is absent", () => {
    render(<RoadmapFeature title="No notify" description="desc" />)
    expect(screen.queryByRole("button", { name: /notify me/i })).not.toBeInTheDocument()
  })

  it("fires notifyAction and the analytics event when Notify me is clicked", () => {
    const notifyAction = vi.fn()
    render(
      <RoadmapFeature
        title="AI Copilot"
        description="Smarter dispatch."
        notifyAction={notifyAction}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /notify me about ai copilot/i }))

    expect(notifyAction).toHaveBeenCalledTimes(1)
    expect(trackEvent).toHaveBeenCalledWith("feature_interest_clicked", "roadmap", "AI Copilot")
  })
})
