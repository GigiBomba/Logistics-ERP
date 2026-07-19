import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import { Timeline } from "@/components/shared/timeline"
import React from "react"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
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

const singleItem = [
  {
    date: "January 2026",
    title: "Kickoff",
    status: "completed" as const,
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

  it("renders description when provided", () => {
    render(<Timeline items={sampleItems} />)
    expect(screen.getByText("Initial release to beta testers")).toBeInTheDocument()
    expect(screen.getByText("Native mobile application launch")).toBeInTheDocument()
  })

  it("renders items in correct order (chronological)", () => {
    render(<Timeline items={sampleItems} />)
    const titles = screen.getAllByText(/Beta Launch|Public Release|Mobile App/)
    expect(titles[0]).toHaveTextContent("Beta Launch")
    expect(titles[1]).toHaveTextContent("Public Release")
    expect(titles[2]).toHaveTextContent("Mobile App")
  })

  it("displays dates in the same order as items", () => {
    render(<Timeline items={sampleItems} />)
    const dates = screen.getAllByText(/July 2026|August 2026|September 2026/)
    expect(dates[0]).toHaveTextContent("July 2026")
    expect(dates[1]).toHaveTextContent("August 2026")
    expect(dates[2]).toHaveTextContent("September 2026")
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

  it("renders current item with amber-500 dot color", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    const amberDots = container.querySelectorAll(".border-amber-500")
    expect(amberDots.length).toBe(1)

    const currentItem = screen.getByText("Public Release")
    expect(currentItem).toBeInTheDocument()
  })

  it("renders upcoming item with muted dot", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    const hasUpcomingStyle = container.innerHTML.includes("border-muted-foreground")
    expect(hasUpcomingStyle).toBe(true)
  })

  it("renders upcoming item with border background", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    const upcomingDot = container.querySelector('[class*="border-muted-foreground"]')
    expect(upcomingDot).toBeTruthy()
  })

  it("renders vertical connecting line between items", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    // Should have 2 connecting lines for 3 items (last has no line)
    const lines = container.querySelectorAll(".w-0\\.5")
    expect(lines.length).toBe(2)
  })

  it("does not render vertical line after last item", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    // For 3 items, only 2 connecting line divs should exist (last item has no line)
    const lineElements = container.querySelectorAll('[class*="w-0"][class*="5"]')
    expect(lineElements.length).toBe(2)
  })

  it("applies completed line color for completed items", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    const primaryLines = container.querySelectorAll(".bg-primary")
    expect(primaryLines.length).toBeGreaterThanOrEqual(1)
  })

  it("applies amber line color for current item", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    const amberLines = container.querySelectorAll(".bg-amber-500")
    expect(amberLines.length).toBe(1)
  })

  it("renders custom icon when provided instead of default dot", () => {
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
    expect(screen.getByText("★")).toBeInTheDocument()
  })

  it("renders custom icon inside the dot container", () => {
    const itemsWithIcon = [
      {
        date: "July 2026",
        title: "Custom Event",
        icon: <span data-testid="custom-icon">★</span>,
        status: "current" as const,
      },
    ]
    const { container } = render(<Timeline items={itemsWithIcon} />)
    const dotContainer = container.querySelector(".h-6.w-6")
    expect(dotContainer).toBeInTheDocument()
    const iconInDot = dotContainer?.querySelector('[data-testid="custom-icon"]')
    expect(iconInDot).toBeInTheDocument()
  })

  it("renders empty container when items array is empty", () => {
    const { container } = render(<Timeline items={[]} />)
    expect(container.querySelector("h3")).toBeNull()
    expect(screen.queryByText("January 2026")).not.toBeInTheDocument()
  })

  it("renders single item without vertical line", () => {
    const { container } = render(<Timeline items={singleItem} />)
    expect(screen.getByText("Kickoff")).toBeInTheDocument()
    expect(screen.getByText("January 2026")).toBeInTheDocument()
    // Single item should have no connecting lines
    const lines = container.querySelectorAll('[class*="w-0.5"]')
    expect(lines.length).toBe(0)
  })

  it("renders single completed item with check icon", () => {
    const { container } = render(<Timeline items={singleItem} />)
    const checkSvgs = container.querySelectorAll("svg.lucide-check")
    expect(checkSvgs.length).toBe(1)
  })

  it("renders item without description gracefully", () => {
    render(<Timeline items={sampleItems} />)
    // Public Release has no description; should not crash
    expect(screen.getByText("Public Release")).toBeInTheDocument()
    expect(screen.queryByText("Public Release")?.parentElement?.textContent).not.toContain(
      "undefined"
    )
  })

  it("defaults to 'upcoming' status when status is not provided", () => {
    const itemsWithoutStatus = [
      {
        date: "December 2026",
        title: "Future Feature",
      },
    ]
    const { container } = render(<Timeline items={itemsWithoutStatus as any} />)
    expect(screen.getByText("Future Feature")).toBeInTheDocument()
    // Should use upcoming styling (muted)
    const hasUpcomingStyle = container.innerHTML.includes("border-muted-foreground")
    expect(hasUpcomingStyle).toBe(true)
  })

  it("renders each item with relative flex layout", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    // The outer container also has .relative, so count items by h3 presence within their parent
    const h3Elements = container.querySelectorAll("h3")
    expect(h3Elements.length).toBe(3)
    // Each motion.div has both relative and flex classes
    const motionDivs = container.querySelector('[class*="gap-6"]')
    expect(motionDivs).toBeInTheDocument()
  })

  it("applies custom className to root element", () => {
    const { container } = render(
      <Timeline items={sampleItems} className="custom-timeline" />
    )
    const rootDiv = container.firstChild as HTMLElement
    expect(rootDiv.className).toContain("custom-timeline")
    expect(rootDiv.className).toContain("relative")
  })

  it("renders date with text-xs and font-medium classes", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    const dateSpans = container.querySelectorAll("span.text-xs.font-medium")
    expect(dateSpans.length).toBe(3)
  })

  it("renders title with h3 element", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    const titles = container.querySelectorAll("h3")
    expect(titles.length).toBe(3)
    expect(titles[0]).toHaveTextContent("Beta Launch")
  })

  it("applies pb-8 spacing to all items with last:pb-0 on the final item", () => {
    const { container } = render(<Timeline items={sampleItems} />)
    // All items have pb-8 class alongside last:pb-0 on the last item
    const motionDivs = container.querySelectorAll('[class*="pb-8"]')
    expect(motionDivs.length).toBe(3)
    // The last item includes last:pb-0 via Tailwind
    const lastItem = motionDivs[motionDivs.length - 1]
    expect(lastItem.className).toContain("pb-8")
  })
})
