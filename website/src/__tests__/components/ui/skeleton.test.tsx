import { describe, it, expect } from "vitest"
import { render } from "@/test-utils"
import { Skeleton } from "@/components/ui/skeleton"

describe("Skeleton", () => {
  it("renders", () => {
    const { container } = render(<Skeleton />)
    expect(container.firstChild).toBeInTheDocument()
  })

  it("has pulse animation class", () => {
    const { container } = render(<Skeleton />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("animate-pulse")
  })

  it("has rounded-md class", () => {
    const { container } = render(<Skeleton />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("rounded-md")
  })

  it("forwards className", () => {
    const { container } = render(<Skeleton className="custom-skel" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("custom-skel")
  })
})
