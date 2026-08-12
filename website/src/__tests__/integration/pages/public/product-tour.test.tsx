import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import ProductTourPage from "@/pages/public/product-tour"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("ProductTourPage", () => {
  it("renders the demo banner", () => {
    render(<ProductTourPage />)
    expect(
      screen.getByText(/this is a demo.*no real data is modified/i)
    ).toBeInTheDocument()
  })

  it("renders sidebar navigation with all items", () => {
    render(<ProductTourPage />)
    expect(screen.getByText("Dashboard")).toBeInTheDocument()
    expect(screen.getByText("Routes")).toBeInTheDocument()
    expect(screen.getByText("Fleet")).toBeInTheDocument()
    expect(screen.getByText("Dispatch")).toBeInTheDocument()
    expect(screen.getByText("Invoices")).toBeInTheDocument()
    expect(screen.getByText("Analytics")).toBeInTheDocument()
    expect(screen.getByText("Settings")).toBeInTheDocument()
  })

  it("shows Dashboard content by default", () => {
    render(<ProductTourPage />)
    expect(screen.getByText(/welcome back/i)).toBeInTheDocument()
    expect(screen.getByText("Today's Summary")).toBeInTheDocument()
  })

  it("renders stat cards on the dashboard", () => {
    render(<ProductTourPage />)
    expect(screen.getByText("Active Trips")).toBeInTheDocument()
    expect(screen.getByText("Pending Loads")).toBeInTheDocument()
    expect(screen.getByText("Drivers Available")).toBeInTheDocument()
    expect(screen.getByText("Fleet Status")).toBeInTheDocument()
  })

  it("renders quick actions section on dashboard", () => {
    render(<ProductTourPage />)
    expect(screen.getByText("Quick Actions")).toBeInTheDocument()
  })

  it("navigates to Routes section when clicked", () => {
    render(<ProductTourPage />)
    fireEvent.click(screen.getByText("Routes"))
    expect(screen.getByText("Route Planning")).toBeInTheDocument()
    expect(screen.getByText("Active Routes")).toBeInTheDocument()
  })

  it("navigates to Fleet section when clicked", () => {
    render(<ProductTourPage />)
    fireEvent.click(screen.getByText("Fleet"))
    expect(screen.getByText("Fleet Management")).toBeInTheDocument()
  })

  it("navigates to Dispatch section when clicked", () => {
    render(<ProductTourPage />)
    fireEvent.click(screen.getByText("Dispatch"))
    expect(screen.getByText("Dispatch Console")).toBeInTheDocument()
  })

  it("navigates to Invoices section when clicked", () => {
    render(<ProductTourPage />)
    fireEvent.click(screen.getByText("Invoices"))
    expect(screen.getByText(/total outstanding/i)).toBeInTheDocument()
  })

  it("navigates to Analytics section when clicked", () => {
    render(<ProductTourPage />)
    fireEvent.click(screen.getByText("Analytics"))
    expect(screen.getByText("Analytics")).toBeInTheDocument()
  })

  it("navigates to Settings section when clicked", () => {
    render(<ProductTourPage />)
    fireEvent.click(screen.getByText("Settings"))
    expect(screen.getByText(/manage your account/i)).toBeInTheDocument()
  })

  it("renders the CTA banner at the bottom", () => {
    render(<ProductTourPage />)
    expect(
      screen.getByText(/ready to use operion for real/i)
    ).toBeInTheDocument()
    expect(screen.getByText("Get Started")).toBeInTheDocument()
  })

  it("renders pro tip in the sidebar", () => {
    render(<ProductTourPage />)
    expect(screen.getByText("Pro Tip")).toBeInTheDocument()
  })

  it("renders a working search input", () => {
    render(<ProductTourPage />)
    const searchInput = screen.getByPlaceholderText("Search...")
    expect(searchInput).toBeInTheDocument()
    fireEvent.change(searchInput, { target: { value: "test query" } })
    expect(searchInput).toHaveValue("test query")
  })

  it("renders notification bell", () => {
    render(<ProductTourPage />)
    expect(screen.getByLabelText("Notifications")).toBeInTheDocument()
  })

  it("renders static demo data badges", () => {
    render(<ProductTourPage />)
    const badges = screen.getAllByText(/live demo data/i)
    expect(badges.length).toBeGreaterThanOrEqual(1)
  })
})
