import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { Button } from "@/components/ui/button"
import { Link } from "react-router"

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Click me</Button>)
    expect(screen.getByRole("button", { name: /click me/i })).toBeInTheDocument()
  })

  it("applies default variant classes", () => {
    render(<Button>Default</Button>)
    const btn = screen.getByRole("button")
    expect(btn.className).toContain("bg-primary")
  })

  it("applies outline variant", () => {
    render(<Button variant="outline">Outline</Button>)
    expect(screen.getByRole("button").className).toContain("border-input")
  })

  it("applies destructive variant", () => {
    render(<Button variant="destructive">Destructive</Button>)
    expect(screen.getByRole("button").className).toContain("bg-destructive")
  })

  it("applies secondary variant", () => {
    render(<Button variant="secondary">Secondary</Button>)
    expect(screen.getByRole("button").className).toContain("bg-secondary")
  })

  it("applies ghost variant", () => {
    render(<Button variant="ghost">Ghost</Button>)
    expect(screen.getByRole("button").className).toContain("hover:bg-accent")
  })

  it("applies link variant", () => {
    render(<Button variant="link">Link</Button>)
    expect(screen.getByRole("button").className).toContain("underline-offset-4")
  })

  it("applies size classes", () => {
    render(<Button size="sm">Small</Button>)
    expect(screen.getByRole("button").className).toContain("h-8")
  })

  it("applies large size", () => {
    render(<Button size="lg">Large</Button>)
    expect(screen.getByRole("button").className).toContain("h-10")
  })

  it("applies xl size", () => {
    render(<Button size="xl">XL</Button>)
    expect(screen.getByRole("button").className).toContain("h-12")
  })

  it("applies icon size", () => {
    render(<Button size="icon">+</Button>)
    expect(screen.getByRole("button").className).toContain("w-9")
  })

  it("renders as disabled", () => {
    render(<Button disabled>Disabled</Button>)
    expect(screen.getByRole("button")).toBeDisabled()
  })

  it("supports asChild with Link", () => {
    render(
      <Button asChild>
        <Link to="/test">Link Button</Link>
      </Button>
    )
    expect(screen.getByRole("link")).toBeInTheDocument()
    expect(screen.getByRole("link")).toHaveAttribute("href", "/test")
  })

  it("forwards className", () => {
    render(<Button className="custom-class">Custom</Button>)
    expect(screen.getByRole("button").className).toContain("custom-class")
  })
})
