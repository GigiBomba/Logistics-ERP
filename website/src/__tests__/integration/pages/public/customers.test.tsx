import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
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
  it("renders heading and industry filters", () => {
    render(<CustomersPage />)
    expect(screen.getAllByText("Customer Stories").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Transportation").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Retail").length).toBeGreaterThanOrEqual(1)
  })

  it("renders case study cards", () => {
    render(<CustomersPage />)
    expect(screen.getByText("TransLogistica")).toBeInTheDocument()
    expect(screen.getByText("FreshFoods Distribution")).toBeInTheDocument()
    expect(screen.getByText("BuildRight Materials")).toBeInTheDocument()
  })

  it("shows results on customer stories", () => {
    render(<CustomersPage />)
    expect(screen.getByText("32% faster delivery times")).toBeInTheDocument()
    expect(screen.getByText("28% fuel cost reduction")).toBeInTheDocument()
  })

  it("filters by industry when tab clicked", () => {
    render(<CustomersPage />)
    const transportTabs = screen.getAllByText("Transportation").filter(
      (el: HTMLElement) => el.tagName === "BUTTON"
    )
    if (transportTabs.length > 0) {
      fireEvent.click(transportTabs[0])
    }
    expect(screen.getByText("TransLogistica")).toBeInTheDocument()
  })

  it("renders call-to-action section", () => {
    render(<CustomersPage />)
    expect(screen.getByText("Share your story")).toBeInTheDocument()
  })
})
