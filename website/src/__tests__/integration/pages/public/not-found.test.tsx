import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import NotFoundPage from "@/pages/public/not-found"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: (_target, tag) => {
        const Tag = tag as any
        return ({ children, ...props }: any) => <Tag {...props}>{children}</Tag>
      },
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("NotFoundPage", () => {
  it("renders 404 status code", () => {
    render(<NotFoundPage />)
    expect(screen.getByText("404")).toBeInTheDocument()
  })

  it("renders not found heading", () => {
    render(<NotFoundPage />)
    expect(screen.getByText("Page Not Found")).toBeInTheDocument()
  })

  it("renders description text", () => {
    render(<NotFoundPage />)
    expect(
      screen.getByText(/the page you're looking for doesn't exist/i)
    ).toBeInTheDocument()
  })

  it("renders go home link pointing to /", () => {
    render(<NotFoundPage />)
    const homeLink = screen.getByText("Go Home").closest("a")
    expect(homeLink).toHaveAttribute("href", "/")
  })

  it("renders contact support link pointing to /contact", () => {
    render(<NotFoundPage />)
    const contactLink = screen.getByText("Contact").closest("a")
    expect(contactLink).toHaveAttribute("href", "/contact")
  })

  it("renders all helpful action links", () => {
    render(<NotFoundPage />)
    // 4 helpful links (Home, Features, Pricing, Contact) + 1 Go Home button link
    const buttons = screen.getAllByRole("link")
    expect(buttons).toHaveLength(5)
  })
})
