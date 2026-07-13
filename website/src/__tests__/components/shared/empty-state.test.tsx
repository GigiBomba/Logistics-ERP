import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { EmptyState } from "@/components/shared/empty-state"

describe("EmptyState", () => {
  it("renders title", () => {
    render(<EmptyState title="Nothing here" />)
    expect(screen.getByText("Nothing here")).toBeInTheDocument()
  })

  it("renders description", () => {
    render(<EmptyState title="Empty" description="No items found" />)
    expect(screen.getByText("No items found")).toBeInTheDocument()
  })

  it("renders action button", () => {
    render(<EmptyState title="Empty" action={<button>Add Item</button>} />)
    expect(screen.getByRole("button", { name: /add item/i })).toBeInTheDocument()
  })

  it("renders default icon (PackageOpen)", () => {
    const { container } = render(<EmptyState title="Empty" />)
    const svg = container.querySelector("svg")
    expect(svg).toBeInTheDocument()
  })

  it("renders without description", () => {
    render(<EmptyState title="Just Title" />)
    expect(screen.getByText("Just Title")).toBeInTheDocument()
  })
})
