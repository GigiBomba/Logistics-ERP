import { describe, it, expect } from "vitest"
import { render } from "@/test-utils"
import { LoadingSpinner, Skeleton, PageSkeleton } from "@/components/ui/loading-spinner"

describe("LoadingSpinner", () => {
  it("renders an animated spinner", () => {
    render(<LoadingSpinner />)
    const svg = document.querySelector("svg")
    expect(svg).toBeInTheDocument()
    expect(svg!.getAttribute("class")).toContain("animate-spin")
  })

  it("renders small size", () => {
    render(<LoadingSpinner size="sm" />)
    const svg = document.querySelector("svg")!
    expect(svg.getAttribute("class")).toContain("h-4")
    expect(svg.getAttribute("class")).toContain("w-4")
  })

  it("renders large size", () => {
    render(<LoadingSpinner size="lg" />)
    const svg = document.querySelector("svg")!
    expect(svg.getAttribute("class")).toContain("h-12")
    expect(svg.getAttribute("class")).toContain("w-12")
  })

  it("renders medium size", () => {
    render(<LoadingSpinner size="md" />)
    const svg = document.querySelector("svg")!
    expect(svg.getAttribute("class")).toContain("h-8")
    expect(svg.getAttribute("class")).toContain("w-8")
  })
})

describe("Skeleton", () => {
  it("renders with animate-pulse", () => {
    render(<Skeleton className="h-10 w-64" />)
    const skeleton = document.querySelector(".animate-pulse")!
    expect(skeleton).toBeInTheDocument()
    expect(skeleton.getAttribute("class")).toContain("h-10")
    expect(skeleton.getAttribute("class")).toContain("bg-muted")
  })
})

describe("PageSkeleton", () => {
  it("renders multiple skeleton elements", () => {
    render(<PageSkeleton />)
    const skeletons = document.querySelectorAll(".animate-pulse")
    expect(skeletons.length).toBeGreaterThan(3)
  })
})
