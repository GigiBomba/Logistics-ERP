import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { StatCard } from "@/components/shared/stat-card"
import { MapPin } from "lucide-react"

describe("StatCard", () => {
  it("renders value and label", () => {
    render(<StatCard value="12,345" label="Total Orders" />)
    expect(screen.getByText("12,345")).toBeInTheDocument()
    expect(screen.getByText("Total Orders")).toBeInTheDocument()
  })

  it("renders icon when provided", () => {
    const { container } = render(
      <StatCard value="99" label="Issues" icon={MapPin} />
    )
    const svg = container.querySelector("svg")
    expect(svg).toBeInTheDocument()
  })

  it("does not render icon when not provided", () => {
    const { container } = render(<StatCard value="10" label="Items" />)
    const svg = container.querySelector("svg")
    expect(svg).not.toBeInTheDocument()
  })

  it("renders trend up with green color on text", () => {
    render(
      <StatCard
        value="500"
        label="Revenue"
        trend={{ direction: "up", value: "+12.5%" }}
      />
    )
    const trendValue = screen.getByText("+12.5%")
    expect(trendValue).toBeInTheDocument()
    expect(trendValue).toHaveClass("text-green-600")
    expect(screen.getByText("vs last month")).toBeInTheDocument()
  })

  it("renders trend down with red color on text", () => {
    render(
      <StatCard
        value="200"
        label="Bounces"
        trend={{ direction: "down", value: "-3.2%" }}
      />
    )
    const trendValue = screen.getByText("-3.2%")
    expect(trendValue).toBeInTheDocument()
    expect(trendValue).toHaveClass("text-red-600")
    expect(screen.getByText("vs last month")).toBeInTheDocument()
  })

  it("renders trending up icon with green class for up trend", () => {
    const { container } = render(
      <StatCard
        value="500"
        label="Revenue"
        trend={{ direction: "up", value: "+12.5%" }}
      />
    )
    const svgs = container.querySelectorAll("svg")
    // The TrendingUp icon has text-green-600 class on the icon container
    const trendingUpIcon = Array.from(svgs).find(
      (svg) => svg.classList.contains("text-green-600") || svg.closest(".text-green-600")
    )
    expect(trendingUpIcon).toBeTruthy()
  })

  it("renders trending down icon with red class for down trend", () => {
    const { container } = render(
      <StatCard
        value="200"
        label="Bounces"
        trend={{ direction: "down", value: "-3.2%" }}
      />
    )
    const svgs = container.querySelectorAll("svg")
    const trendingDownIcon = Array.from(svgs).find(
      (svg) => svg.classList.contains("text-red-600") || svg.closest(".text-red-600")
    )
    expect(trendingDownIcon).toBeTruthy()
  })

  it("does not render trend section when trend is not provided", () => {
    render(<StatCard value="50" label="Items" />)
    expect(screen.queryByText("vs last month")).not.toBeInTheDocument()
  })

  it("forwards className to the container", () => {
    const { container } = render(
      <StatCard value="1" label="Test" className="custom-class" />
    )
    const outerDiv = container.firstChild as HTMLElement
    expect(outerDiv.className).toContain("custom-class")
  })

  it("handles large numbers rendered as strings", () => {
    render(<StatCard value="1,234,567" label="Total Users" />)
    expect(screen.getByText("1,234,567")).toBeInTheDocument()
    expect(screen.getByText("Total Users")).toBeInTheDocument()
  })

  it("handles decimal values", () => {
    render(<StatCard value="99.99" label="Avg Rating" />)
    expect(screen.getByText("99.99")).toBeInTheDocument()
  })

  it("handles percentage values", () => {
    render(<StatCard value="87.5%" label="Completion Rate" />)
    expect(screen.getByText("87.5%")).toBeInTheDocument()
  })

  it("handles missing value as empty string", () => {
    const { container } = render(<StatCard value="" label="No Data" />)
    // The value p element renders empty; use container query to find it
    const valueEl = container.querySelector("p.text-3xl")
    expect(valueEl).toBeInTheDocument()
    expect(valueEl?.textContent).toBe("")
    expect(screen.getByText("No Data")).toBeInTheDocument()
  })

  it("renders value in a bold large text element", () => {
    render(<StatCard value="42" label="Answer" />)
    const valueEl = screen.getByText("42")
    expect(valueEl.tagName).toBe("P")
    expect(valueEl.className).toContain("text-3xl")
    expect(valueEl.className).toContain("font-bold")
  })

  it("renders label in muted small text", () => {
    render(<StatCard value="X" label="Small Label" />)
    const labelEl = screen.getByText("Small Label")
    expect(labelEl.className).toContain("text-sm")
    expect(labelEl.className).toContain("text-muted-foreground")
  })
})
