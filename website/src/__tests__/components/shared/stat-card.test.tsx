import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { StatCard } from "@/components/shared/stat-card"
import { MapPin } from "lucide-react"

describe("StatCard", () => {
  it("renders value and label", () => {
    render(<StatCard value="12,345" label="Total Orders" />)
    expect(screen.getByText("12,345")).toBeInTheDocument()
    expect(screen.getByText("Total Orders")).toBeInTheDocument()
  })

  it("renders icon when provided", () => {
    const { container } = render(
      <StatCard value="99" label="Issues" icon={MapPin} />
    )
    const svg = container.querySelector("svg")
    expect(svg).toBeInTheDocument()
  })

  it("does not render icon when not provided", () => {
    const { container } = render(<StatCard value="10" label="Items" />)
    const svg = container.querySelector("svg")
    expect(svg).not.toBeInTheDocument()
  })

  it("renders trend up with green color", () => {
    render(
      <StatCard
        value="500"
        label="Revenue"
        trend={{ direction: "up", value: "+12.5%" }}
      />
    )
    expect(screen.getByText("+12.5%")).toBeInTheDocument()
    expect(screen.getByText("+12.5%")).toHaveClass("text-green-600")
    expect(screen.getByText("vs last month")).toBeInTheDocument()
  })

  it("renders trend down with red color", () => {
    render(
      <StatCard
        value="200"
        label="Bounces"
        trend={{ direction: "down", value: "-3.2%" }}
      />
    )
    expect(screen.getByText("-3.2%")).toBeInTheDocument()
    expect(screen.getByText("-3.2%")).toHaveClass("text-red-600")
  })

  it("does not render trend section when not provided", () => {
    render(<StatCard value="50" label="Items" />)
    expect(screen.queryByText("vs last month")).not.toBeInTheDocument()
  })

  it("forwards className to the container", () => {
    const { container } = render(
      <StatCard value="1" label="Test" className="custom-class" />
    )
    const outerDiv = container.firstChild as HTMLElement
    expect(outerDiv.className).toContain("custom-class")
  })
})
