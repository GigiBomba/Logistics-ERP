import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import ContactPage from "@/pages/public/contact"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("ContactPage", () => {
  it("renders the page title", () => {
    render(<ContactPage />)
    expect(screen.getByText("Get in Touch")).toBeInTheDocument()
  })

  it("renders the contact form with all fields", () => {
    render(<ContactPage />)
    expect(screen.getByLabelText("Name")).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toBeInTheDocument()
    expect(screen.getByLabelText("Subject")).toBeInTheDocument()
    expect(screen.getByLabelText("Message")).toBeInTheDocument()
  })

  it("renders submit button", () => {
    render(<ContactPage />)
    expect(screen.getByRole("button", { name: /send message/i })).toBeInTheDocument()
  })

  it("shows email and phone contact info", () => {
    render(<ContactPage />)
    expect(screen.getByText("contact@operionerp.xyz")).toBeInTheDocument()
    expect(screen.getByText("+40 123 456 789")).toBeInTheDocument()
  })

  it("renders knowledge base and FAQ links", () => {
    render(<ContactPage />)
    expect(screen.getByText("Knowledge Base")).toBeInTheDocument()
    expect(screen.getByText("Common Questions")).toBeInTheDocument()
  })

  it("shows validation errors on empty submit", async () => {
    render(<ContactPage />)
    const submitBtn = screen.getByRole("button", { name: /send message/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      // Zod validation messages are defined inline in the schema
      expect(screen.getByText("Name must be at least 2 characters")).toBeInTheDocument()
      expect(screen.getByText("Please enter a valid email")).toBeInTheDocument()
      expect(screen.getAllByText(/must be at least/i).length).toBeGreaterThanOrEqual(2)
    })
  })

  it("renders contact methods section with badges", () => {
    render(<ContactPage />)
    expect(screen.getByText("Contact Methods")).toBeInTheDocument()
    expect(screen.getByText("The best way to reach us")).toBeInTheDocument()
    expect(screen.getByText("Inquire")).toBeInTheDocument()
  })

  it("renders navigation links to docs and faq", () => {
    render(<ContactPage />)
    const docLink = screen.getByText("Browse Documentation").closest("a")
    expect(docLink).toHaveAttribute("href", "/docs")

    const faqLink = screen.getByText("View FAQ").closest("a")
    expect(faqLink).toHaveAttribute("href", "/faq")
  })
})
