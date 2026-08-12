import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import CustomersPage from "@/pages/public/customers"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("CustomersPage", () => {
  it("renders heading", () => {
    render(<CustomersPage />)
    expect(screen.getAllByText("Customer Stories").length).toBeGreaterThanOrEqual(1)
  })

  it("shows coming soon message", () => {
    render(<CustomersPage />)
    expect(screen.getByText("Coming soon")).toBeInTheDocument()
    expect(
      screen.getByText(/success stories will appear here/i)
    ).toBeInTheDocument()
  })

  it("renders call-to-action section", () => {
    render(<CustomersPage />)
    expect(screen.getByText("Get in touch")).toBeInTheDocument()
  })
})
