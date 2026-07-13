import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { Separator } from "@/components/ui/separator"

describe("Separator", () => {
  it("renders a decorative separator by default", () => {
    const { container } = render(<Separator />)
    const el = container.firstChild as HTMLElement
    expect(el).toBeInTheDocument()
    expect(el).toHaveAttribute("role", "none")
  })

  it("renders horizontal orientation by default", () => {
    const { container } = render(<Separator />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("h-[1px]")
    expect(el.className).toContain("w-full")
  })

  it("renders vertical orientation", () => {
    const { container } = render(<Separator orientation="vertical" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("h-full")
    expect(el.className).toContain("w-[1px]")
  })

  it("applies role separator when non-decorative", () => {
    const { container } = render(<Separator decorative={false} />)
    const el = container.firstChild as HTMLElement
    expect(el).toHaveAttribute("role", "separator")
    expect(el).toHaveAttribute("aria-orientation", "horizontal")
  })

  it("forwards className", () => {
    const { container } = render(<Separator className="custom-sep" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("custom-sep")
  })
})
