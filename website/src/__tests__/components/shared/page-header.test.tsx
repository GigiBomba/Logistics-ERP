import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { PageHeader } from "@/components/shared/page-header"

describe("PageHeader", () => {
  it("renders title", () => {
    render(<PageHeader title="Test Title" />)
    expect(screen.getByRole("heading", { name: /test title/i })).toBeInTheDocument()
  })

  it("renders description", () => {
    render(<PageHeader title="Title" description="Test description" />)
    expect(screen.getByText("Test description")).toBeInTheDocument()
  })

  it("renders children", () => {
    render(<PageHeader title="Title"><button>Action</button></PageHeader>)
    expect(screen.getByRole("button", { name: /action/i })).toBeInTheDocument()
  })

  it("renders without description", () => {
    render(<PageHeader title="Only Title" />)
    expect(screen.getByRole("heading", { name: /only title/i })).toBeInTheDocument()
  })
})
