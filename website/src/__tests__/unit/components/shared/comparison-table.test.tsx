import { describe, it, expect, vi } from "vitest"
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
  it("renders column headers from props", () => {
    render(<ComparisonTable columns={columns} rows={rows} />)
    expect(screen.getByText("Free")).toBeInTheDocument()
    expect(screen.getByText("Pro")).toBeInTheDocument()
    expect(screen.getByText("Enterprise")).toBeInTheDocument()
  })

  it("renders the 'Feature' header column", () => {
    render(<ComparisonTable columns={columns} rows={rows} />)
    expect(screen.getByText("Feature")).toBeInTheDocument()
  })

  it("renders feature rows from props", () => {
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

  it("renders checkmark icon for boolean true values", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const checkSvgs = container.querySelectorAll("svg.lucide-check")
    // Route Planning has all true, API Access has 2 true, Custom Branding has 1 true
    expect(checkSvgs.length).toBe(6)
  })

  it("renders cross icon for boolean false values", () => {
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

  it("renders table HTML structure correctly", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    expect(container.querySelector("table")).toBeInTheDocument()
    expect(container.querySelector("thead")).toBeInTheDocument()
    expect(container.querySelector("tbody")).toBeInTheDocument()
  })

  it("applies alternating row background classes", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const rowsEl = container.querySelectorAll("tbody tr")
    expect(rowsEl.length).toBe(4)

    // Odd rows should have default styling, even rows (index % 2 === 1) get bg-muted/10
    rowsEl.forEach((row, index) => {
      if (index % 2 === 1) {
        expect(row.className).toContain("bg-muted/10")
      }
    })
  })

  it("applies hover style to all rows", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const rowsEl = container.querySelectorAll("tbody tr")
    rowsEl.forEach((row) => {
      expect(row.className).toContain("hover:bg-muted/30")
    })
  })

  it("adds border-top to each row", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const rowsEl = container.querySelectorAll("tbody tr")
    rowsEl.forEach((row) => {
      expect(row.className).toContain("border-t")
      expect(row.className).toContain("border-border")
    })
  })

  it("has responsive horizontal scroll container", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const outerDiv = container.firstChild as HTMLElement
    expect(outerDiv.className).toContain("overflow-x-auto")
    expect(outerDiv.className).toContain("w-full")
  })

  it("applies custom className to wrapper", () => {
    const { container } = render(
      <ComparisonTable columns={columns} rows={rows} className="my-custom-class" />
    )
    const outerDiv = container.firstChild as HTMLElement
    expect(outerDiv.className).toContain("my-custom-class")
  })

  it("renders single row correctly", () => {
    const singleRow = [{ feature: "Max Users", values: [true, false, true] }]
    render(<ComparisonTable columns={columns} rows={singleRow} />)
    expect(screen.getByText("Max Users")).toBeInTheDocument()
    expect(screen.getByText("Free")).toBeInTheDocument()
    expect(screen.getByText("Pro")).toBeInTheDocument()
    expect(screen.getByText("Enterprise")).toBeInTheDocument()

    const { container } = render(<ComparisonTable columns={columns} rows={singleRow} />)
    const rowsEl = container.querySelectorAll("tbody tr")
    expect(rowsEl.length).toBe(1)
    const checkSvgs = container.querySelectorAll("svg.lucide-check")
    expect(checkSvgs.length).toBe(2)
    const xSvgs = container.querySelectorAll("svg.lucide-x")
    expect(xSvgs.length).toBe(1)
  })

  it("renders empty state when columns array is empty", () => {
    render(<ComparisonTable columns={[]} rows={rows} />)
    expect(screen.getByText("No data available.")).toBeInTheDocument()
  })

  it("renders empty state when rows array is empty", () => {
    render(<ComparisonTable columns={columns} rows={[]} />)
    expect(screen.getByText("No data available.")).toBeInTheDocument()
  })

  it("renders empty state when both arrays are empty", () => {
    const { container } = render(<ComparisonTable columns={[]} rows={[]} />)
    expect(container.textContent).toContain("No data available")
  })

  it("renders empty state without table structure", () => {
    const { container } = render(<ComparisonTable columns={[]} rows={[]} />)
    expect(container.querySelector("table")).toBeNull()
    expect(container.querySelector("thead")).toBeNull()
    expect(container.querySelector("tbody")).toBeNull()
  })

  it("handles all boolean true values in a row", () => {
    const allTrueRow = [{ feature: "All Features", values: [true, true, true] }]
    const { container } = render(<ComparisonTable columns={columns} rows={allTrueRow} />)
    const checkSvgs = container.querySelectorAll("svg.lucide-check")
    expect(checkSvgs.length).toBe(3)
    const xSvgs = container.querySelectorAll("svg.lucide-x")
    expect(xSvgs.length).toBe(0)
  })

  it("handles all boolean false values in a row", () => {
    const allFalseRow = [{ feature: "No Features", values: [false, false, false] }]
    const { container } = render(<ComparisonTable columns={columns} rows={allFalseRow} />)
    const checkSvgs = container.querySelectorAll("svg.lucide-check")
    expect(checkSvgs.length).toBe(0)
    const xSvgs = container.querySelectorAll("svg.lucide-x")
    expect(xSvgs.length).toBe(3)
  })

  it("handles mixed string and boolean values", () => {
    const mixedRows = [
      { feature: "Mixed", values: ["Included", true, false] },
    ]
    render(<ComparisonTable columns={columns} rows={mixedRows} />)
    expect(screen.getByText("Included")).toBeInTheDocument()
    const { container } = render(<ComparisonTable columns={columns} rows={mixedRows} />)
    expect(container.querySelectorAll("svg.lucide-check").length).toBe(1)
    expect(container.querySelectorAll("svg.lucide-x").length).toBe(1)
  })

  it("sticky feature column has correct minimum width", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const featureHeaders = container.querySelectorAll("th.sticky")
    const featureCells = container.querySelectorAll("td.sticky")
    expect(featureHeaders.length).toBe(1)
    expect(featureCells.length).toBe(4)
    featureHeaders.forEach((el) => {
      expect(el.className).toContain("min-w-[160px]")
    })
  })

  it("does not throw when clicking on table row", () => {
    render(<ComparisonTable columns={columns} rows={rows} />)
    const rowsEl = screen.getAllByText("Users")
    expect(() => {
      rowsEl[0].click()
    }).not.toThrow()
  })

  it("does not throw when clicking on CTA-like content area", () => {
    render(<ComparisonTable columns={columns} rows={rows} />)
    const featureHeaders = screen.getAllByText("Feature")
    expect(() => {
      featureHeaders[0].click()
    }).not.toThrow()
  })

  it("renders all column headers with uppercase tracking class", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const headers = container.querySelectorAll("thead th")
    headers.forEach((header) => {
      expect(header.className).toContain("uppercase")
      expect(header.className).toContain("tracking-wider")
    })
  })

  it("renders feature cell with font-medium class", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    const featureCells = container.querySelectorAll("td.sticky")
    featureCells.forEach((cell) => {
      expect(cell.className).toContain("font-medium")
    })
  })

  it("renders column count matching columns prop", () => {
    const { container } = render(<ComparisonTable columns={columns} rows={rows} />)
    // Feature column + 3 data columns = 4 columns
    const headerCells = container.querySelectorAll("thead th")
    expect(headerCells.length).toBe(4) // Feature + Free + Pro + Enterprise
  })
})
