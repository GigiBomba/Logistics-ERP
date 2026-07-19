import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { ComparisonTable } from "@/components/shared/comparison-table"
import { MapPin } from "lucide-react"

const columns = [
  { label: "Free" },
  { label: "Pro", icon: MapPin },
  { label: "Enterprise" },
]

const rows = [
  { feature: "Users", values: ["Up to 5", "Unlimited", "Unlimited"] },
  { feature: "Route Planning", values: [true, true, true] },
  { feature: "API Access", values: [false, true, true] },
  { feature: "Custom Branding", values: [false, false, true] },
]

describe("ComparisonTable", () => {
  it("renders column headers", () => {
    render(<ComparisonTable columns={columns} rows={rows} />)
    expect(screen.getByText("Free")).toBeInTheDocument()
    expect(screen.getByText("Pro")).toBeInTheDocument()
    expect(screen.getByText("Enterprise")).toBeInTheDocument()
  })

  it("renders feature rows", () => {
    render(<ComparisonTable columns={columns} rows={rows} />)
    expect(screen.getByText("Users")).toBeInTheDocument()
    expect(screen.getByText("Route Planning")).toBeInTheDocument()
    expect(screen.getByText("API Access")).toBeInTheDocument()
    expect(screen.getByText("Custom Branding")).toBeInTheDocument()
  })

  it("renders text values for string entries", () => {
    render(<ComparisonTable columns={columns} rows={rows} />)
    expect(screen.getByText("Up to 5")).toBeInTheDocument()
    expect(screen.getAllByText("Unlimited")).toHaveLength(2)
  })

  it("renders checkmark for boolean true", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const checkSvgs = container.querySelectorAll("svg.lucide-check")
    // Route Planning has all true, API Access has 2 true, Custom Branding has 1 true
    expect(checkSvgs.length).toBe(6)
  })

  it("renders cross for boolean false", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const xSvgs = container.querySelectorAll("svg.lucide-x")
    // API Access has 1 false, Custom Branding has 2 false
    expect(xSvgs.length).toBe(3)
  })

  it("renders icon in column header when provided", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const icons = container.querySelectorAll("svg.lucide-map-pin")
    expect(icons.length).toBe(1)
  })

  it("has responsive scroll container", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const outerDiv = container.firstChild as HTMLElement
    expect(outerDiv.className).toContain("overflow-x-auto")
  })

  it("shows empty state when no columns or rows", () => {
    const { container } = render(
      <ComparisonTable columns={[]} rows={[]} />
    )
    expect(container.textContent).toContain("No data available")
  })
})
