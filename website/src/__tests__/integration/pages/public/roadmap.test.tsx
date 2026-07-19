import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import RoadmapPage from "@/pages/public/roadmap"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("RoadmapPage", () => {
  it("renders heading", () => {
    render(<RoadmapPage />)
    expect(screen.getByText("Roadmap")).toBeInTheDocument()
  })

  it("renders status filters", () => {
    render(<RoadmapPage />)
    const progressEls = screen.getAllByText("In Progress")
    expect(progressEls.length).toBeGreaterThanOrEqual(1)
    const plannedEls = screen.getAllByText("Planned")
    expect(plannedEls.length).toBeGreaterThanOrEqual(1)
    const completedEls = screen.getAllByText("Completed")
    expect(completedEls.length).toBeGreaterThanOrEqual(1)
  })
})
