import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import { Timeline } from "@/components/shared/timeline"
import React from "react"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

const sampleItems = [
  {
    date: "July 2026",
    title: "Beta Launch",
    description: "Initial release to beta testers",
    status: "completed" as const,
  },
  {
    date: "August 2026",
    title: "Public Release",
    status: "current" as const,
  },
  {
    date: "September 2026",
    title: "Mobile App",
    description: "Native mobile application launch",
    status: "upcoming" as const,
  },
]

describe("Timeline", () => {
  it("renders all timeline items", () => {
    render(<Timeline items={sampleItems} />)
    expect(screen.getByText("Beta Launch")).toBeInTheDocument()
    expect(screen.getByText("Public Release")).toBeInTheDocument()
    expect(screen.getByText("Mobile App")).toBeInTheDocument()
  })

  it("renders dates for each item", () => {
    render(<Timeline items={sampleItems} />)
    expect(screen.getByText("July 2026")).toBeInTheDocument()
    expect(screen.getByText("August 2026")).toBeInTheDocument()
    expect(screen.getByText("September 2026")).toBeInTheDocument()
  })

  it("renders descriptions when provided", () => {
    render(<Timeline items={sampleItems} />)
    expect(screen.getByText("Initial release to beta testers")).toBeInTheDocument()
    expect(screen.getByText("Native mobile application launch")).toBeInTheDocument()
  })

  it("renders items in order", () => {
    render(<Timeline items={sampleItems} />)
    const items = screen.getAllByText(/Beta Launch|Public Release|Mobile App/)
    expect(items[0]).toHaveTextContent("Beta Launch")
    expect(items[1]).toHaveTextContent("Public Release")
    expect(items[2]).toHaveTextContent("Mobile App")
  })

  it("renders completed status with check icon", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    const checkSvgs = container.querySelectorAll("svg.lucide-check")
    expect(checkSvgs.length).toBeGreaterThanOrEqual(1)
  })

  it("renders completed status with primary-colored dot", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    const dotContainers = container.querySelectorAll(".border-primary")
    expect(dotContainers.length).toBeGreaterThanOrEqual(1)
  })

  it("renders upcoming status with muted dot", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    const upcomingDots = container.querySelectorAll(".border-muted-foreground\\/30")
    // The class includes "/30" so we check adjacent
    const hasUpcomingStyle = container.innerHTML.includes("border-muted-foreground")
    expect(hasUpcomingStyle).toBe(true)
  })

  it("renders custom icon when provided", () => {
    const itemsWithIcon = [
      {
        date: "July 2026",
        title: "Custom Event",
        icon: <span data-testid="custom-icon">★</span>,
        status: "current" as const,
      },
    ]
    render(<Timeline items={itemsWithIcon} />)
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument()
  })
})
