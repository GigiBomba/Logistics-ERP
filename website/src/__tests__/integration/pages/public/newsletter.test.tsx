import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import NewsletterPage from "@/pages/public/newsletter"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/config/site", () => ({
  siteConfig: {
    name: "Operion",
  },
  apiConfig: { baseUrl: "http://localhost:8000", timeout: 15000 },
}))

describe("NewsletterPage", () => {
  it("renders heading and description", () => {
    render(<NewsletterPage />)
    expect(screen.getByText("Stay Updated")).toBeInTheDocument()
    expect(screen.getByText(/get the latest news/i)).toBeInTheDocument()
  })

  it("renders subscription form", () => {
    render(<NewsletterPage />)
    expect(screen.getByPlaceholderText(/you@company.com/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /subscribe/i })).toBeInTheDocument()
  })

  it("renders privacy policy link", () => {
    render(<NewsletterPage />)
    expect(screen.getByText(/privacy policy/i)).toBeInTheDocument()
  })
})
