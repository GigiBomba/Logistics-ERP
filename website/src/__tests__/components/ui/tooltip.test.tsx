import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, act } from "@/test-utils"
import { Tooltip } from "@/components/ui/tooltip"

describe("Tooltip", () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it("renders children", () => {
    render(
      <Tooltip content="Tooltip text">
        <button>Hover me</button>
      </Tooltip>
    )

    expect(screen.getByText("Hover me")).toBeInTheDocument()
  })

  it("shows tooltip text on mouse enter", () => {
    vi.useFakeTimers()

    render(
      <Tooltip content="Tooltip text" delay={0}>
        <button>Hover me</button>
      </Tooltip>
    )

    const wrapper = screen.getByText("Hover me").parentElement!

    act(() => {
      fireEvent.mouseEnter(wrapper)
      vi.advanceTimersByTime(0)
    })

    expect(screen.getByRole("tooltip")).toHaveTextContent("Tooltip text")
  })

  it("hides tooltip on mouse leave", () => {
    vi.useFakeTimers()

    render(
      <Tooltip content="Tooltip text" delay={0}>
        <button>Hover me</button>
      </Tooltip>
    )

    const wrapper = screen.getByText("Hover me").parentElement!

    act(() => {
      fireEvent.mouseEnter(wrapper)
      vi.advanceTimersByTime(0)
    })

    expect(screen.getByRole("tooltip")).toBeInTheDocument()

    act(() => {
      fireEvent.mouseLeave(wrapper)
      vi.advanceTimersByTime(0)
    })

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
  })

  it("applies top side positioning by default", () => {
    vi.useFakeTimers()

    render(
      <Tooltip content="Tooltip text" delay={0}>
        <button>Hover me</button>
      </Tooltip>
    )

    const wrapper = screen.getByText("Hover me").parentElement!

    act(() => {
      fireEvent.mouseEnter(wrapper)
      vi.advanceTimersByTime(0)
    })

    const tooltip = screen.getByRole("tooltip")
    expect(tooltip.className).toContain("bottom-full")
  })

  it("applies bottom side positioning", () => {
    vi.useFakeTimers()

    render(
      <Tooltip content="Tooltip text" delay={0} side="bottom">
        <button>Hover me</button>
      </Tooltip>
    )

    const wrapper = screen.getByText("Hover me").parentElement!

    act(() => {
      fireEvent.mouseEnter(wrapper)
      vi.advanceTimersByTime(0)
    })

    const tooltip = screen.getByRole("tooltip")
    expect(tooltip.className).toContain("top-full")
  })
})
