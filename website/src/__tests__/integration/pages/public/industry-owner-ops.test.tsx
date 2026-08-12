import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import IndustryOwnerOpsPage from "@/pages/public/industry-owner-ops"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("IndustryOwnerOpsPage", () => {
  it("renders page header with title", () => {
    render(<IndustryOwnerOpsPage />)
    expect(screen.getByText("Operion for Owner-Operators")).toBeInTheDocument()
  })

  it("renders challenges section with owner-operator specific challenges", () => {
    render(<IndustryOwnerOpsPage />)
    expect(screen.getByText("Industry Challenges")).toBeInTheDocument()
    expect(screen.getByText("Invoicing")).toBeInTheDocument()
    expect(screen.getByText("Expense Tracking")).toBeInTheDocument()
    expect(screen.getByText("Load Finding")).toBeInTheDocument()
    expect(screen.getByText("Compliance")).toBeInTheDocument()
  })

  it("renders solutions section", () => {
    render(<IndustryOwnerOpsPage />)
    expect(screen.getByText("How Operion Helps")).toBeInTheDocument()
    expect(screen.getByText("Invoice Automation")).toBeInTheDocument()
    expect(screen.getByText("Expense Management")).toBeInTheDocument()
    expect(screen.getByText("Load Matching")).toBeInTheDocument()
    expect(screen.getByText("Document Storage")).toBeInTheDocument()
  })

  it("renders workflow section", () => {
    render(<IndustryOwnerOpsPage />)
    expect(screen.getByText("Workflow Example")).toBeInTheDocument()
    expect(screen.getByText("Find Load")).toBeInTheDocument()
    expect(screen.getByText("Book Trip")).toBeInTheDocument()
    expect(screen.getByText("Track Expenses")).toBeInTheDocument()
    expect(screen.getByText("Auto-Invoice")).toBeInTheDocument()
    expect(screen.getByText("Get Paid")).toBeInTheDocument()
  })

  it("renders key benefits section", () => {
    render(<IndustryOwnerOpsPage />)
    expect(screen.getByText("Key Benefits")).toBeInTheDocument()
    expect(screen.getByText("Faster Invoicing")).toBeInTheDocument()
    expect(screen.getByText("More Loads/Month")).toBeInTheDocument()
    expect(screen.getByText("Faster Payments")).toBeInTheDocument()
    expect(screen.getByText("Money Saved")).toBeInTheDocument()
  })

  it("renders screenshot placeholder", () => {
    render(<IndustryOwnerOpsPage />)
    expect(screen.getByText("See It in Action")).toBeInTheDocument()
    expect(screen.getByText("Screenshot: Owner-Operator Mobile App")).toBeInTheDocument()
  })

  it("renders CTA banner with Start Free Trial link", () => {
    render(<IndustryOwnerOpsPage />)
    expect(screen.getByText("Ready to transform your owner-operator business?")).toBeInTheDocument()
    const cta = screen.getByRole("link", { name: /start free trial/i })
    expect(cta).toBeInTheDocument()
    expect(cta).toHaveAttribute("href", "/register")
  })

  it("sets correct canonical link", () => {
    render(<IndustryOwnerOpsPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operion.com/industries/owner-operators")
  })
})
