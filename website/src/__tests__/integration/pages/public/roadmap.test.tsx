import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import RoadmapPage from "@/pages/public/roadmap"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
}))

describe("RoadmapPage", () => {
  it("renders Roadmap heading", () => {
    render(<RoadmapPage />)
    expect(screen.getByText("Roadmap")).toBeInTheDocument()
  })

  it("shows filter tabs", () => {
    render(<RoadmapPage />)
    expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Planned" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "In Progress" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Completed" })
    ).toBeInTheDocument()
  })

  it("renders roadmap items with titles", () => {
    render(<RoadmapPage />)
    expect(
      screen.getByText("FastAPI Backend")
    ).toBeInTheDocument()
    expect(
      screen.getByText("Mobile Driver Companion")
    ).toBeInTheDocument()
    const calcTitles = screen.getAllByText("Trip Cost Calculator")
    expect(calcTitles.length).toBeGreaterThanOrEqual(1)
  })

  it("shows status badges", () => {
    render(<RoadmapPage />)
    // Completed items are shown in the Completed column
    const completedBadges = screen.getAllByText("Completed")
    expect(completedBadges.length).toBeGreaterThanOrEqual(1)
    const inProgressBadges = screen.getAllByText("In Progress")
    expect(inProgressBadges.length).toBeGreaterThanOrEqual(1)
  })

  it("shows voting placeholder section", () => {
    render(<RoadmapPage />)
    expect(
      screen.getByText("Want to influence the roadmap?")
    ).toBeInTheDocument()
    expect(
      screen.getByText(/built in the open/i)
    ).toBeInTheDocument()
  })

  it("shows column descriptions", () => {
    render(<RoadmapPage />)
    expect(
      screen.getByText("Under consideration and scoping")
    ).toBeInTheDocument()
    expect(
      screen.getByText("Actively being built")
    ).toBeInTheDocument()
    expect(
      screen.getByText("Shipped and available now")
    ).toBeInTheDocument()
  })

  it("renders category and quarter for items", () => {
    render(<RoadmapPage />)
    const categories = screen.getAllByText("Core Platform")
    expect(categories.length).toBeGreaterThanOrEqual(1)
    const quarters = screen.getAllByText("Q2 2026")
    expect(quarters.length).toBeGreaterThanOrEqual(1)
  })
})
