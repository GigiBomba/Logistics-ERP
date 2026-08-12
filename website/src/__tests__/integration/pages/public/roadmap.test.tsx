import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import RoadmapPage from "@/pages/public/roadmap"

vi.mock("@/services/queries", () => ({
  useRoadmap: vi.fn(() => ({
    data: [
      { id: "1", title: "FastAPI Backend", status: "completed", category: "Architecture", quarter: "Q3 2026", target_date: "2026-07-01" },
      { id: "2", title: "Mobile Driver Companion", status: "in_progress", category: "Mobile", quarter: "Q4 2026", target_date: "2026-10-01" },
      { id: "3", title: "Trip Cost Calculator", status: "completed", category: "Architecture", quarter: "Q3 2026", target_date: "2026-07-15" },
    ],
    isLoading: false,
  })),
}))

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe("RoadmapPage", () => {
  it("renders Roadmap heading", () => {
    render(<RoadmapPage />)
    expect(screen.getByText("Roadmap")).toBeInTheDocument()
  })

  it("renders roadmap items with titles", async () => {
    render(<RoadmapPage />)
    const fastapiEls = await screen.findAllByText("FastAPI Backend")
    expect(fastapiEls.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Mobile Driver Companion")).toBeInTheDocument()
  })

  it("shows status badges", async () => {
    render(<RoadmapPage />)
    const completedEls = await screen.findAllByText("Completed")
    expect(completedEls.length).toBeGreaterThanOrEqual(1)
  })

  it("shows voting placeholder section", () => {
    render(<RoadmapPage />)
    expect(screen.getByText("Want to influence the roadmap?")).toBeInTheDocument()
    expect(screen.getByText(/built in the open/i)).toBeInTheDocument()
  })

  it("renders category for items", async () => {
    render(<RoadmapPage />)
    const archEls = await screen.findAllByText("Architecture")
    expect(archEls.length).toBeGreaterThanOrEqual(1)
  })
})
