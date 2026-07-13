import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { StatusBadge } from "@/components/shared/status-badge"

describe("StatusBadge", () => {
  it("renders label", () => {
    render(<StatusBadge status="operational" label="All Systems Go" />)
    expect(screen.getByText("All Systems Go")).toBeInTheDocument()
  })

  it("renders default label when no label provided", () => {
    render(<StatusBadge status="operational" />)
    expect(screen.getByText("Operational")).toBeInTheDocument()
  })

  it("renders green dot for operational status", () => {
    const { container } = render(<StatusBadge status="operational" />)
    const dot = container.querySelector("span > span")
    expect(dot?.className).toContain("bg-green-500")
  })

  it("renders yellow dot for degraded status", () => {
    const { container } = render(<StatusBadge status="degraded" />)
    const dot = container.querySelector("span > span")
    expect(dot?.className).toContain("bg-yellow-500")
  })

  it("renders red dot for outage status", () => {
    const { container } = render(<StatusBadge status="outage" />)
    const dot = container.querySelector("span > span")
    expect(dot?.className).toContain("bg-red-500")
  })

  it("renders blue dot for maintenance status", () => {
    const { container } = render(<StatusBadge status="maintenance" />)
    const dot = container.querySelector("span > span")
    expect(dot?.className).toContain("bg-blue-500")
  })

  it("renders green dot for active status", () => {
    const { container } = render(<StatusBadge status="active" />)
    const dot = container.querySelector("span > span")
    expect(dot?.className).toContain("bg-green-500")
  })

  it("hides dot when showDot is false", () => {
    const { container } = render(<StatusBadge status="operational" showDot={false} />)
    const dot = container.querySelector("span > span")
    expect(dot).toBeNull()
  })

  it("applies correct text color class for operational", () => {
    const { container } = render(<StatusBadge status="operational" />)
    const badge = container.firstChild as HTMLElement
    expect(badge.className).toContain("text-green-700")
  })

  it("applies correct text color class for degraded", () => {
    const { container } = render(<StatusBadge status="degraded" />)
    const badge = container.firstChild as HTMLElement
    expect(badge.className).toContain("text-yellow-700")
  })

  it("applies correct text color class for outage", () => {
    const { container } = render(<StatusBadge status="outage" />)
    const badge = container.firstChild as HTMLElement
    expect(badge.className).toContain("text-red-700")
  })

  it("applies correct text color class for maintenance", () => {
    const { container } = render(<StatusBadge status="maintenance" />)
    const badge = container.firstChild as HTMLElement
    expect(badge.className).toContain("text-blue-700")
  })
})
