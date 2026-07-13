import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { Tag } from "@/components/ui/tag"

describe("Tag", () => {
  it("renders as span by default", () => {
    render(<Tag>Default</Tag>)
    const el = screen.getByText("Default")
    expect(el.tagName).toBe("SPAN")
  })

  it("renders as anchor when href is provided", () => {
    render(<Tag href="/tags/react">React</Tag>)
    const el = screen.getByText("React")
    expect(el.tagName).toBe("A")
    expect(el).toHaveAttribute("href", "/tags/react")
  })

  it("applies default variant classes", () => {
    render(<Tag>Tag</Tag>)
    const el = screen.getByText("Tag")
    expect(el.className).toContain("bg-primary/10")
    expect(el.className).toContain("text-primary")
  })

  it("applies outline variant classes", () => {
    render(<Tag variant="outline">Outline</Tag>)
    const el = screen.getByText("Outline")
    expect(el.className).toContain("border-border")
    expect(el.className).toContain("text-muted-foreground")
  })

  it("renders link with outline variant", () => {
    render(<Tag variant="outline" href="/outline">Linked</Tag>)
    const el = screen.getByText("Linked")
    expect(el.tagName).toBe("A")
    expect(el.className).toContain("border-border")
  })

  it("forwards className", () => {
    render(<Tag className="custom-tag">Custom</Tag>)
    expect(screen.getByText("Custom").className).toContain("custom-tag")
  })
})
