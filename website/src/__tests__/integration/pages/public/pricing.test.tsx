import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import PricingPage from "@/pages/public/pricing"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("PricingPage", () => {
  it("renders page header with title and description", () => {
    render(<PricingPage />)
    expect(screen.getByText("Simple, Transparent Pricing")).toBeInTheDocument()
    expect(
      screen.getByText(/Available Now.*autonomous dispatch engine is operational and free to use/i)
    ).toBeInTheDocument()
  })

  it("renders Coming Soon card", () => {
    render(<PricingPage />)
    expect(screen.getByText("Coming Soon")).toBeInTheDocument()
    expect(
      screen.getByText(/autonomous dispatch engine is operational and free during the current phase/i)
    ).toBeInTheDocument()
  })

  it("renders early access CTA button linking to /register", () => {
    render(<PricingPage />)
    const earlyAccessLink = screen.getByRole("link", {
      name: /sign up for early access/i,
    })
    expect(earlyAccessLink).toBeInTheDocument()
    expect(earlyAccessLink).toHaveAttribute("href", "/register")
  })

  it("renders FAQ section with questions", () => {
    render(<PricingPage />)
    expect(screen.getByText("Pricing FAQ")).toBeInTheDocument()
    expect(screen.getByText("Is Operion currently available?")).toBeInTheDocument()
    expect(
      screen.getByText("Will there be a free trial when pricing launches?")
    ).toBeInTheDocument()
    expect(
      screen.getByText("What payment methods will be accepted?")
    ).toBeInTheDocument()
  })

  it("renders bottom CTA section", () => {
    render(<PricingPage />)
    expect(screen.getByText("Start Using Autonomous Dispatching")).toBeInTheDocument()
    expect(
      screen.getByText(/Operion is free during the current phase/i)
    ).toBeInTheDocument()
  })

  it("renders Sign Up link in bottom CTA", () => {
    render(<PricingPage />)
    const signUpLinks = screen
      .getAllByRole("link")
      .filter((l) => l.getAttribute("href") === "/register")
    expect(signUpLinks.length).toBeGreaterThanOrEqual(1)
  })

  it("renders canonical link in helmet", () => {
    render(<PricingPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operionerp.xyz/pricing")
  })
})
