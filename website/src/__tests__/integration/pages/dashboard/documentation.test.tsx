import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import DocumentationPage from "@/pages/dashboard/documentation"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("DocumentationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders "Documentation" heading and description', () => {
    render(<DocumentationPage />)
    expect(screen.getByText("Documentation")).toBeInTheDocument()
    expect(screen.getByText(/Learn how to get the most out of Operion ERP/i)).toBeInTheDocument()
  })

  it("shows search input with placeholder", () => {
    render(<DocumentationPage />)
    expect(screen.getByPlaceholderText(/Search documentation/i)).toBeInTheDocument()
  })

  it("renders all 8 documentation category cards", () => {
    render(<DocumentationPage />)
    expect(screen.getByText("Getting Started")).toBeInTheDocument()
    expect(screen.getByText("Route Planning")).toBeInTheDocument()
    expect(screen.getByText("Fleet Tracking")).toBeInTheDocument()
    expect(screen.getByText("Dispatch")).toBeInTheDocument()
    expect(screen.getByText("OCR & Documents")).toBeInTheDocument()
    expect(screen.getByText("Analytics")).toBeInTheDocument()
    expect(screen.getByText("Administration")).toBeInTheDocument()
    expect(screen.getByText("API Reference")).toBeInTheDocument()
  })

  it("shows article counts on category cards", () => {
    render(<DocumentationPage />)
    // "5 articles" and "6 articles" each appear twice; use getAllByText
    expect(screen.getAllByText("5 articles").length).toBe(2)
    expect(screen.getByText("8 articles")).toBeInTheDocument()
    expect(screen.getByText("3 articles")).toBeInTheDocument()
  })

  it("shows category descriptions", () => {
    render(<DocumentationPage />)
    expect(screen.getByText(/Installation, setup, and first steps/i)).toBeInTheDocument()
    expect(screen.getByText(/Learn how to create and optimize routes/i)).toBeInTheDocument()
    expect(screen.getByText(/Integrate Operion with your existing systems/i)).toBeInTheDocument()
  })

  it("renders Video Tutorials section with Coming Soon", () => {
    render(<DocumentationPage />)
    expect(screen.getByText("Video Tutorials")).toBeInTheDocument()
    expect(screen.getByText(/Step-by-step video guides/i)).toBeInTheDocument()
    expect(screen.getAllByText("Coming Soon").length).toBeGreaterThanOrEqual(1)
  })

  it("wraps category cards in links to docs sections", () => {
    render(<DocumentationPage />)
    const gettingStartedLink = screen.getByText("Getting Started").closest("a")
    expect(gettingStartedLink).toHaveAttribute("href", "/docs/getting-started")
    const apiLink = screen.getByText("API Reference").closest("a")
    expect(apiLink).toHaveAttribute("href", "/docs/api")
  })
})
