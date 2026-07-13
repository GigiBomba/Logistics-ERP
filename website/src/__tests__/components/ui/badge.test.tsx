import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { Badge } from "@/components/ui/badge"

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge>New</Badge>)
    expect(screen.getByText("New")).toBeInTheDocument()
  })

  it("applies default variant classes", () => {
    render(<Badge>Badge</Badge>)
    const badge = screen.getByText("Badge")
    expect(badge.className).toContain("bg-primary")
    expect(badge.className).toContain("text-primary-foreground")
  })

  it("applies secondary variant", () => {
    render(<Badge variant="secondary">Secondary</Badge>)
    expect(screen.getByText("Secondary").className).toContain("bg-secondary")
  })

  it("applies destructive variant", () => {
    render(<Badge variant="destructive">Destructive</Badge>)
    expect(screen.getByText("Destructive").className).toContain("bg-destructive")
  })

  it("applies outline variant", () => {
    render(<Badge variant="outline">Outline</Badge>)
    expect(screen.getByText("Outline").className).toContain("text-foreground")
  })

  it("applies success variant", () => {
    render(<Badge variant="success">Success</Badge>)
    expect(screen.getByText("Success").className).toContain("bg-green-100")
  })

  it("forwards className", () => {
    render(<Badge className="custom-badge">Custom</Badge>)
    expect(screen.getByText("Custom").className).toContain("custom-badge")
  })
})
