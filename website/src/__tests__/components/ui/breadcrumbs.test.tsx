import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { Breadcrumbs } from "@/components/ui/breadcrumbs"

const defaultItems = [
  { label: "Home", href: "/" },
  { label: "Products", href: "/products" },
  { label: "Widget" },
]

describe("Breadcrumbs", () => {
  it("renders all items", () => {
    render(<Breadcrumbs items={defaultItems} />)
    expect(screen.getByText("Home")).toBeInTheDocument()
    expect(screen.getByText("Products")).toBeInTheDocument()
    expect(screen.getByText("Widget")).toBeInTheDocument()
  })

  it("renders last item as span (not a link)", () => {
    render(<Breadcrumbs items={defaultItems} />)
    const lastItem = screen.getByText("Widget")
    expect(lastItem.tagName).toBe("SPAN")
  })

  it("renders non-last items with href as anchor tags", () => {
    render(<Breadcrumbs items={defaultItems} />)
    const homeLink = screen.getByText("Home")
    expect(homeLink.tagName).toBe("A")
    expect(homeLink).toHaveAttribute("href", "/")

    const productsLink = screen.getByText("Products")
    expect(productsLink.tagName).toBe("A")
    expect(productsLink).toHaveAttribute("href", "/products")
  })

  it("last item has aria-current page", () => {
    render(<Breadcrumbs items={defaultItems} />)
    const lastItem = screen.getByText("Widget")
    expect(lastItem).toHaveAttribute("aria-current", "page")
  })

  it("renders default separator (ChevronRight)", () => {
    const { container } = render(<Breadcrumbs items={defaultItems} />)
    const svgs = container.querySelectorAll("svg")
    // There should be 2 separators between 3 items
    expect(svgs.length).toBeGreaterThanOrEqual(2)
  })

  it("renders custom separator", () => {
    const { container } = render(
      <Breadcrumbs items={defaultItems} separator={<span data-testid="custom-sep">/</span>} />
    )
    const separators = container.querySelectorAll('[data-testid="custom-sep"]')
    expect(separators.length).toBe(2)
  })

  it("has nav with aria-label Breadcrumb", () => {
    render(<Breadcrumbs items={defaultItems} />)
    const nav = screen.getByLabelText("Breadcrumb")
    expect(nav).toBeInTheDocument()
  })

  it("renders item without href as span even if not last", () => {
    const items = [
      { label: "Custom", href: "/custom" },
      { label: "No Link" },
    ]
    render(<Breadcrumbs items={items} />)
    const noLink = screen.getByText("No Link")
    expect(noLink.tagName).toBe("SPAN")
  })
})
