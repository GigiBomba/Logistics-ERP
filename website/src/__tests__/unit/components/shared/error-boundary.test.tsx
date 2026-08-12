import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { WidgetErrorBoundary } from "@/components/shared/error-boundary"

// Suppress console.error for expected error-catch tests
beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {})
})

/** Helper component that throws an error on render */
function Bomb({ shouldThrow = false }: { shouldThrow?: boolean }) {
  if (shouldThrow) {
    throw new Error("💥")
  }
  return <div>Safe content</div>
}

describe("WidgetErrorBoundary", () => {
  it("renders children when no error occurs", () => {
    render(
      <WidgetErrorBoundary>
        <div>Child content</div>
      </WidgetErrorBoundary>
    )
    expect(screen.getByText("Child content")).toBeInTheDocument()
  })

  it("catches thrown errors from child components", () => {
    render(
      <WidgetErrorBoundary>
        <Bomb shouldThrow />
      </WidgetErrorBoundary>
    )
    // The error-boundary should catch the error and render fallback instead
    expect(screen.queryByText("Safe content")).not.toBeInTheDocument()
  })

  it("renders the default fallback UI when an error is caught", () => {
    render(
      <WidgetErrorBoundary>
        <Bomb shouldThrow />
      </WidgetErrorBoundary>
    )
    expect(
      screen.getByText("Something went wrong loading this section.")
    ).toBeInTheDocument()
  })

  it("renders default fallback with a warning icon", () => {
    const { container } = render(
      <WidgetErrorBoundary>
        <Bomb shouldThrow />
      </WidgetErrorBoundary>
    )
    // TriangleAlert icon from lucide-react renders as an SVG
    const svg = container.querySelector("svg")
    expect(svg).toBeInTheDocument()
  })

  it("renders default fallback inside a card with destructive styling", () => {
    render(
      <WidgetErrorBoundary>
        <Bomb shouldThrow />
      </WidgetErrorBoundary>
    )
    const fallbackText = screen.getByText("Something went wrong loading this section.")
    const card = fallbackText.closest('[class*="border-destructive"]')
    expect(card).toBeInTheDocument()
  })

  it("renders custom fallback element when provided instead of default", () => {
    render(
      <WidgetErrorBoundary fallback={<div>Custom error UI</div>}>
        <Bomb shouldThrow />
      </WidgetErrorBoundary>
    )
    expect(screen.getByText("Custom error UI")).toBeInTheDocument()
    expect(
      screen.queryByText("Something went wrong loading this section.")
    ).not.toBeInTheDocument()
  })

  it("does not show children after an error is caught", () => {
    render(
      <WidgetErrorBoundary>
        <Bomb shouldThrow />
      </WidgetErrorBoundary>
    )
    // The error boundary catches the error and replaces children with fallback
    expect(screen.queryByText("Safe content")).not.toBeInTheDocument()
  })

  it("continues rendering children normally when no error occurs with a safe Bomb", () => {
    render(
      <WidgetErrorBoundary>
        <Bomb shouldThrow={false} />
      </WidgetErrorBoundary>
    )
    expect(screen.getByText("Safe content")).toBeInTheDocument()
  })

  it("wraps children in a Card layout when showing fallback", () => {
    render(
      <WidgetErrorBoundary>
        <Bomb shouldThrow />
      </WidgetErrorBoundary>
    )
    const text = screen.getByText("Something went wrong loading this section.")
    // It should be inside a CardContent (which sits inside a Card)
    expect(text.closest('[class*="card"]')).toBeInTheDocument()
  })
})
