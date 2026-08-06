import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import ProductsPage from "@/pages/public/products"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("ProductsPage", () => {
  it("renders heading and product cards", () => {
    render(<ProductsPage />)
    expect(screen.getByText("The Autonomous Logistics Operating System")).toBeInTheDocument()
    expect(screen.getAllByText("Operion Core").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Operion AI Dispatch").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Operion Mobile").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Operion Toolkit").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Operion Cloud").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Operion Analytics").length).toBeGreaterThanOrEqual(1)
  })

  it("shows status badges on product cards", () => {
    render(<ProductsPage />)
    const badges = screen.getAllByText("Available")
    expect(badges.length).toBeGreaterThanOrEqual(2)
  })

  it("renders call-to-action banner", () => {
    render(<ProductsPage />)
    expect(screen.getByText("Ready to dispatch with a single instruction?")).toBeInTheDocument()
  })
})
