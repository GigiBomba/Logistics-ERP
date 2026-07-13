import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { Progress } from "@/components/ui/progress"

describe("Progress", () => {
  it("renders with a given value", () => {
    render(<Progress value={50} />)
    const bar = screen.getByRole("progressbar")
    expect(bar).toBeInTheDocument()
  })

  it("has correct ARIA attributes", () => {
    render(<Progress value={42} />)
    const bar = screen.getByRole("progressbar")
    expect(bar).toHaveAttribute("aria-valuemin", "0")
    expect(bar).toHaveAttribute("aria-valuemax", "100")
    expect(bar).toHaveAttribute("aria-valuenow", "42")
    expect(bar).toHaveAttribute("aria-label", "42%")
  })

  it("clamps value to 0 minimum", () => {
    render(<Progress value={-10} />)
    const bar = screen.getByRole("progressbar")
    expect(bar).toHaveAttribute("aria-valuenow", "0")
  })

  it("clamps value to 100 maximum", () => {
    render(<Progress value={150} />)
    const bar = screen.getByRole("progressbar")
    expect(bar).toHaveAttribute("aria-valuenow", "100")
  })

  it("applies default variant class", () => {
    const { container } = render(<Progress value={50} />)
    const inner = container.querySelector(".h-full")
    expect(inner?.className).toContain("bg-primary")
  })

  it("applies success variant class", () => {
    const { container } = render(<Progress value={50} variant="success" />)
    const inner = container.querySelector(".h-full")
    expect(inner?.className).toContain("bg-emerald-500")
  })

  it("applies warning variant class", () => {
    const { container } = render(<Progress value={50} variant="warning" />)
    const inner = container.querySelector(".h-full")
    expect(inner?.className).toContain("bg-amber-500")
  })

  it("renders inner bar with correct width", () => {
    const { container } = render(<Progress value={75} />)
    const inner = container.querySelector(".h-full") as HTMLElement
    expect(inner.style.width).toBe("75%")
  })
})
