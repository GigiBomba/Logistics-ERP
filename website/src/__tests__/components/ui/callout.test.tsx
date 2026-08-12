import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { Callout } from "@/components/ui/callout"

describe("Callout", () => {
  it("renders title and children", () => {
    render(
      <Callout title="Notice">
        This is important.
      </Callout>
    )

    expect(screen.getByText("Notice")).toBeInTheDocument()
    expect(screen.getByText("This is important.")).toBeInTheDocument()
  })

  it("renders default info variant with blue border", () => {
    const { container } = render(<Callout>Info</Callout>)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("border-blue-200")
    expect(el.className).toContain("bg-blue-50")
    expect(el.className).toContain("text-blue-800")
  })

  it("renders warning variant with amber colors", () => {
    const { container } = render(<Callout variant="warning">Warning</Callout>)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("border-amber-200")
    expect(el.className).toContain("bg-amber-50")
    expect(el.className).toContain("text-amber-800")
  })

  it("renders success variant with emerald colors", () => {
    const { container } = render(<Callout variant="success">Success</Callout>)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("border-emerald-200")
    expect(el.className).toContain("bg-emerald-50")
    expect(el.className).toContain("text-emerald-800")
  })

  it("renders danger variant with red colors", () => {
    const { container } = render(<Callout variant="danger">Danger</Callout>)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("border-red-200")
    expect(el.className).toContain("bg-red-50")
    expect(el.className).toContain("text-red-800")
  })

  it("renders an icon by default", () => {
    const { container } = render(<Callout variant="info">With icon</Callout>)
    // The default icon is an Info SVG element with aria-hidden="true"
    const svg = container.querySelector("svg")
    expect(svg).toBeInTheDocument()
    expect(svg).toHaveAttribute("aria-hidden", "true")
  })

  it("renders custom icon instead of default", () => {
    const { container } = render(<Callout icon={<span data-testid="custom-icon">★</span>}>Custom</Callout>)
    expect(container.querySelector('[data-testid="custom-icon"]')).toBeInTheDocument()
  })
})
